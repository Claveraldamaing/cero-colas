"""Cookie sessions, account management and recovery for the P1 portal.

Local operator commands (run from backend):
  python -m app.p1.auth create-admin --email admin@example.com --name Administrador
  python -m app.p1.auth local-mail
"""

import argparse
import getpass
import hmac
import json
import logging
import os
from pathlib import Path
import re
import secrets
import smtplib
import ssl
from datetime import timedelta
from email.message import EmailMessage
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import Base, SessionLocal, engine, get_db
from app.p1.auth_models import (
    P1AuthAttempt, P1Challenge, P1RecoveryToken, P1Session, P1User, default_preferences,
)
from app.p1.security import (
    DUMMY_PASSWORD_HASH, csrf_for_token, hash_password, hash_token, new_token,
    password_problem, utcnow, verify_password,
)

router = APIRouter(prefix="/auth", tags=["P1 · Usuarios y seguridad"])
admin_router = APIRouter(prefix="/admin", tags=["P1 · Administración de usuarios"])
COOKIE_NAME = "p1_session"
logger = logging.getLogger(__name__)


def option(name, default=None):
    return getattr(settings, name, os.getenv(name, default))


def truthy(value):
    return value is True or str(value).lower() in {"1", "true", "yes"}


def problem(status: int, code: str, message: str):
    raise HTTPException(status_code=status, detail={"code": code, "message": message})


def normalize_email(value: str):
    value = value.strip().lower()
    if len(value) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
        raise ValueError("Ingresa un correo electrónico válido.")
    return value


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ChallengeInput(StrictInput):
    challenge_id: str = Field(min_length=1, max_length=64)
    challenge_answer: str = Field(min_length=1, max_length=16)


class LoginInput(ChallengeInput):
    email: str = Field(max_length=254)
    password: str = Field(min_length=1, max_length=128)

    _email = field_validator("email")(normalize_email)


class RegisterInput(LoginInput):
    name: str = Field(min_length=2, max_length=120)

    @field_validator("name")
    @classmethod
    def name_valid(cls, value):
        value = " ".join(value.split())
        if len(value) < 2:
            raise ValueError("Ingresa tu nombre.")
        return value


class Preferences(StrictInput):
    email_notifications: bool = Field(default=True, strict=True)
    language: Literal["es"] = "es"
    theme: Literal["system", "light", "dark"] = "system"


class ProfileInput(StrictInput):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    preferences: Preferences | None = None

    @field_validator("name")
    @classmethod
    def name_valid(cls, value):
        if value is None:
            return value
        value = " ".join(value.split())
        if len(value) < 2:
            raise ValueError("Ingresa tu nombre.")
        return value


class PasswordInput(StrictInput):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=1, max_length=128)


class ForgotInput(ChallengeInput):
    email: str = Field(max_length=254)
    _email = field_validator("email")(normalize_email)


class ResetInput(StrictInput):
    token: str = Field(min_length=20, max_length=128)
    new_password: str = Field(min_length=1, max_length=128)


class AccountInput(StrictInput):
    active: bool | None = Field(default=None, strict=True)
    role: Literal["PACIENTE", "ADMIN"] | None = None


def user_json(user: P1User):
    return {
        "id": user.id, "name": user.name, "email": user.email,
        "role": user.role, "active": user.active,
        "preferences": {**default_preferences(), **(user.preferences or {})},
        "created_at": user.created_at.isoformat() + "Z",
    }


def client_subject(request: Request):
    return request.client.host if request.client else "unknown"


def challenge_client(request: Request):
    return hash_token(client_subject(request) + "|" + request.headers.get("user-agent", ""))


def check_origin(request: Request):
    origin = request.headers.get("origin")
    if origin and origin.rstrip("/") not in {str(o).rstrip("/") for o in settings.CORS_ORIGINS}:
        problem(403, "ORIGIN_REJECTED", "Este origen no está autorizado para iniciar una sesión.")


def check_limit(db: Session, scope: str, subject: str, count: int, seconds: int):
    since = utcnow() - timedelta(seconds=seconds)
    attempts = db.query(P1AuthAttempt).filter(
        P1AuthAttempt.scope == scope, P1AuthAttempt.subject_hash == hash_token(subject),
        P1AuthAttempt.created_at > since,
    ).count()
    if attempts >= count:
        raise HTTPException(429, detail={"code": "TOO_MANY_ATTEMPTS", "message": "Demasiados intentos. Espera 15 minutos antes de volver a intentarlo."}, headers={"Retry-After": str(seconds)})


