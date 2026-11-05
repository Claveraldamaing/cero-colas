"""Portal privacy policy and user-facing prototype notice."""
from app.core.config import settings

PROTOTYPE_NOTICE = (
    "Prototipo académico conectado al simulador oficial del contrato apicitas. "
    "Usa únicamente datos de prueba. Los resultados del simulador no acreditan identidad, SIS ni citas reales. "
    "El DNI y la fecha de nacimiento se transmiten para la identificación y no se guardan en la base local. "
    "La sesión hospitalaria y sus tokens permanecen en memoria del servidor hasta su vencimiento o cierre. "
    "La política definitiva debe ser aprobada por el hospital antes de utilizar datos reales."
)


def privacy_config():
    approved = bool(getattr(settings, "HOSPITAL_PRIVACY_POLICY_APPROVED", False))
    text = getattr(settings, "HOSPITAL_PRIVACY_POLICY_TEXT", "").strip()
    return approved and bool(text), text
