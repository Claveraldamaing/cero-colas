"""Hospital integration errors and user-safe messages."""
ERROR_MESSAGES = {
    "IDENTIDAD_NO_VALIDA": "No encontramos un paciente con esos datos. Revisa el DNI y la fecha de nacimiento.",
    "IDENTIDAD_BLOQUEADA": "Por seguridad, espera 30 minutos o acércate a Admisión.",
    "SESION_PACIENTE_INVALIDA": "Tu identificación hospitalaria terminó. Ingresa nuevamente el DNI y la fecha de nacimiento.",
    "NO_AUTORIZADO": "No fue posible autorizar la conexión con el hospital. Comunícate con el equipo de soporte.",
    "DEMASIADAS_SOLICITUDES": "Se alcanzó el límite de intentos. Espera antes de volver a intentarlo.",
    "CANAL_CERRADO": "Las citas en línea no están disponibles en este momento.",
    "SERVICIO_NO_DISPONIBLE": "El servicio del hospital no está disponible. Intenta más tarde.",
    "DATOS_INVALIDOS": "Revisa el DNI y la fecha de nacimiento ingresados.",
    "NO_ELEGIBLE": "Por el momento no cumples las condiciones para reservar en línea.",
    "PACIENTE_SUSPENDIDO": "Por inasistencias anteriores, reserva en Admisión.",
    "ERROR_INTERNO": "El hospital no pudo completar la consulta. Intenta más tarde.",
}
REASON_MESSAGES = {
    "SIS_NO_VIGENTE": "Tu SIS no está vigente. Acércate a Admisión.",
    "SIS_NO_VERIFICABLE": "No pudimos confirmar tu SIS. Intenta más tarde.",
    "PACIENTE_NUEVO": "Para tu primera atención, acércate a Admisión.",
    "SIN_REFERENCIA": "Necesitas una referencia aceptada o recibida de tu establecimiento.",
    "SIN_ESPECIALIDADES_PROGRAMADAS": "Aún no hay horarios disponibles para tu especialidad.",
    "ESPERA_ENTRE_RESERVAS": "Aún debes esperar para realizar otra reserva. Revisa la próxima fecha permitida.",
    "PACIENTE_SUSPENDIDO": "Por inasistencias anteriores, reserva en Admisión.",
}


class HospitalError(Exception):
    def __init__(self, code: str, message: str, status: int = 503, rastreo: str | None = None, retry_after: int | None = None):
        super().__init__(code)  # Never include upstream body/credentials in exceptions.
        self.status = status
        self.detail = {"code": code, "message": message}
        if rastreo:
            self.detail["rastreo"] = rastreo
        if retry_after is not None:
            self.detail["retry_after"] = retry_after
