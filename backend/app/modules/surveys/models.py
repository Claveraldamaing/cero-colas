"""Local P1 feedback only: hospital identity and clinical data are never persisted."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint

from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class P1UsageEvent(Base):
    __tablename__ = "p1_usage_events"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("p1_users.id", ondelete="CASCADE"), nullable=False, index=True)
    # A random, opaque local session identifier, never a hospital token or DNI.
    session_id = Column(String(36), ForeignKey("p1_sessions.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(String(40), nullable=False, default="eligibility_consulted")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    __table_args__ = (UniqueConstraint("session_id", "event_type", name="uq_p1_usage_session_type"),)


class P1Survey(Base):
    __tablename__ = "p1_surveys"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("p1_users.id", ondelete="CASCADE"), nullable=False, index=True)
    usage_event_id = Column(String(36), ForeignKey("p1_usage_events.id", ondelete="CASCADE"), nullable=False, unique=True)
    ease_score = Column(Integer, nullable=False)
    satisfaction_score = Column(Integer, nullable=False)
    comment = Column(Text, nullable=True)
    scale_min = Column(Integer, nullable=False, default=1)
    scale_max = Column(Integer, nullable=False, default=5)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    __table_args__ = (
        CheckConstraint("scale_min < scale_max", name="ck_p1_survey_scale"),
        CheckConstraint("ease_score >= scale_min AND ease_score <= scale_max", name="ck_p1_survey_ease"),
        CheckConstraint("satisfaction_score >= scale_min AND satisfaction_score <= scale_max", name="ck_p1_survey_satisfaction"),
    )
