"""Authentication policies and session lifecycle shared by HTTP and CLI entry points."""
import hmac
import os
import secrets
from datetime import timedelta

from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.errors import problem
from app.core.security import (
    DUMMY_PASSWORD_HASH, csrf_for_token, hash_password, hash_token, new_token,
    password_problem, utcnow, verify_password,
)
from . import repository
from .models import P1Challenge, P1RecoveryToken, P1Session, P1User, default_preferences
from .schemas import LoginInput, PasswordInput, RegisterInput, ResetInput

COOKIE_NAME = "p1_session"


def option(name, default=None):
    return getattr(settings, name, os.getenv(name, default))


def truthy(value):
    return value is True or str(value).lower() in {"1", "true", "yes"}


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
    attempts = repository.count_attempts(db, scope, hash_token(subject), since)
    if attempts >= count:
        raise HTTPException(429, detail={"code": "TOO_MANY_ATTEMPTS", "message": "Demasiados intentos. Espera 15 minutos antes de volver a intentarlo."}, headers={"Retry-After": str(seconds)})


def record_attempt(db: Session, scope: str, subject: str):
    repository.add_attempt(db, scope, hash_token(subject))


def throttle(db: Session, request: Request, scope: str, count=30, seconds=900):
    check_limit(db, scope, client_subject(request), count, seconds)
    record_attempt(db, scope, client_subject(request))
    # Bound retention of challenge/rate-limit material. No hospital identity is retained.
    repository.prune_attempts(db, utcnow() - timedelta(days=1))
    db.commit()


def issue_challenge(db: Session, request: Request, response: Response):
    throttle(db, request, "challenge", count=60)
    left, right = secrets.randbelow(9) + 1, secrets.randbelow(9) + 1
    challenge_id = new_token()
    now = utcnow()
    repository.prune_challenges(db, now)
    repository.add_challenge(db, P1Challenge(id=challenge_id, answer_hash=hash_token(challenge_id + ":" + str(left + right)), client_hash=challenge_client(request), expires_at=now + timedelta(minutes=5)))
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return {"challenge_id": challenge_id, "prompt": f"¿Cuánto es {left} + {right}?", "expires_in": 300, "mode": "development_arithmetic"}


def verify_challenge(db: Session, request: Request, challenge_id: str, challenge_answer: str):
    entry = repository.challenge_by_id(db, challenge_id)
    now = utcnow()
    if not entry or entry.expires_at <= now or entry.consumed_at is not None or entry.client_hash != challenge_client(request):
        problem(400, "CHALLENGE_EXPIRED", "La verificación venció o ya fue utilizada. Solicita una nueva.")
    expected_hash = entry.answer_hash
    # The conditional update also prevents simultaneous reuse of the same challenge.
    consumed = repository.consume_challenge(db, challenge_id, now)
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
    entry = repository.active_session_by_token_hash(db, hash_token(token), utcnow())
    if not entry:
        problem(401, "SESSION_EXPIRED", "Tu sesión venció. Inicia sesión nuevamente.")
    user = repository.user_by_id(db, entry.user_id)
    if not user or not user.active:
        problem(401, "ACCOUNT_UNAVAILABLE", "La cuenta no está disponible. Contacta al administrador.")
    return entry


def current_user(session: P1Session = Depends(current_session), db: Session = Depends(get_db)) -> P1User:
    return repository.user_by_id(db, session.user_id)


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


def register_account(db: Session, request: Request, payload: RegisterInput):
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
    return user


def login_account(db: Session, request: Request, payload: LoginInput):
    check_origin(request)
    throttle(db, request, "login_ip", count=30)
    check_limit(db, "login_identity", payload.email, count=5, seconds=900)
    verify_challenge(db, request, payload.challenge_id, payload.challenge_answer)
    user = repository.user_by_email(db, payload.email)
    correct = verify_password(payload.password, user.password_hash if user else DUMMY_PASSWORD_HASH)
    if not user or not correct or not user.active:
        record_attempt(db, "login_identity", payload.email)
        db.commit()
        problem(401, "INVALID_CREDENTIALS", "Correo o contraseña incorrectos, o cuenta no disponible.")
    repository.clear_attempts(db, "login_identity", hash_token(payload.email))
    # A new login replaces an existing browser session, avoiding session fixation.
    old_token = request.cookies.get(COOKIE_NAME)
    if old_token:
        old = repository.session_by_token_hash(db, hash_token(old_token))
        if old:
            old.revoked_at = utcnow()
            forget_hospital_sessions([old.id])
    db.commit()
    return user


def forget_hospital_sessions(ids):
    # Lazy import prevents a dependency cycle while keeping sensitive sessions short-lived.
    try:
        from app.integrations.hospital import hospital_client
    except ImportError:
        return
    for session_id in ids:
        hospital_client.forget(session_id)


def revoke_sessions(db: Session, user_id: str):
    entries = repository.sessions_by_user(db, user_id)
    for entry in entries:
        entry.revoked_at = utcnow()
    forget_hospital_sessions([entry.id for entry in entries])


def change_password(db: Session, request: Request, user: P1User, payload: PasswordInput):
    throttle(db, request, "password_change", count=5)
    if not verify_password(payload.current_password, user.password_hash):
        problem(400, "PASSWORD_MISMATCH", "La contraseña actual no es correcta.")
    require_password(payload.new_password)
    if verify_password(payload.new_password, user.password_hash):
        problem(422, "PASSWORD_REUSED", "Elige una contraseña diferente de la actual.")
    user.password_hash = hash_password(payload.new_password)
    revoke_sessions(db, user.id)
    repository.expire_recovery_tokens(db, user.id, utcnow())
    db.commit()


def start_recovery(db: Session, user: P1User):
    token = new_token()
    repository.expire_recovery_tokens(db, user.id, utcnow())
    recovery = P1RecoveryToken(user_id=user.id, token_hash=hash_token(token), expires_at=utcnow() + timedelta(minutes=30))
    repository.add_recovery_token(db, recovery)
    db.commit()
    return token, recovery


def reset_password(db: Session, request: Request, payload: ResetInput):
    check_origin(request)
    throttle(db, request, "reset_password", count=10)
    require_password(payload.new_password)
    entry = repository.recovery_by_token_hash(db, hash_token(payload.token), for_update=True)
    now = utcnow()
    if not entry or entry.used_at is not None or entry.expires_at <= now:
        problem(400, "RECOVERY_INVALID", "El enlace es inválido, venció o ya fue utilizado. Solicita uno nuevo.")
    user = repository.user_by_id(db, entry.user_id)
    if not user or not user.active:
        problem(400, "RECOVERY_INVALID", "El enlace es inválido, venció o ya fue utilizado. Solicita uno nuevo.")
    consumed = repository.consume_recovery_token(db, entry.id, now)
    if not consumed:
        db.rollback()
        problem(400, "RECOVERY_INVALID", "El enlace ya fue utilizado. Solicita uno nuevo.")
    user.password_hash = hash_password(payload.new_password)
    revoke_sessions(db, user.id)
    db.commit()
    return user
