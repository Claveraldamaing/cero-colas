"""P1 identity, eligibility, dashboards and local satisfaction surveys."""
import re
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.p1.auth import current_session, current_user, require_admin, require_csrf, verify_challenge
from app.p1.auth_models import P1Session, P1User
from app.p1.hospital import HospitalError, LIMA, hospital_client
from app.p1.portal_models import P1Survey, P1UsageEvent

router = APIRouter(prefix="/portal", tags=["P1 · Portal"])

PROTOTYPE_NOTICE = (
    "Prototipo académico conectado al simulador oficial del contrato apicitas. "
    "Usa únicamente datos de prueba. Los resultados del simulador no acreditan identidad, SIS ni citas reales. "
    "El DNI y la fecha de nacimiento se transmiten para la identificación y no se guardan en la base local. "
    "La sesión hospitalaria y sus tokens permanecen en memoria del servidor hasta su vencimiento o cierre. "
    "La política definitiva debe ser aprobada por el hospital antes de utilizar datos reales."
)


def fail(exc: HospitalError):
    headers = {"Retry-After": str(exc.detail["retry_after"])} if "retry_after" in exc.detail else None
    raise HTTPException(status_code=exc.status, detail=exc.detail, headers=headers)


def survey_scale():
    return {"min": getattr(settings, "SURVEY_MIN_SCORE", 1), "max": getattr(settings, "SURVEY_MAX_SCORE", 5), "prototype": True}


class IdentificationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    numero_documento: str = Field(pattern=r"^[0-9]{8}$")
    fecha_nacimiento: date
    consent: bool
    challenge_id: str = Field(min_length=1, max_length=100)
    challenge_answer: str = Field(min_length=1, max_length=100)

    @field_validator("fecha_nacimiento")
    @classmethod
    def birthday_not_in_future(cls, value):
        if value > datetime.now(LIMA).date():
            raise ValueError("La fecha de nacimiento no puede estar en el futuro.")
        return value


class SurveyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ease_score: int = Field(strict=True)
    satisfaction_score: int = Field(strict=True)
    comment: str | None = Field(default=None, max_length=1000)

    @field_validator("comment")
    @classmethod
    def trim_comment(cls, value):
        if value:
            value = value.strip()
            # Comments are intentionally optional and must not collect identifiers.
            if re.search(r"(?<!\d)\d{8}(?!\d)", value) or re.search(r"\b\d{4}-\d{2}-\d{2}\b", value):
                raise ValueError("No incluyas DNI ni fechas de nacimiento en el comentario.")
            return value or None
        return None


def privacy_config():
    approved = bool(getattr(settings, "HOSPITAL_PRIVACY_POLICY_APPROVED", False))
    text = getattr(settings, "HOSPITAL_PRIVACY_POLICY_TEXT", "").strip()
    return approved and bool(text), text


@router.get("/policies")
def policies(user: P1User = Depends(current_user)):
    approved, text = privacy_config()
    result = {"source": hospital_client.source, "privacy_notice": text if approved and hospital_client.source == "hospital" else PROTOTYPE_NOTICE, "privacy_approved": approved, "reference_max_age_days": getattr(settings, "REFERENCE_MAX_AGE_DAYS", None), "survey_scale": survey_scale(), "policies": None, "integration_error": None}
    try:
        payload = hospital_client.request("GET", "/politicas")
        result["policies"] = {key: payload.get(key) for key in ("ventana", "reservas_por_dia", "dias_entre_reservas", "horas_minimas_para_anular", "intentos_identificacion", "sesion_paciente_segundos")}
    except HospitalError as exc:
        result["integration_error"] = exc.detail
    return result


@router.post("/identify")
def identify(data: IdentificationInput, request: Request, session: P1Session = Depends(require_csrf), db: Session = Depends(get_db)):
    if not data.consent:
        raise HTTPException(422, detail={"code": "CONSENT_REQUIRED", "message": "Debes aceptar el aviso de privacidad antes de enviar tu identificación."})
    approved, _ = privacy_config()
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


def mark_usage(db, session):
    existing = db.query(P1UsageEvent).filter(P1UsageEvent.session_id == session.id, P1UsageEvent.event_type == "eligibility_consulted").first()
    if existing:
        return existing
    usage = P1UsageEvent(user_id=session.user_id, session_id=session.id, event_type="eligibility_consulted")
    db.add(usage)
    try:
        db.commit()
        db.refresh(usage)
        return usage
    except IntegrityError:
        db.rollback()
        return db.query(P1UsageEvent).filter(P1UsageEvent.session_id == session.id, P1UsageEvent.event_type == "eligibility_consulted").one()


@router.get("/eligibility")
def eligibility(refresh: bool = Query(default=False), session: P1Session = Depends(current_session), db: Session = Depends(get_db)):
    try:
        result = hospital_client.eligibility(session.id, refresh=refresh)
    except HospitalError as exc:
        fail(exc)
    mark_usage(db, session)
    return {"source": hospital_client.source, "identity": hospital_client.public_identity(session.id), "eligibility": result}


@router.delete("/identity")
def clear_identity(session: P1Session = Depends(require_csrf)):
    hospital_client.forget(session.id)
    return {"identified": False}