def record_attempt(db: Session, scope: str, subject: str):
    db.add(P1AuthAttempt(scope=scope, subject_hash=hash_token(subject)))


def throttle(db: Session, request: Request, scope: str, count=30, seconds=900):
    check_limit(db, scope, client_subject(request), count, seconds)
    record_attempt(db, scope, client_subject(request))
    # Bound retention of challenge/rate-limit material. No hospital identity is retained.
    db.query(P1AuthAttempt).filter(P1AuthAttempt.created_at < utcnow() - timedelta(days=1)).delete(synchronize_session=False)
    db.commit()


@router.get("/challenge")
def challenge(request: Request, response: Response, db: Session = Depends(get_db)):
    throttle(db, request, "challenge", count=60)
    left, right = secrets.randbelow(9) + 1, secrets.randbelow(9) + 1
    challenge_id = new_token()
    db.query(P1Challenge).filter(P1Challenge.expires_at < utcnow()).delete(synchronize_session=False)
    db.add(P1Challenge(id=challenge_id, answer_hash=hash_token(challenge_id + ":" + str(left + right)), client_hash=challenge_client(request), expires_at=utcnow() + timedelta(minutes=5)))
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return {"challenge_id": challenge_id, "prompt": f"¿Cuánto es {left} + {right}?", "expires_in": 300, "mode": "development_arithmetic"}


def verify_challenge(db: Session, request: Request, challenge_id: str, challenge_answer: str):
    entry = db.query(P1Challenge).filter(P1Challenge.id == challenge_id).first()
    now = utcnow()
    if not entry or entry.expires_at <= now or entry.consumed_at is not None or entry.client_hash != challenge_client(request):
        problem(400, "CHALLENGE_EXPIRED", "La verificación venció o ya fue utilizada. Solicita una nueva.")
    expected_hash = entry.answer_hash
    # The conditional update also prevents simultaneous reuse of the same challenge.
    consumed = db.query(P1Challenge).filter(P1Challenge.id == challenge_id, P1Challenge.consumed_at.is_(None), P1Challenge.expires_at > now).update({"consumed_at": now}, synchronize_session=False)
    db.commit()
    if not consumed or not hmac.compare_digest(expected_hash, hash_token(challenge_id + ":" + challenge_answer.strip())):
        problem(400, "CHALLENGE_INVALID", "La respuesta de verificación no es correcta. Solicita una nueva.")


def set_session_cookie(response: Response, token: str):
    response.set_cookie(COOKIE_NAME, token, max_age=int(option("SESSION_TTL_SECONDS", 28800)), httponly=True, secure=truthy(option("COOKIE_SECURE", False)), samesite="lax", path="/")
    response.headers["Cache-Control"] = "no-store"


def create_session(db: Session, user: P1User, response: Response):
    token = new_token()
    csrf_token = csrf_for_token(token)
    entry = P1Session(user_id=user.id, token_hash=hash_token(token), csrf_hash=hash_token(csrf_token), expires_at=utcnow() + timedelta(seconds=int(option("SESSION_TTL_SECONDS", 28800))))
    db.add(entry)
    db.commit()
    set_session_cookie(response, token)
    return {"user": user_json(user), "csrf_token": csrf_token}


def current_session(request: Request, db: Session = Depends(get_db)) -> P1Session:
    token = request.cookies.get(COOKIE_NAME, "")
    if not token or len(token) > 128:
        problem(401, "AUTH_REQUIRED", "Inicia sesión para continuar.")
    entry = db.query(P1Session).filter(P1Session.token_hash == hash_token(token), P1Session.revoked_at.is_(None), P1Session.expires_at > utcnow()).first()
    if not entry:
        problem(401, "SESSION_EXPIRED", "Tu sesión venció. Inicia sesión nuevamente.")
    user = db.get(P1User, entry.user_id)
    if not user or not user.active:
        problem(401, "ACCOUNT_UNAVAILABLE", "La cuenta no está disponible. Contacta al administrador.")
    return entry


def current_user(session: P1Session = Depends(current_session), db: Session = Depends(get_db)) -> P1User:
    return db.get(P1User, session.user_id)


def require_csrf(request: Request, session: P1Session = Depends(current_session)) -> P1Session:
    value = request.headers.get("X-CSRF-Token", "")
    if not value or not hmac.compare_digest(hash_token(value), session.csrf_hash):
        problem(403, "CSRF_INVALID", "La verificación de sesión no es válida. Actualiza la página.")
    return session


