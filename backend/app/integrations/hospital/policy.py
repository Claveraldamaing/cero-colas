"""Reference-validity policy applied to hospital eligibility responses."""
from datetime import date, datetime

from .errors import REASON_MESSAGES
from .schemas import LIMA


def evaluate_references(eligibility: dict, config):
    out = dict(eligibility)
    configured_days = getattr(config, "REFERENCE_MAX_AGE_DAYS", None)
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
