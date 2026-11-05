import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, JSON, String
from app.database import Base
from app.p1.security import utcnow


def uuid_string():
    return str(uuid.uuid4())


def default_preferences():
    return {"email_notifications": True, "language": "es", "theme": "system"}


class P1User(Base):
    __tablename__ = "p1_users"

    id = Column(String(36), primary_key=True, default=uuid_string)
    name = Column(String(120), nullable=False)
    email = Column(String(254), nullable=False, unique=True, index=True)
    password_hash = Column(String(256), nullable=False)
    role = Column(String(16), nullable=False, default="PACIENTE")
    active = Column(Boolean, nullable=False, default=True)
    preferences = Column(JSON, nullable=False, default=default_preferences)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)


class P1Session(Base):
    __tablename__ = "p1_sessions"

    id = Column(String(36), primary_key=True, default=uuid_string)
    user_id = Column(String(36), ForeignKey("p1_users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    csrf_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    expires_at = Column(DateTime, nullable=False, index=True)
    revoked_at = Column(DateTime, nullable=True)


class P1Challenge(Base):
    __tablename__ = "p1_challenges"

    id = Column(String(64), primary_key=True, default=uuid_string)
    answer_hash = Column(String(64), nullable=False)
    client_hash = Column(String(64), nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    consumed_at = Column(DateTime, nullable=True)


class P1RecoveryToken(Base):
    __tablename__ = "p1_recovery_tokens"

    id = Column(String(36), primary_key=True, default=uuid_string)
    user_id = Column(String(36), ForeignKey("p1_users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)


class P1AuthAttempt(Base):
    __tablename__ = "p1_auth_attempts"

    id = Column(String(36), primary_key=True, default=uuid_string)
    scope = Column(String(32), nullable=False)
    subject_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    __table_args__ = (Index("ix_p1_auth_attempt_window", "scope", "subject_hash", "created_at"),)
