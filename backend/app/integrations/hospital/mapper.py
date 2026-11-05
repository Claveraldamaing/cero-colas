"""Pure normalization of upstream hospital payloads into portal-safe data."""
from datetime import datetime

from .errors import HospitalError
from .schemas import APPOINTMENT_FIELDS, ELIGIBILITY_REQUIRED_FIELDS, LIMA, PATIENT_FIELDS, POLICY_FIELDS


def identity_payload(payload: dict):
    token, seconds, patient = payload.get("paciente_token"), payload.get("expira_en"), payload.get("paciente")
    if not isinstance(token, str) or not token or not isinstance(seconds, int) or seconds <= 0 or not isinstance(patient, dict) or not isinstance(patient.get("nombre_enmascarado"), str):
        raise HospitalError("RESPUESTA_INVALIDA", "La identificación devuelta por el hospital está incompleta.", 502)
    return token, seconds, {key: patient.get(key) for key in PATIENT_FIELDS}


def eligibility_payload(raw: dict):
    if any(key not in raw for key in ELIGIBILITY_REQUIRED_FIELDS) or not isinstance(raw["elegible"], bool) or not isinstance(raw["sis"], dict) or any(not isinstance(raw[key], list) for key in ("motivos", "referencias", "especialidades")):
        raise HospitalError("RESPUESTA_INVALIDA", "La evaluación enviada por el hospital está incompleta.", 502)
    # Allow forward-compatible values, but never pass undocumented fields or secrets to a browser.
    return {key: raw[key] for key in ELIGIBILITY_REQUIRED_FIELDS}


def policies_payload(payload: dict):
    return {key: payload.get(key) for key in POLICY_FIELDS}


def next_appointment(payload: dict, now: datetime):
    appointments = payload.get("datos")
    if not isinstance(appointments, list):
        raise HospitalError("RESPUESTA_INVALIDA", "La lista de citas enviada por el hospital está incompleta.", 502)
    candidates = []
    for appointment in appointments:
        if not isinstance(appointment, dict) or appointment.get("estado") in {"ANULADA", "ATENDIDA", "NO_ASISTIO"}:
            continue
        try:
            starts = datetime.fromisoformat(f"{appointment['fecha']}T{appointment['hora_inicio']}").replace(tzinfo=LIMA)
        except (KeyError, ValueError, TypeError):
            continue
        if starts >= now:
            candidates.append((starts, appointment))
    if not candidates:
        return None
    appointment = min(candidates, key=lambda item: item[0])[1]
    return {key: appointment.get(key) for key in APPOINTMENT_FIELDS}
