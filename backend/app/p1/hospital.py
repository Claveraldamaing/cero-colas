"""Backend-only adapter for the supplied apicitas contract.

Credentials and patient sessions live exclusively in this process. Run one worker
until an approved shared, ephemeral session service is introduced. No mock fallback.
"""
import logging
import threading
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger("cerocolas.hospital")
LIMA = timezone(timedelta(hours=-5))

ERROR_MESSAGES = {
    "IDENTIDAD_NO_VALIDA": "No encontramos un paciente con esos datos. Revisa el DNI y la fecha de nacimiento.",
    "IDENTIDAD_BLOQUEADA": "Por seguridad, espera 30 minutos o acércate a Admisión.",
    "SESION_PACIENTE_INVALIDA": "Tu identificación hospitalaria terminó. Ingresa nuevamente el DNI y la fecha de nacimiento.",
    "NO_AUTORIZADO": "No fue posible autorizar la conexión con el hospital. Comunícate con el equipo de soporte.",
    "DEMASIADAS_SOLICITUDES": "Se alcanzó el límite de intentos. Espera antes de volver a intentarlo.",
    "CANAL_CERRADO": "Las citas en línea no están disponibles en este momento.",
    "SERVICIO_NO_DISPONIBLE": "El servicio del hospital no está disponible. Intenta más tarde.",
    "DATOS_INVALIDOS": "Revisa el DNI y la fecha de nacimiento ingresados.",
    "NO_ELEGIBLE": "Por el momento no cumples las condiciones para reservar en línea.",
    "PACIENTE_SUSPENDIDO": "Por inasistencias anteriores, reserva en Admisión.",
    "ERROR_INTERNO": "El hospital no pudo completar la consulta. Intenta más tarde.",
}
REASON_MESSAGES = {
    "SIS_NO_VIGENTE": "Tu SIS no está vigente. Acércate a Admisión.",
    "SIS_NO_VERIFICABLE": "No pudimos confirmar tu SIS. Intenta más tarde.",
    "PACIENTE_NUEVO": "Para tu primera atención, acércate a Admisión.",
    "SIN_REFERENCIA": "Necesitas una referencia aceptada o recibida de tu establecimiento.",
    "SIN_ESPECIALIDADES_PROGRAMADAS": "Aún no hay horarios disponibles para tu especialidad.",
    "ESPERA_ENTRE_RESERVAS": "Aún debes esperar para realizar otra reserva. Revisa la próxima fecha permitida.",
    "PACIENTE_SUSPENDIDO": "Por inasistencias anteriores, reserva en Admisión.",
}


class HospitalError(Exception):
    def __init__(self, code: str, message: str, status: int = 503, rastreo: str | None = None, retry_after: int | None = None):
        super().__init__(code)  # Never include upstream body/credentials in exceptions.
        self.status = status
        self.detail = {"code": code, "message": message}
        if rastreo:
            self.detail["rastreo"] = rastreo
        if retry_after is not None:
            self.detail["retry_after"] = retry_after


@dataclass
class PatientIdentity:
    token: str
    expires_at: datetime
    patient: dict
    eligibility: dict | None = None


