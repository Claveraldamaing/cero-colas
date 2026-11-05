"""HTTP routes for accounts, sessions, recovery and temporary admin user management."""
import logging
import smtplib

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import problem
from app.core.security import csrf_for_token, utcnow
from . import mail, repository, service
from .models import P1Session, P1User
from .schemas import AccountInput, ForgotInput, LoginInput, PasswordInput, ProfileInput, RegisterInput, ResetInput

router = APIRouter(prefix="/auth", tags=["P1 · Usuarios y seguridad"])
admin_router = APIRouter(prefix="/admin", tags=["P1 · Administración de usuarios"])
logger = logging.getLogger(__name__)


@router.get("/challenge")
def challenge(request: Request, response: Response, db: Session = Depends(get_db)):
    return service.issue_challenge(db, request, response)


@router.post("/register", status_code=201)
def register(payload: RegisterInput, request: Request, response: Response, db: Session = Depends(get_db)):
    user = service.register_account(db, request, payload)
    return service.create_session(db, user, response)


@router.post("/login")
def login(payload: LoginInput, request: Request, response: Response, db: Session = Depends(get_db)):
    user = service.login_account(db, request, payload)
    return service.create_session(db, user, response)


@router.get("/me")
def me(request: Request, response: Response, user: P1User = Depends(service.current_user)):
    response.headers["Cache-Control"] = "no-store"
    return {"user": service.user_json(user), "csrf_token": csrf_for_token(request.cookies[service.COOKIE_NAME])}


@router.post("/logout")
def logout(response: Response, session: P1Session = Depends(service.require_csrf), db: Session = Depends(get_db)):
    session.revoked_at = utcnow()
    db.commit()
    service.forget_hospital_sessions([session.id])
    response.delete_cookie(service.COOKIE_NAME, path="/", secure=service.truthy(service.option("COOKIE_SECURE", False)), httponly=True, samesite="lax")
    response.headers["Cache-Control"] = "no-store"
    return {"message": "Sesión cerrada."}


@router.patch("/profile", dependencies=[Depends(service.require_csrf)])
def update_profile(payload: ProfileInput, request: Request, response: Response, user: P1User = Depends(service.current_user), db: Session = Depends(get_db)):
    if payload.name is not None:
        user.name = payload.name
    if payload.preferences is not None:
        user.preferences = {**(user.preferences or service.default_preferences()), **payload.preferences.model_dump(exclude_unset=True)}
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return {"user": service.user_json(user), "csrf_token": csrf_for_token(request.cookies[service.COOKIE_NAME])}


@router.post("/change-password", dependencies=[Depends(service.require_csrf)])
def change_password(payload: PasswordInput, request: Request, response: Response, user: P1User = Depends(service.current_user), db: Session = Depends(get_db)):
    service.change_password(db, request, user, payload)
    return {**service.create_session(db, user, response), "message": "Contraseña actualizada. Las sesiones anteriores se cerraron."}


@router.post("/forgot-password")
def forgot_password(payload: ForgotInput, request: Request, db: Session = Depends(get_db)):
    service.check_origin(request)
    service.throttle(db, request, "forgot_password", count=5)
    service.verify_challenge(db, request, payload.challenge_id, payload.challenge_answer)
    if not service.option("SMTP_HOST", "") and not mail.local_mail_enabled():
        problem(503, "RECOVERY_UNAVAILABLE", "La recuperación por correo aún no está configurada. Contacta al administrador.")
    user = repository.active_user_by_email(db, payload.email)
    if user:
        token, recovery = service.start_recovery(db, user)
        try:
            mail.deliver_recovery(user.email, token)
        except (OSError, RuntimeError, smtplib.SMTPException):
            recovery.used_at = utcnow()
            db.commit()
            logger.error("Password recovery delivery failed; inspect mail configuration.")
    return {"message": "Si existe una cuenta activa con ese correo, se ha solicitado un enlace de recuperación.", "delivery_mode": "smtp" if service.option("SMTP_HOST", "") else "local_mailbox"}


@router.post("/reset-password")
def reset_password(payload: ResetInput, request: Request, response: Response, db: Session = Depends(get_db)):
    service.reset_password(db, request, payload)
    response.delete_cookie(service.COOKIE_NAME, path="/")
    return {"message": "Contraseña restablecida. Ya puedes iniciar sesión con tu nueva contraseña."}


@admin_router.get("/users")
def list_users(response: Response, user: P1User = Depends(service.require_admin), db: Session = Depends(get_db), offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), q: str = Query("", max_length=120)):
    items, total = repository.list_users(db, q, offset, limit)
    response.headers["Cache-Control"] = "no-store"
    return {"items": [service.user_json(item) for item in items], "total": total, "offset": offset, "limit": limit}


@admin_router.patch("/users/{user_id}", dependencies=[Depends(service.require_csrf)])
def update_account(user_id: str, payload: AccountInput, user: P1User = Depends(service.require_admin), db: Session = Depends(get_db)):
    # Serialize edits of active administrators so concurrent requests cannot remove all.
    admins = repository.lock_active_admins(db)
    target = repository.user_by_id(db, user_id)
    if not target:
        problem(404, "USER_NOT_FOUND", "El usuario no existe.")
    if target.id == user.id and (payload.active is False or payload.role == "PACIENTE"):
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