def feedback_status(db, session):
    usage = db.query(P1UsageEvent).filter(P1UsageEvent.session_id == session.id, P1UsageEvent.user_id == session.user_id).order_by(P1UsageEvent.created_at.desc()).first()
    survey = db.query(P1Survey).filter(P1Survey.usage_event_id == usage.id, P1Survey.user_id == session.user_id).first() if usage else None
    return {"eligible": bool(usage and not survey), "submitted": bool(survey), "event_id": usage.id if usage else None, "scale": survey_scale()}


@router.get("/surveys/status")
def survey_status(session: P1Session = Depends(current_session), db: Session = Depends(get_db)):
    return feedback_status(db, session)


@router.post("/surveys", status_code=201)
def submit_survey(data: SurveyInput, session: P1Session = Depends(require_csrf), db: Session = Depends(get_db)):
    scale = survey_scale()
    if not all(scale["min"] <= score <= scale["max"] for score in (data.ease_score, data.satisfaction_score)):
        raise HTTPException(422, detail={"code": "INVALID_SURVEY_SCORE", "message": f"Selecciona un puntaje entre {scale['min']} y {scale['max']} para ambas preguntas."})
    status = feedback_status(db, session)
    if status["submitted"]:
        raise HTTPException(409, detail={"code": "SURVEY_ALREADY_SUBMITTED", "message": "Ya respondiste la encuesta de esta sesión de uso."})
    if not status["eligible"]:
        raise HTTPException(409, detail={"code": "SURVEY_USAGE_REQUIRED", "message": "La encuesta estará disponible después de consultar tu elegibilidad."})
    survey = P1Survey(user_id=session.user_id, usage_event_id=status["event_id"], ease_score=data.ease_score, satisfaction_score=data.satisfaction_score, comment=data.comment, scale_min=scale["min"], scale_max=scale["max"])
    db.add(survey)
    try:
        db.commit()
        db.refresh(survey)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, detail={"code": "SURVEY_ALREADY_SUBMITTED", "message": "Ya respondiste la encuesta de esta sesión de uso."}) from None
    return {"id": survey.id, "created_at": survey.created_at, "message": "Gracias. Tu respuesta fue guardada."}


def next_appointment(session_id):
    payload = hospital_client.patient_request(session_id, "/citas")
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
        if starts >= datetime.now(LIMA):
            candidates.append((starts, appointment))
    if not candidates:
        return None
    appointment = min(candidates, key=lambda item: item[0])[1]
    return {key: appointment.get(key) for key in ("codigo_cita", "estado", "canal", "fecha", "hora_inicio", "hora_fin", "especialidad", "consultorio", "medico", "financiamiento", "indicaciones", "anulable_hasta")}


@router.get("/dashboard")
def patient_dashboard(session: P1Session = Depends(current_session), db: Session = Depends(get_db)):
    identity = hospital_client.public_identity(session.id)
    result = {"source": hospital_client.source, "identity": identity, "eligibility": None, "next_appointment": None, "appointments_status": "identity_required", "notifications": {"integrated": False, "items": []}, "survey": feedback_status(db, session), "integration_errors": []}
    if not identity["identified"]:
        return result
    try:
        result["eligibility"] = hospital_client.eligibility(session.id)
        mark_usage(db, session)
        result["survey"] = feedback_status(db, session)
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


@router.get("/admin/dashboard")
def admin_dashboard(user: P1User = Depends(require_admin), db: Session = Depends(get_db)):
    scale = survey_scale()
    survey_query = db.query(P1Survey).filter(P1Survey.scale_min == scale["min"], P1Survey.scale_max == scale["max"])
    responses, average_ease, average_satisfaction = survey_query.with_entities(func.count(P1Survey.id), func.avg(P1Survey.ease_score), func.avg(P1Survey.satisfaction_score)).one()
    counts = dict(survey_query.with_entities(P1Survey.satisfaction_score, func.count(P1Survey.id)).group_by(P1Survey.satisfaction_score).all())
    total_users = db.query(func.count(P1User.id)).scalar()
    active_users = db.query(func.count(P1User.id)).filter(P1User.active.is_(True)).scalar()
    result = {
        "source": hospital_client.source,
        "users": {"total": total_users, "active": active_users, "inactive": total_users - active_users, "admins": db.query(func.count(P1User.id)).filter(P1User.role == "ADMIN").scalar()},
        "metrics": {"reservations": None, "cancellations": None, "tickets": None, "chatbot": None},
        "survey": {"responses": responses, "average_ease": round(float(average_ease), 2) if average_ease is not None else None, "average_satisfaction": round(float(average_satisfaction), 2) if average_satisfaction is not None else None, "distribution": [{"score": score, "count": counts.get(score, 0)} for score in range(scale["min"], scale["max"] + 1)], "scale": scale, "source": "local_database"},
        "service": {"available": False, "canal_abierto": None, "verificacion_sis": None, "hora_servidor": None},
        "pending_integrations": ["Reservas gestionadas: requiere agregados del módulo P2.", "Anulaciones y notificaciones: requieren integración del módulo P3.", "Tickets y uso de chatbot: requieren integración del módulo P4."],
    }
    try:
        health = hospital_client.request("GET", "/salud")
        if not isinstance(health.get("canal_abierto"), bool):
            raise HospitalError("RESPUESTA_INVALIDA", "El estado del canal hospitalario está incompleto.", 502)
        result["service"] = {"available": True, **{key: health.get(key) for key in ("canal_abierto", "verificacion_sis", "hora_servidor")}}
    except HospitalError as exc:
        result["service"]["error"] = exc.detail
    return result
