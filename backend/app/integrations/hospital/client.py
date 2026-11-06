"""Backend-only adapter for the supplied apicitas contract.

Credentials and patient sessions live exclusively in this process. Run one worker
until an approved shared, ephemeral session service is introduced. No mock fallback.
"""
import logging
import threading
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.database import SessionLocal
from app.modules.reservations.models import APIAudit
from . import mapper, policy
from .errors import ERROR_MESSAGES, HospitalError
from .schemas import PatientIdentity

logger = logging.getLogger("cerocolas.hospital")


def persist_api_audit(entry):
    with SessionLocal() as db:
        db.add(APIAudit(**entry))
        db.commit()


class HospitalClient:
    def __init__(self, config=settings, transport=None, audit_writer=None):
        self.config = config
        self.transport = transport  # Explicit test injection, never a runtime fallback.
        self.audit_writer = audit_writer
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

    def _audit(self, request_id, method, path, status, error_code, elapsed_ms, retry_number):
        if self.audit_writer is None:
            return
        try:
            self.audit_writer({
                "request_id": request_id,
                "metodo_http": method[:10],
                "endpoint": path[:255],
                "estado_http": status,
                "codigo_error": error_code[:100] if error_code else None,
                "rastreo": request_id,
                "tiempo_respuesta_ms": elapsed_ms,
                "numero_reintento": retry_number,
                "fecha_hora": datetime.now(timezone.utc),
            })
        except SQLAlchemyError as error:
            logger.error(
                "hospital_audit_write_failed request_id=%s error_type=%s",
                request_id,
                type(error).__name__,
            )

    def _send(self, method, path, *, audit_request_id=None, retry_number=0, **kwargs):
        base, _, _ = self._configuration()
        request_id = audit_request_id or str(uuid.uuid4())
        started = time.monotonic()
        try:
            with httpx.Client(timeout=getattr(self.config, "HOSPITAL_API_TIMEOUT_SECONDS", 15), transport=self.transport, follow_redirects=False) as client:
                response = client.request(method, base + path, **kwargs)
        except (httpx.HTTPError, OSError):
            elapsed_ms = int((time.monotonic() - started) * 1000)
            self._audit(request_id, method, path, None, "SERVICIO_NO_DISPONIBLE", elapsed_ms, retry_number)
            logger.warning(
                "hospital_request request_id=%s path=%s status=unavailable elapsed_ms=%d",
                request_id,
                path,
                elapsed_ms,
            )
            raise HospitalError("SERVICIO_NO_DISPONIBLE", ERROR_MESSAGES["SERVICIO_NO_DISPONIBLE"]) from None
        error_code = None
        if not response.is_success:
            error_code = str(self._json(response).get("codigo", "ERROR_SERVICIO"))
        self._audit(
            request_id,
            method,
            path,
            response.status_code,
            error_code,
            int((time.monotonic() - started) * 1000),
            retry_number,
        )
        return response

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
            request_id = str(uuid.uuid4())
            response = self._send("POST", "/oauth/token", audit_request_id=request_id, retry_number=int(force), data={"grant_type": "client_credentials", "client_id": client_id, "client_secret": secret, "scope": "portal.leer portal.citar"})
            if response.status_code != 200:
                raise self._error(response, request_id)
            payload = self._json(response)
            token, lifetime = payload.get("access_token"), payload.get("expires_in")
            if not isinstance(token, str) or not token or not isinstance(lifetime, int) or lifetime <= 0 or str(payload.get("token_type", "")).lower() != "bearer":
                raise HospitalError("RESPUESTA_INVALIDA", "El servicio devolvió una autorización incompleta.", 502)
            self._client_token = token
            self._token_expires = time.monotonic() + max(lifetime - 30, 1)
            return token

    def request(self, method: str, path: str, *, patient_token=None, user_ip=None, json=None, params=None, idempotency_key=None):
        for attempt in range(2):
            request_id = str(uuid.uuid4())
            headers = {"Authorization": "Bearer " + self._token(force=attempt == 1), "X-Request-Id": request_id}
            if patient_token:
                headers["X-Paciente-Token"] = patient_token
            if user_ip:
                headers["X-Usuario-IP"] = user_ip
            if idempotency_key:
                headers["Idempotency-Key"] = idempotency_key
            started = time.monotonic()
            try:
                response = self._send(
                    method,
                    path,
                    audit_request_id=request_id,
                    retry_number=attempt,
                    headers=headers,
                    json=json,
                    params=params,
                )
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
        token, seconds, patient = mapper.identity_payload(payload)
        identity = PatientIdentity(token, datetime.now(timezone.utc) + timedelta(seconds=seconds), patient)
        with self._lock:
            self._identities[str(session_id)] = identity
        return identity

    def patient_request(self, session_id, path, *, method="GET", params=None, json=None, idempotency_key=None):
        identity = self.identity(session_id, required=True)
        try:
            return self.request(
                method,
                path,
                patient_token=identity.token,
                params=params,
                json=json,
                idempotency_key=idempotency_key,
            )
        except HospitalError as exc:
            if exc.detail["code"] == "SESION_PACIENTE_INVALIDA":
                self.forget(session_id)
            raise

    def eligibility(self, session_id, refresh=False):
        identity = self.identity(session_id, required=True)
        if identity.eligibility is None or refresh:
            raw = self.patient_request(session_id, "/elegibilidad")
            identity.eligibility = mapper.eligibility_payload(raw)
        return self.evaluate_references(identity.eligibility)

    def evaluate_references(self, eligibility: dict):
        return policy.evaluate_references(eligibility, self.config)

    def public_identity(self, session_id):
        identity = self.identity(session_id)
        if not identity:
            return {"identified": False}
        return {"identified": True, "paciente": identity.patient, "expires_at": identity.expires_at.isoformat(), "seconds_remaining": max(0, int((identity.expires_at - datetime.now(timezone.utc)).total_seconds()))}


hospital_client = HospitalClient(audit_writer=persist_api_audit)
