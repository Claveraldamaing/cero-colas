"""Administrative account rules: listing, roles and active status."""
from sqlalchemy.orm import Session

from app.core.errors import problem
from app.modules.auth import repository, service
from app.modules.auth.models import P1User
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
