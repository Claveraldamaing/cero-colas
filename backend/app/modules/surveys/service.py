"""Local usage tracking and satisfaction survey business rules."""
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from .models import P1Survey, P1UsageEvent
from .schemas import SurveyInput


def survey_scale():
    return {"min": getattr(settings, "SURVEY_MIN_SCORE", 1), "max": getattr(settings, "SURVEY_MAX_SCORE", 5), "prototype": True}


def mark_usage(db: Session, session):
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


def feedback_status(db: Session, session):
    usage = db.query(P1UsageEvent).filter(P1UsageEvent.session_id == session.id, P1UsageEvent.user_id == session.user_id).order_by(P1UsageEvent.created_at.desc()).first()
    survey = db.query(P1Survey).filter(P1Survey.usage_event_id == usage.id, P1Survey.user_id == session.user_id).first() if usage else None
    return {"eligible": bool(usage and not survey), "submitted": bool(survey), "event_id": usage.id if usage else None, "scale": survey_scale()}


def submit_survey(db: Session, session, data: SurveyInput):
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


def summary(db: Session, scale: dict):
    survey_query = db.query(P1Survey).filter(P1Survey.scale_min == scale["min"], P1Survey.scale_max == scale["max"])
    responses, average_ease, average_satisfaction = survey_query.with_entities(func.count(P1Survey.id), func.avg(P1Survey.ease_score), func.avg(P1Survey.satisfaction_score)).one()
    counts = dict(survey_query.with_entities(P1Survey.satisfaction_score, func.count(P1Survey.id)).group_by(P1Survey.satisfaction_score).all())
    return {
        "responses": responses,
        "average_ease": round(float(average_ease), 2) if average_ease is not None else None,
        "average_satisfaction": round(float(average_satisfaction), 2) if average_satisfaction is not None else None,
        "distribution": [{"score": score, "count": counts.get(score, 0)} for score in range(scale["min"], scale["max"] + 1)],
        "scale": scale,
        "source": "local_database",
    }