def require_admin(user: P1User = Depends(current_user)) -> P1User:
    if user.role != "ADMIN":
        problem(403, "ADMIN_REQUIRED", "Se requieren permisos de administrador.")
    return user


def require_password(password: str):
    issue = password_problem(password)
    if issue:
        problem(422, "WEAK_PASSWORD", issue)


@router.post("/register", status_code=201)
def register(payload: RegisterInput, request: Request, response: Response, db: Session = Depends(get_db)):
    check_origin(request)
    throttle(db, request, "register", count=10, seconds=3600)
    verify_challenge(db, request, payload.challenge_id, payload.challenge_answer)
    require_password(payload.password)
    user = P1User(name=payload.name, email=payload.email, password_hash=hash_password(payload.password), role="PACIENTE", active=True, preferences=default_preferences())
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        problem(409, "EMAIL_UNAVAILABLE", "No se puede registrar este correo. Si ya tienes una cuenta, inicia sesión o recupera tu contraseña.")
    return create_session(db, user, response)


@router.post("/login")
def login(payload: LoginInput, request: Request, response: Response, db: Session = Depends(get_db)):
    check_origin(request)
    throttle(db, request, "login_ip", count=30)
    check_limit(db, "login_identity", payload.email, count=5, seconds=900)
    verify_challenge(db, request, payload.challenge_id, payload.challenge_answer)
    user = db.query(P1User).filter(P1User.email == payload.email).first()
    correct = verify_password(payload.password, user.password_hash if user else DUMMY_PASSWORD_HASH)
    if not user or not correct or not user.active:
        record_attempt(db, "login_identity", payload.email)
        db.commit()
        problem(401, "INVALID_CREDENTIALS", "Correo o contraseña incorrectos, o cuenta no disponible.")
    db.query(P1AuthAttempt).filter(P1AuthAttempt.scope == "login_identity", P1AuthAttempt.subject_hash == hash_token(payload.email)).delete(synchronize_session=False)
    # A new login replaces an existing browser session, avoiding session fixation.
    old_token = request.cookies.get(COOKIE_NAME)
    if old_token:
        old = db.query(P1Session).filter(P1Session.token_hash == hash_token(old_token)).first()
        if old:
            old.revoked_at = utcnow()
            forget_hospital_sessions([old.id])
    db.commit()
    return create_session(db, user, response)


@router.get("/me")
def me(request: Request, response: Response, user: P1User = Depends(current_user)):
    response.headers["Cache-Control"] = "no-store"
    return {"user": user_json(user), "csrf_token": csrf_for_token(request.cookies[COOKIE_NAME])}


def forget_hospital_sessions(ids):
    # Lazy import prevents a dependency cycle while keeping sensitive sessions short-lived.
    try:
        from app.p1.hospital import hospital_client
    except ImportError:
        return
    for session_id in ids:
        hospital_client.forget(session_id)


def revoke_sessions(db: Session, user_id: str):
    entries = db.query(P1Session).filter(P1Session.user_id == user_id, P1Session.revoked_at.is_(None)).all()
    for entry in entries:
        entry.revoked_at = utcnow()
    forget_hospital_sessions([entry.id for entry in entries])


@router.post("/logout")
def logout(response: Response, session: P1Session = Depends(require_csrf), db: Session = Depends(get_db)):
    session.revoked_at = utcnow()
    db.commit()
    forget_hospital_sessions([session.id])
    response.delete_cookie(COOKIE_NAME, path="/", secure=truthy(option("COOKIE_SECURE", False)), httponly=True, samesite="lax")
    response.headers["Cache-Control"] = "no-store"
    return {"message": "Sesión cerrada."}


@router.patch("/profile", dependencies=[Depends(require_csrf)])
def update_profile(payload: ProfileInput, request: Request, response: Response, user: P1User = Depends(current_user), db: Session = Depends(get_db)):
    if payload.name is not None:
        user.name = payload.name
    if payload.preferences is not None:
        user.preferences = {**(user.preferences or default_preferences()), **payload.preferences.model_dump(exclude_unset=True)}
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return {"user": user_json(user), "csrf_token": csrf_for_token(request.cookies[COOKIE_NAME])}


