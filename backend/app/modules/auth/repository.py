"""Database access for accounts, sessions, challenges and recovery tokens."""
from sqlalchemy.orm import Session

from .models import P1AuthAttempt, P1Challenge, P1RecoveryToken, P1Session, P1User


def user_by_email(db: Session, email: str):
    return db.query(P1User).filter(P1User.email == email).first()


def active_user_by_email(db: Session, email: str):
    return db.query(P1User).filter(P1User.email == email, P1User.active.is_(True)).first()


def user_by_id(db: Session, user_id: str):
    return db.get(P1User, user_id)


def session_by_token_hash(db: Session, token_hash: str):
    return db.query(P1Session).filter(P1Session.token_hash == token_hash).first()


def active_session_by_token_hash(db: Session, token_hash: str, now):
    return db.query(P1Session).filter(
        P1Session.token_hash == token_hash,
        P1Session.revoked_at.is_(None),
        P1Session.expires_at > now,
    ).first()


def sessions_by_user(db: Session, user_id: str):
    return db.query(P1Session).filter(
        P1Session.user_id == user_id,
        P1Session.revoked_at.is_(None),
    ).all()


def count_attempts(db: Session, scope: str, subject_hash: str, since):
    return db.query(P1AuthAttempt).filter(
        P1AuthAttempt.scope == scope,
        P1AuthAttempt.subject_hash == subject_hash,
        P1AuthAttempt.created_at > since,
    ).count()


def add_attempt(db: Session, scope: str, subject_hash: str):
    db.add(P1AuthAttempt(scope=scope, subject_hash=subject_hash))


def clear_attempts(db: Session, scope: str, subject_hash: str):
    db.query(P1AuthAttempt).filter(
        P1AuthAttempt.scope == scope,
        P1AuthAttempt.subject_hash == subject_hash,
    ).delete(synchronize_session=False)


def prune_attempts(db: Session, before):
    db.query(P1AuthAttempt).filter(P1AuthAttempt.created_at < before).delete(synchronize_session=False)


def challenge_by_id(db: Session, challenge_id: str):
    return db.query(P1Challenge).filter(P1Challenge.id == challenge_id).first()


def add_challenge(db: Session, challenge: P1Challenge):
    db.add(challenge)


def consume_challenge(db: Session, challenge_id: str, now):
    return db.query(P1Challenge).filter(
        P1Challenge.id == challenge_id,
        P1Challenge.consumed_at.is_(None),
        P1Challenge.expires_at > now,
    ).update({"consumed_at": now}, synchronize_session=False)


def prune_challenges(db: Session, before):
    db.query(P1Challenge).filter(P1Challenge.expires_at < before).delete(synchronize_session=False)


def expire_recovery_tokens(db: Session, user_id: str, now):
    db.query(P1RecoveryToken).filter(
        P1RecoveryToken.user_id == user_id,
        P1RecoveryToken.used_at.is_(None),
    ).update({"used_at": now}, synchronize_session=False)


def recovery_by_token_hash(db: Session, token_hash: str, for_update: bool = False):
    query = db.query(P1RecoveryToken).filter(P1RecoveryToken.token_hash == token_hash)
    if for_update:
        query = query.with_for_update()
    return query.first()


def add_recovery_token(db: Session, recovery: P1RecoveryToken):
    db.add(recovery)


def consume_recovery_token(db: Session, token_id: str, now):
    return db.query(P1RecoveryToken).filter(
        P1RecoveryToken.id == token_id,
        P1RecoveryToken.used_at.is_(None),
    ).update({"used_at": now}, synchronize_session=False)


def list_users(db: Session, q: str, offset: int, limit: int):
    query = db.query(P1User)
    if q.strip():
        pattern = "%" + q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        query = query.filter(P1User.name.ilike(pattern, escape="\\") | P1User.email.ilike(pattern, escape="\\"))
    total = query.count()
    items = query.order_by(P1User.created_at.desc(), P1User.id).offset(offset).limit(limit).all()
    return items, total


def lock_active_admins(db: Session):
    return db.query(P1User).filter(
        P1User.role == "ADMIN",
        P1User.active.is_(True),
    ).order_by(P1User.id).with_for_update().all()
