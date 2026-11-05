"""Portal identity, eligibility and patient dashboard orchestration."""
from datetime import datetime

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.integrations.hospital import HospitalError, LIMA, hospital_client
from app.integrations.hospital import mapper as hospital_mapper
from app.modules.auth.models import P1Session
from app.modules.auth.service import verify_challenge
from app.modules.surveys import service as surveys_service
from . import policy
from .schemas import IdentificationInput


def fail(exc: HospitalError):
    headers = {"Retry-After": str(exc.detail["retry_after"])} if "retry_after" in exc.detail else None
    raise HTTPException(status_code=exc.status, detail=exc.detail, headers=headers)


def policies():
    approved, text = policy.privacy_config()
    result = {"source": hospital_client.source, "privacy_notice": text if approved and hospital_client.source == "hospital" else policy.PROTOTYPE_NOTICE, "privacy_approved": approved, "reference_max_age_days": getattr(settings, "REFERENCE_MAX_AGE_DAYS", None), "survey_scale": surveys_service.survey_scale(), "policies": None, "integration_error": None}
    try:
        payload = hospital_client.request("GET", "/politicas")
        result["policies"] = hospital_mapper.policies_payload(payload)
    except HospitalError as exc:
        result["integration_error"] = exc.detail
    return result


def identify(session: P1Session, request: Request, data: IdentificationInput, db: Session):
    if not data.consent:
        raise HTTPException(422, detail={"code": "CONSENT_REQUIRED", "message": "Debes aceptar el aviso de privacidad antes de enviar tu identificación."})
    approved, _ = policy.privacy_config()
    if hospital_client.source == "hospital" and not approved:
        raise HTTPException(503, detail={"code": "PRIVACY_POLICY_PENDING", "message": "El hospital debe aprobar la política de privacidad antes de habilitar la identificación con datos reales."})
    verify_challenge(db, request, data.challenge_id, data.challenge_answer)
    # X-Forwarded-For is never trusted here; deploy Uvicorn with an explicit proxy allowlist.
    if request.client is None:
        raise HTTPException(400, detail={"code": "CLIENT_IP_REQUIRED", "message": "No fue posible determinar el origen de la solicitud."})
    try:
        hospital_client.identify(session.id, data.numero_documento, data.fecha_nacimiento.isoformat(), request.client.host)
    except HospitalError as exc:
        fail(exc)
    return {"source": hospital_client.source, "identity": hospital_client.public_identity(session.id), "eligibility": None}


def eligibility(session: P1Session, db: Session, refresh: bool):
    try:
        result = hospital_client.eligibility(session.id, refresh=refresh)
    except HospitalError as exc:
        fail(exc)
    surveys_service.mark_usage(db, session)
    return {"source": hospital_client.source, "identity": hospital_client.public_identity(session.id), "eligibility": result}


def clear_identity(session: P1Session):
    hospital_client.forget(session.id)
    return {"identified": False}


def next_appointment(session_id):
    payload = hospital_client.patient_request(session_id, "/citas")
    return hospital_mapper.next_appointment(payload, datetime.now(LIMA))


def dashboard(session: P1Session, db: Session):
    identity = hospital_client.public_identity(session.id)
    result = {"source": hospital_client.source, "identity": identity, "eligibility": None, "next_appointment": None, "appointments_status": "identity_required", "notifications": {"integrated": False, "items": []}, "survey": surveys_service.feedback_status(db, session), "integration_errors": []}
    if not identity["identified"]:
        return result
    try:
        result["eligibility"] = hospital_client.eligibility(session.id)
        surveys_service.mark_usage(db, session)
        result["survey"] = surveys_service.feedback_status(db, session)
    except HospitalError as exc:
        result["integration_errors"].append(exc.detail)
    try:
        result["next_appointment"] = next_appointment(session.id)
        result["appointments_status"] = "available"
    except HospitalError as exc:
        result["appointments_status"] = "unavailable"
        if exc.detail not in result["integration_errors"]:
            result["integration_errors"].append(exc.detail)
    result["identity"] = hospital_client.public_identity(session.id)
    if not result["identity"]["identified"]:
        result["eligibility"] = None
    return result