@router.post("/change-password", dependencies=[Depends(require_csrf)])
def change_password(payload: PasswordInput, request: Request, response: Response, user: P1User = Depends(current_user), db: Session = Depends(get_db)):
    throttle(db, request, "password_change", count=5)
    if not verify_password(payload.current_password, user.password_hash):
        problem(400, "PASSWORD_MISMATCH", "La contraseña actual no es correcta.")
    require_password(payload.new_password)
    if verify_password(payload.new_password, user.password_hash):
        problem(422, "PASSWORD_REUSED", "Elige una contraseña diferente de la actual.")
    user.password_hash = hash_password(payload.new_password)
    revoke_sessions(db, user.id)
    db.query(P1RecoveryToken).filter(P1RecoveryToken.user_id == user.id, P1RecoveryToken.used_at.is_(None)).update({"used_at": utcnow()}, synchronize_session=False)
    db.commit()
    return {**create_session(db, user, response), "message": "Contraseña actualizada. Las sesiones anteriores se cerraron."}


def local_mail_enabled():
    return option("ENVIRONMENT", "development") == "development" and truthy(option("LOCAL_MAIL_ENABLED", True))


def mailbox_path():
    directory = option("LOCAL_MAILBOX_DIR", str(Path(__file__).resolve().parents[2] / ".local-mail"))
    return (Path(directory) / "recovery.jsonl").resolve()


def deliver_recovery(email: str, token: str):
    base = str(option("FRONTEND_URL", "http://localhost:5173")).rstrip("/")
    link = base + "/?reset_token=" + quote(token)
    if option("SMTP_HOST", ""):
        message = EmailMessage()
        message["Subject"] = "Cero Colas · Recuperar contraseña"
        message["From"] = option("SMTP_FROM", "") or option("SMTP_USERNAME", "")
        message["To"] = email
        message.set_content("Solicitaste cambiar tu contraseña de Cero Colas. El enlace vence en 30 minutos y funciona una sola vez.\n\n" + link + "\n\nSi no hiciste esta solicitud, ignora este mensaje.")
        use_ssl = truthy(option("SMTP_SSL", False))
        smtp_class = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
        kwargs = {"context": ssl.create_default_context()} if use_ssl else {}
        with smtp_class(option("SMTP_HOST"), int(option("SMTP_PORT", 465 if use_ssl else 587)), timeout=10, **kwargs) as smtp:
            if not use_ssl and truthy(option("SMTP_STARTTLS", True)):
                smtp.starttls(context=ssl.create_default_context())
            if option("SMTP_USERNAME", ""):
                smtp.login(option("SMTP_USERNAME"), option("SMTP_PASSWORD", ""))
            smtp.send_message(message)
        return
    if not local_mail_enabled():
        raise RuntimeError("Recovery delivery is not configured")
    path = mailbox_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # This developer mailbox is a filesystem artifact, never an HTTP endpoint.
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"to": email, "url": link, "expires_at": (utcnow() + timedelta(minutes=30)).isoformat() + "Z"}, ensure_ascii=False) + "\n")
    if os.name != "nt":
        path.chmod(0o600)


@router.post("/forgot-password")
def forgot_password(payload: ForgotInput, request: Request, db: Session = Depends(get_db)):
    check_origin(request)
    throttle(db, request, "forgot_password", count=5)
    verify_challenge(db, request, payload.challenge_id, payload.challenge_answer)
    if not option("SMTP_HOST", "") and not local_mail_enabled():
        problem(503, "RECOVERY_UNAVAILABLE", "La recuperación por correo aún no está configurada. Contacta al administrador.")
    user = db.query(P1User).filter(P1User.email == payload.email, P1User.active.is_(True)).first()
    if user:
        token = new_token()
        db.query(P1RecoveryToken).filter(P1RecoveryToken.user_id == user.id, P1RecoveryToken.used_at.is_(None)).update({"used_at": utcnow()}, synchronize_session=False)
        recovery = P1RecoveryToken(user_id=user.id, token_hash=hash_token(token), expires_at=utcnow() + timedelta(minutes=30))
        db.add(recovery)
        db.commit()
        try:
            deliver_recovery(user.email, token)
        except (OSError, RuntimeError, smtplib.SMTPException):
            recovery.used_at = utcnow()
            db.commit()
            logger.error("Password recovery delivery failed; inspect mail configuration.")
    return {"message": "Si existe una cuenta activa con ese correo, se ha solicitado un enlace de recuperación.", "delivery_mode": "smtp" if option("SMTP_HOST", "") else "local_mailbox"}


