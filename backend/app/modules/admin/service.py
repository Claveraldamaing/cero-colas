"""Administrative account and portal dashboard rules."""
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.errors import problem
from app.integrations import hospital
from app.integrations.hospital import HospitalError
from app.modules.auth import repository, service
from app.modules.auth.models import P1User
from app.modules.surveys import service as surveys_service
from .schemas import AccountInput


def list_accounts(db: Session, q: str, offset: int, limit: int):
    items, total = repository.list_users(db, q, offset, limit)
    return [service.user_json(item) for item in items], total


def update_account(db: Session, actor: P1User, user_id: str, payload: AccountInput):
    # Serialize edits of active administrators so concurrent requests cannot remove all.
    admins = repository.lock_active_admins(db)
    target = repository.user_by_id(db, user_id)
    if not target:
        problem(404, "USER_NOT_FOUND", "El usuario no existe.")
    if target.id == actor.id and (payload.active is False or payload.role == "PACIENTE"):
        problem(409, "SELF_ACCOUNT_CHANGE", "No puedes desactivar tu propia cuenta ni retirar tu rol de administrador.")
    removing_admin = target.role == "ADMIN" and target.active and (payload.active is False or payload.role == "PACIENTE")
    if removing_admin and len(admins) <= 1:
        problem(409, "LAST_ADMIN", "Debe existir al menos un administrador activo.")
    old_role = target.role
    if payload.active is not None:
        target.active = payload.active
    if payload.role is not None:
        target.role = payload.role
    if not target.active or old_role != target.role:
        service.revoke_sessions(db, target.id)
    db.commit()
    return service.user_json(target)


def portal_dashboard(db: Session):
    scale = surveys_service.survey_scale()
    total_users = db.query(func.count(P1User.id)).scalar()
    active_users = db.query(func.count(P1User.id)).filter(P1User.active.is_(True)).scalar()
    result = {
        "source": hospital.hospital_client.source,
        "users": {"total": total_users, "active": active_users, "inactive": total_users - active_users, "admins": db.query(func.count(P1User.id)).filter(P1User.role == "ADMIN").scalar()},
        "metrics": {"reservations": None, "cancellations": None, "tickets": None, "chatbot": None},
        "survey": surveys_service.summary(db, scale),
        "service": {"available": False, "canal_abierto": None, "verificacion_sis": None, "hora_servidor": None},
        "pending_integrations": ["Reservas gestionadas: requiere agregados del módulo P2.", "Anulaciones y notificaciones: requieren integración del módulo P3.", "Tickets y uso de chatbot: requieren integración del módulo P4."],
    }
    try:
        health = hospital.hospital_client.request("GET", "/salud")
        if not isinstance(health.get("canal_abierto"), bool):
            raise HospitalError("RESPUESTA_INVALIDA", "El estado del canal hospitalario está incompleto.", 502)
        result["service"] = {"available": True, **{key: health.get(key) for key in ("canal_abierto", "verificacion_sis", "hora_servidor")}}
    except HospitalError as exc:
        result["service"]["error"] = exc.detail
    return result