class HospitalClient:
    def __init__(self, config=settings, transport=None):
        self.config = config
        self.transport = transport  # Explicit test injection, never a runtime fallback.
        self._client_token: str | None = None
        self._token_expires = 0.0
        self._lock = threading.RLock()
        self._identities: dict[str, PatientIdentity] = {}
        self._attempts: dict[str, deque] = defaultdict(deque)

    @property
    def source(self):
        return getattr(self.config, "HOSPITAL_MODE", "simulator")

    def _configuration(self):
        url = getattr(self.config, "HOSPITAL_API_BASE_URL", "").rstrip("/")
        client_id = getattr(self.config, "HOSPITAL_CLIENT_ID", "")
        client_secret = getattr(self.config, "HOSPITAL_CLIENT_SECRET", "")
        if not url or not client_id or not client_secret:
            raise HospitalError("INTEGRACION_NO_CONFIGURADA", "Faltan la URL o las credenciales del servicio hospitalario. Configura el simulador o el ambiente entregado por el hospital.")
        if self.source == "hospital" and not url.startswith("https://"):
            raise HospitalError("INTEGRACION_NO_CONFIGURADA", "La conexión hospitalaria requiere HTTPS.")
        return url, client_id, client_secret

    def _send(self, method, path, **kwargs):
        base, _, _ = self._configuration()
        try:
            with httpx.Client(timeout=getattr(self.config, "HOSPITAL_API_TIMEOUT_SECONDS", 15), transport=self.transport, follow_redirects=False) as client:
                return client.request(method, base + path, **kwargs)
        except (httpx.HTTPError, OSError):
            raise HospitalError("SERVICIO_NO_DISPONIBLE", ERROR_MESSAGES["SERVICIO_NO_DISPONIBLE"]) from None

    @staticmethod
    def _json(response):
        try:
            body = response.json()
            return body if isinstance(body, dict) else {}
        except ValueError:
            return {}

    @staticmethod
    def _error(response, request_id):
        body = HospitalClient._json(response)
        code = str(body.get("codigo", "ERROR_SERVICIO"))[:80]
        # An unknown upstream message may expose internals; do not echo it.
        message = ERROR_MESSAGES.get(code, "No pudimos completar la consulta. Comunica el código de rastreo a soporte.")
        rastreo = str(body.get("rastreo") or request_id)[:100]
        raw_retry = response.headers.get("Retry-After", "")
        retry = min(int(raw_retry), 86400) if raw_retry.isdigit() else None
        status = response.status_code if 400 <= response.status_code < 600 else 502
        return HospitalError(code, message, status, rastreo, retry)

    def _token(self, force=False):
        with self._lock:
            if not force and self._client_token and time.monotonic() < self._token_expires:
                return self._client_token
            _, client_id, secret = self._configuration()
            response = self._send("POST", "/oauth/token", data={"grant_type": "client_credentials", "client_id": client_id, "client_secret": secret, "scope": "portal.leer portal.citar"})
            if response.status_code != 200:
                raise self._error(response, str(uuid.uuid4()))
            payload = self._json(response)
            token, lifetime = payload.get("access_token"), payload.get("expires_in")
            if not isinstance(token, str) or not token or not isinstance(lifetime, int) or lifetime <= 0 or str(payload.get("token_type", "")).lower() != "bearer":
                raise HospitalError("RESPUESTA_INVALIDA", "El servicio devolvió una autorización incompleta.", 502)
            self._client_token = token
            self._token_expires = time.monotonic() + max(lifetime - 30, 1)
            return token

    def request(self, method: str, path: str, *, patient_token=None, user_ip=None, json=None):
        for attempt in range(2):
            request_id = str(uuid.uuid4())
            headers = {"Authorization": "Bearer " + self._token(force=attempt == 1), "X-Request-Id": request_id}
            if patient_token:
                headers["X-Paciente-Token"] = patient_token
            if user_ip:
                headers["X-Usuario-IP"] = user_ip
            started = time.monotonic()
            try:
                response = self._send(method, path, headers=headers, json=json)
            except HospitalError:
                logger.warning("hospital_request request_id=%s path=%s status=unavailable elapsed_ms=%d", request_id, path, int((time.monotonic() - started) * 1000))
                raise
            logger.info("hospital_request request_id=%s path=%s status=%s elapsed_ms=%d", request_id, path, response.status_code, int((time.monotonic() - started) * 1000))
            body = self._json(response)
            if response.status_code == 401 and body.get("codigo") == "NO_AUTORIZADO" and attempt == 0:
                continue  # Contract permits one client-token renewal, no retry loop.
            if not response.is_success:
                raise self._error(response, request_id)
            if not body:
                raise HospitalError("RESPUESTA_INVALIDA", "El servicio devolvió una respuesta incompleta.", 502, request_id)
            return body
        raise HospitalError("NO_AUTORIZADO", ERROR_MESSAGES["NO_AUTORIZADO"], 503)

    def limit_identification(self, user_ip):
        now = time.monotonic()
        with self._lock:
            # Sweep all buckets so unrelated clients do not retain expired IPs.
            for key in list(self._attempts):
                bucket = self._attempts[key]
                while bucket and bucket[0] <= now - 3600:
                    bucket.popleft()
                if not bucket:
                    del self._attempts[key]
            bucket = self._attempts[user_ip]
            if len(bucket) >= 20:
                raise HospitalError("DEMASIADAS_SOLICITUDES", ERROR_MESSAGES["DEMASIADAS_SOLICITUDES"], 429, retry_after=max(1, int(3600 - (now - bucket[0]))))
            bucket.append(now)

    def forget(self, session_id):
        with self._lock:
            self._identities.pop(str(session_id), None)

    def identity(self, session_id, required=False):
        now = datetime.now(timezone.utc)
        with self._lock:
            for key in list(self._identities):
                if self._identities[key].expires_at <= now:
                    del self._identities[key]
            identity = self._identities.get(str(session_id))
        if required and not identity:
            raise HospitalError("SESION_PACIENTE_INVALIDA", ERROR_MESSAGES["SESION_PACIENTE_INVALIDA"], 401)
        return identity

    def identify(self, session_id, document: str, birthday: str, user_ip: str):
        self.limit_identification(user_ip)
        # Re-identifying cannot accidentally leave another patient's previous session active.
        self.forget(session_id)
        payload = self.request("POST", "/pacientes/identificacion", user_ip=user_ip, json={"tipo_documento": "DNI", "numero_documento": document, "fecha_nacimiento": birthday})
        token, seconds, patient = payload.get("paciente_token"), payload.get("expira_en"), payload.get("paciente")
        if not isinstance(token, str) or not token or not isinstance(seconds, int) or seconds <= 0 or not isinstance(patient, dict) or not isinstance(patient.get("nombre_enmascarado"), str):
            raise HospitalError("RESPUESTA_INVALIDA", "La identificación devuelta por el hospital está incompleta.", 502)
        identity = PatientIdentity(token, datetime.now(timezone.utc) + timedelta(seconds=seconds), {"nombre_enmascarado": patient["nombre_enmascarado"], "edad": patient.get("edad")})
        with self._lock:
            self._identities[str(session_id)] = identity
        return identity

    def patient_request(self, session_id, path):
        identity = self.identity(session_id, required=True)
        try:
            return self.request("GET", path, patient_token=identity.token)
        except HospitalError as exc:
            if exc.detail["code"] == "SESION_PACIENTE_INVALIDA":
                self.forget(session_id)
            raise

    def eligibility(self, session_id, refresh=False):
        identity = self.identity(session_id, required=True)
        if identity.eligibility is None or refresh:
            raw = self.patient_request(session_id, "/elegibilidad")
            required = ("elegible", "motivos", "condicion", "sis", "referencias", "especialidades", "proxima_reserva_desde")
            if any(key not in raw for key in required) or not isinstance(raw["elegible"], bool) or not isinstance(raw["sis"], dict) or any(not isinstance(raw[key], list) for key in ("motivos", "referencias", "especialidades")):
                raise HospitalError("RESPUESTA_INVALIDA", "La evaluación enviada por el hospital está incompleta.", 502)
            # Allow forward-compatible values, but never pass undocumented fields or secrets to a browser.
            identity.eligibility = {key: raw[key] for key in required}
        return self.evaluate_references(identity.eligibility)

    def evaluate_references(self, eligibility: dict):
        out = dict(eligibility)
        configured_days = getattr(self.config, "REFERENCE_MAX_AGE_DAYS", None)
        reasons = [{"code": code, "message": REASON_MESSAGES.get(code, "El hospital indica una restricción que requiere revisión en Admisión.")} for code in out["motivos"]]
        allowed_ids = set()
        today = datetime.now(LIMA).date()
        references = []
        for ref in out["referencias"]:
            if not isinstance(ref, dict):
                continue
            clean = {key: ref.get(key) for key in ("referencia_id", "numero", "estado", "fecha_envio", "establecimiento_origen", "especialidad_destino", "especialidades_coincidentes")}
            valid = False
            if configured_days is not None:
                try:
                    age = (today - date.fromisoformat(str(ref.get("fecha_envio")))).days
                    valid = 0 <= age <= configured_days and ref.get("estado") in {"ACEPTADA", "RECIBIDA"}
                except (TypeError, ValueError):
                    valid = False
            clean["validity"] = "policy_pending" if configured_days is None else ("valid" if valid else "not_valid")
            if valid and isinstance(ref.get("referencia_id"), str):
                allowed_ids.add(ref["referencia_id"])
            references.append(clean)
        specialties, allowed = [], []
        for specialty in out["especialidades"]:
            if not isinstance(specialty, dict):
                continue
            clean = {key: specialty.get(key) for key in ("especialidad_id", "nombre", "referencias")}
            specialties.append(clean)
            valid_refs = [ref for ref in (specialty.get("referencias") or []) if ref in allowed_ids and any(r["referencia_id"] == ref and specialty.get("especialidad_id") in (r.get("especialidades_coincidentes") or []) for r in references)]
            if valid_refs:
                allowed.append({**clean, "referencias": valid_refs})
        out.update(referencias=references, especialidades=specialties, reference_policy_pending=configured_days is None, reference_max_age_days=configured_days, reason_messages=reasons, specialties_allowed=allowed)
        out["sis"] = {key: out["sis"].get(key) for key in ("estado", "verificado_en")}
        out["reserve_ready"] = bool(out["elegible"] and not out["motivos"] and out["sis"].get("estado") == "VIGENTE" and out["condicion"] in {"CONTINUADOR", "REINGRESANTE"} and allowed and configured_days is not None)
        if configured_days is None:
            reasons.append({"code": "REFERENCE_POLICY_PENDING", "message": "Admisión aún debe confirmar la vigencia de las referencias. La reserva permanece bloqueada hasta configurar esa regla."})
        elif out["elegible"] and not allowed:
            reasons.append({"code": "NO_VALID_REFERENCES", "message": "No hay referencias vigentes para las especialidades disponibles según la regla configurada por Admisión."})
        return out

    def public_identity(self, session_id):
        identity = self.identity(session_id)
        if not identity:
            return {"identified": False}
        return {"identified": True, "paciente": identity.patient, "expires_at": identity.expires_at.isoformat(), "seconds_remaining": max(0, int((identity.expires_at - datetime.now(timezone.utc)).total_seconds()))}


hospital_client = HospitalClient()