@router.post("/reset-password")
def reset_password(payload: ResetInput, request: Request, response: Response, db: Session = Depends(get_db)):
    check_origin(request)
    throttle(db, request, "reset_password", count=10)
    require_password(payload.new_password)
    entry = db.query(P1RecoveryToken).filter(P1RecoveryToken.token_hash == hash_token(payload.token)).with_for_update().first()
    now = utcnow()
    if not entry or entry.used_at is not None or entry.expires_at <= now:
        problem(400, "RECOVERY_INVALID", "El enlace es inválido, venció o ya fue utilizado. Solicita uno nuevo.")
    user = db.get(P1User, entry.user_id)
    if not user or not user.active:
        problem(400, "RECOVERY_INVALID", "El enlace es inválido, venció o ya fue utilizado. Solicita uno nuevo.")
    consumed = db.query(P1RecoveryToken).filter(P1RecoveryToken.id == entry.id, P1RecoveryToken.used_at.is_(None)).update({"used_at": now}, synchronize_session=False)
    if not consumed:
        db.rollback()
        problem(400, "RECOVERY_INVALID", "El enlace ya fue utilizado. Solicita uno nuevo.")
    user.password_hash = hash_password(payload.new_password)
    revoke_sessions(db, user.id)
    db.commit()
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"message": "Contraseña restablecida. Ya puedes iniciar sesión con tu nueva contraseña."}


@admin_router.get("/users")
def list_users(response: Response, user: P1User = Depends(require_admin), db: Session = Depends(get_db), offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), q: str = Query("", max_length=120)):
    query = db.query(P1User)
    if q.strip():
        pattern = "%" + q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        query = query.filter(P1User.name.ilike(pattern, escape="\\") | P1User.email.ilike(pattern, escape="\\"))
    total = query.count()
    items = query.order_by(P1User.created_at.desc(), P1User.id).offset(offset).limit(limit).all()
    response.headers["Cache-Control"] = "no-store"
    return {"items": [user_json(item) for item in items], "total": total, "offset": offset, "limit": limit}


@admin_router.patch("/users/{user_id}", dependencies=[Depends(require_csrf)])
def update_account(user_id: str, payload: AccountInput, user: P1User = Depends(require_admin), db: Session = Depends(get_db)):
    # Serialize edits of active administrators so concurrent requests cannot remove all.
    admins = db.query(P1User).filter(P1User.role == "ADMIN", P1User.active.is_(True)).order_by(P1User.id).with_for_update().all()
    target = db.get(P1User, user_id)
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
        revoke_sessions(db, target.id)
    db.commit()
    return user_json(target)


def operator_cli():
    parser = argparse.ArgumentParser(description="Administración local de cuentas P1")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create-admin", help="Crear un administrador sin contraseña predeterminada")
    create.add_argument("--email", required=True)
    create.add_argument("--name", required=True)
    sub.add_parser("local-mail", help="Consultar el último enlace del buzón local de desarrollo")
    args = parser.parse_args()
    if args.command == "local-mail":
        if not local_mail_enabled():
            parser.error("El buzón local solo está disponible en desarrollo.")
        path = mailbox_path()
        if not path.exists() or not path.read_text(encoding="utf-8").strip():
            print("El buzón local no contiene solicitudes.")
            return
        item = json.loads(path.read_text(encoding="utf-8").splitlines()[-1])
        print("Para:", item["to"], "\nVence:", item["expires_at"], "\nEnlace:", item["url"])
        return
    try:
        email = normalize_email(args.email)
    except ValueError as exc:
        parser.error(str(exc))
    name = " ".join(args.name.split())
    if not 2 <= len(name) <= 120:
        parser.error("El nombre debe tener entre 2 y 120 caracteres.")
    password = getpass.getpass("Contraseña del administrador: ")
    issue = password_problem(password)
    if issue:
        parser.error(issue)
    if password != getpass.getpass("Repite la contraseña: "):
        parser.error("Las contraseñas no coinciden.")
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        if db.query(P1User).filter(P1User.email == email).first():
            parser.error("El correo ya está registrado. No se modificó la cuenta existente.")
        db.add(P1User(name=name, email=email, password_hash=hash_password(password), role="ADMIN", active=True, preferences=default_preferences()))
        db.commit()
    print("Administrador creado. Ya puede iniciar sesión.")


if __name__ == "__main__":
    operator_cli()
