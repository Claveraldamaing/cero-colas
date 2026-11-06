"""Reference-validity policy applied to hospital eligibility responses."""
from datetime import date, datetime
from urllib.parse import urlparse

from .errors import REASON_MESSAGES
from .schemas import LIMA


def evaluate_references(eligibility: dict, config):
    out = dict(eligibility)
    configured_days = getattr(config, "REFERENCE_MAX_AGE_DAYS", None)
    simulator_url = urlparse(getattr(config, "HOSPITAL_API_BASE_URL", ""))
    local_simulator = (
        getattr(config, "HOSPITAL_MODE", None) == "simulator"
        and simulator_url.hostname in {"localhost", "127.0.0.1", "::1"}
    )
    simulator_policy_override = configured_days is None and local_simulator
    reasons = [{"code": code, "message": REASON_MESSAGES.get(code, "El hospital indica una restricción que requiere revisión en Admisión.")} for code in out["motivos"]]
    allowed_ids = set()
    today = datetime.now(LIMA).date()
    references = []
    for ref in out["referencias"]:
        if not isinstance(ref, dict):
            continue
        clean = {key: ref.get(key) for key in ("referencia_id", "numero", "estado", "fecha_envio", "establecimiento_origen", "especialidad_destino", "especialidades_coincidentes")}
        valid = False
        if configured_days is not None or simulator_policy_override:
            try:
                age = (today - date.fromisoformat(str(ref.get("fecha_envio")))).days
                valid = (
                    age >= 0
                    and (simulator_policy_override or age <= configured_days)
                    and ref.get("estado") in {"ACEPTADA", "RECIBIDA"}
                )
            except (TypeError, ValueError):
                valid = False
        clean["validity"] = (
            "simulator_only" if simulator_policy_override and valid
            else "policy_pending" if configured_days is None
            else "valid" if valid
            else "not_valid"
        )
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
    out.update(
        referencias=references,
        especialidades=specialties,
        reference_policy_pending=configured_days is None,
        reference_max_age_days=configured_days,
        reservation_simulation=local_simulator,
        reason_messages=reasons,
        specialties_allowed=allowed,
    )
    out["sis"] = {key: out["sis"].get(key) for key in ("estado", "verificado_en")}
    out["reserve_ready"] = bool(out["elegible"] and not out["motivos"] and out["sis"].get("estado") == "VIGENTE" and out["condicion"] in {"CONTINUADOR", "REINGRESANTE"} and allowed and (configured_days is not None or simulator_policy_override))
    if configured_days is None:
        message = (
            "Modo simulador local: se permite probar la reserva sin aplicar todavía la vigencia por días. No es una reserva real."
            if simulator_policy_override
            else "Admisión aún debe confirmar la vigencia de las referencias. La reserva permanece bloqueada hasta configurar esa regla."
        )
        reasons.append({"code": "REFERENCE_POLICY_PENDING", "message": message})
    elif out["elegible"] and not allowed:
        reasons.append({"code": "NO_VALID_REFERENCES", "message": "No hay referencias vigentes para las especialidades disponibles según la regla configurada por Admisión."})
    return out
