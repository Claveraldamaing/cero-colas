from sqlalchemy import BigInteger, Column, Date, DateTime, ForeignKey, Integer, String, Text, Time, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base


class LocalAppointment(Base):
    __tablename__ = "cita_local"

    id_cita_local = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    id_usuario = Column(String(36), ForeignKey("p1_users.id", ondelete="CASCADE"), nullable=False, index=True)
    codigo_cita = Column(String(50), nullable=False, unique=True)
    clave_anulacion_cifrada = Column(Text, nullable=True)
    idempotency_key = Column(String(128), nullable=False)
    idempotency_fingerprint = Column(String(64), nullable=True)
    estado = Column(String(30), nullable=False)
    canal = Column(String(30), nullable=True)
    fecha = Column(Date, nullable=False)
    hora_inicio = Column(Time, nullable=False)
    hora_fin = Column(Time, nullable=True)
    especialidad = Column(String(150), nullable=True)
    consultorio = Column(String(150), nullable=True)
    medico = Column(String(150), nullable=True)
    financiamiento = Column(String(100), nullable=True)
    anulable_hasta = Column(DateTime(timezone=True), nullable=True)
    fecha_registro = Column(DateTime(timezone=True), nullable=False)
    fecha_sincronizacion = Column(DateTime(timezone=True), nullable=True)

    indicaciones = relationship(
        "AppointmentInstruction",
        back_populates="cita",
        cascade="all, delete-orphan",
        order_by="AppointmentInstruction.orden",
    )

    __table_args__ = (
        UniqueConstraint("id_usuario", "idempotency_key", name="uq_cita_user_idempotency"),
    )


class AppointmentInstruction(Base):
    __tablename__ = "cita_indicacion"

    id_indicacion = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    id_cita_local = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("cita_local.id_cita_local", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    descripcion = Column(Text, nullable=False)
    orden = Column(Integer, nullable=True)
    cita = relationship("LocalAppointment", back_populates="indicaciones")


class APIAudit(Base):
    __tablename__ = "auditoria_api"

    id_auditoria = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    request_id = Column(String(36), nullable=True)
    metodo_http = Column(String(10), nullable=True)
    endpoint = Column(String(255), nullable=True)
    estado_http = Column(Integer, nullable=True)
    codigo_error = Column(String(100), nullable=True)
    rastreo = Column(String(150), nullable=True)
    tiempo_respuesta_ms = Column(Integer, nullable=True)
    numero_reintento = Column(Integer, nullable=False, default=0)
    fecha_hora = Column(DateTime(timezone=True), nullable=False)
