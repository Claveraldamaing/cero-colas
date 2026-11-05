"""Hospital contract constants and the in-memory patient identity model."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

LIMA = timezone(timedelta(hours=-5))

PATIENT_FIELDS = ("nombre_enmascarado", "edad")
ELIGIBILITY_REQUIRED_FIELDS = (
    "elegible",
    "motivos",
    "condicion",
    "sis",
    "referencias",
    "especialidades",
    "proxima_reserva_desde",
)
POLICY_FIELDS = (
    "ventana",
    "reservas_por_dia",
    "dias_entre_reservas",
    "horas_minimas_para_anular",
    "intentos_identificacion",
    "sesion_paciente_segundos",
)
APPOINTMENT_FIELDS = (
    "codigo_cita",
    "estado",
    "canal",
    "fecha",
    "hora_inicio",
    "hora_fin",
    "especialidad",
    "consultorio",
    "medico",
    "financiamiento",
    "indicaciones",
    "anulable_hasta",
)


@dataclass
class PatientIdentity:
    token: str
    expires_at: datetime
    patient: dict
    eligibility: dict | None = None
