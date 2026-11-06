from datetime import date, datetime, time, timezone
import hashlib
import json

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.integrations.hospital import HospitalError, hospital_client
from app.modules.auth.models import P1Session, P1User
from .models import AppointmentInstruction, LocalAppointment
from .schemas import AppointmentRequest

APPOINTMENT_FIELDS = (
    "codigo_cita", "estado", "canal", "fecha", "hora_inicio", "hora_fin",
    "especialidad", "consultorio", "medico", "financiamiento",
    "indicaciones", "anulable_hasta",
)


def _fail_hospital(error: HospitalError):
    detail = error.detail
    headers = {"Retry-After": str(detail["retry_after"])} if "retry_after" in detail else None
    raise HTTPException(status_code=error.status, detail=detail, headers=headers) from None


def _eligibility(session_id: str):
    try:
        return hospital_client.eligibility(session_id, refresh=True)
    except HospitalError as error:
        _fail_hospital(error)


def _assert_reservable(session_id: str, specialty_id: str | None = None):
    eligibility = _eligibility(session_id)
    if not eligibility.get("reserve_ready"):
        policy_pending = eligibility.get("reference_policy_pending", False)
        code = "REFERENCE_POLICY_PENDING" if policy_pending else "RESERVATION_NOT_READY"
        message = (
            "La reserva seguirá bloqueada hasta que Admisión confirme y configure la vigencia de las referencias."
            if policy_pending
            else "El paciente no cumple todas las condiciones para reservar en línea."
        )
        raise HTTPException(status_code=409, detail={"code": code, "message": message})

    specialties = eligibility.get("specialties_allowed") or []
    selected = next(
        (item for item in specialties if item.get("especialidad_id") == specialty_id),
        None,
    ) if specialty_id else None
    if specialty_id and selected is None:
        raise HTTPException(
            status_code=403,
            detail={"code": "SPECIALTY_NOT_ALLOWED", "message": "Esta especialidad no está habilitada para las referencias vigentes del paciente."},
        )
    return eligibility, selected


def _availability_payload(payload: dict):
    rows = payload.get("datos")
    if not isinstance(rows, list):
        raise HTTPException(status_code=502, detail={"code": "INVALID_HOSPITAL_RESPONSE", "message": "El servicio devolvió un calendario incompleto."})
    result = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            day = date.fromisoformat(row["fecha"])
            count = row["cupos_libres"]
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise ValueError
        except (KeyError, TypeError, ValueError):
            raise HTTPException(status_code=502, detail={"code": "INVALID_HOSPITAL_RESPONSE", "message": "El servicio devolvió un día disponible con formato inválido."}) from None
        result.append({"date": day.isoformat(), "available_slots": count})
    return {"items": result}


def _slots_payload(payload: dict):
    rows = payload.get("datos")
    if not isinstance(rows, list):
        raise HTTPException(status_code=502, detail={"code": "INVALID_HOSPITAL_RESPONSE", "message": "El servicio devolvió una lista de horarios incompleta."})
    result = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        required = ("cupo_id", "fecha", "hora_inicio", "hora_fin", "consultorio", "medico")
        if any(not isinstance(row.get(key), str) or not row[key] for key in required):
            raise HTTPException(status_code=502, detail={"code": "INVALID_HOSPITAL_RESPONSE", "message": "El servicio devolvió un horario con formato inválido."})
        try:
            date.fromisoformat(row["fecha"])
            time.fromisoformat(row["hora_inicio"])
            time.fromisoformat(row["hora_fin"])
        except ValueError:
            raise HTTPException(status_code=502, detail={"code": "INVALID_HOSPITAL_RESPONSE", "message": "El servicio devolvió un horario con formato inválido."}) from None
        result.append({
            "slot_id": row["cupo_id"],
            "date": row["fecha"],
            "start_time": row["hora_inicio"],
            "end_time": row["hora_fin"],
            "office": row["consultorio"],
            "doctor": row["medico"],
        })
    return {"items": result}


def _fernet():
    key = getattr(settings, "CITA_ENCRYPTION_KEY", "")
    if not key:
        raise HTTPException(
            status_code=503,
            detail={"code": "APPOINTMENT_ENCRYPTION_NOT_CONFIGURED", "message": "Falta configurar CITA_ENCRYPTION_KEY para guardar de forma segura la clave de anulación."},
        )
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, UnicodeEncodeError):
        raise HTTPException(
            status_code=503,
            detail={"code": "APPOINTMENT_ENCRYPTION_MISCONFIGURED", "message": "CITA_ENCRYPTION_KEY no tiene un formato Fernet válido."},
        ) from None


def _saved_response(appointment: LocalAppointment, fernet: Fernet):
    key = None
    if appointment.clave_anulacion_cifrada:
        try:
            key = fernet.decrypt(appointment.clave_anulacion_cifrada.encode()).decode()
        except (InvalidToken, UnicodeDecodeError):
            raise HTTPException(
                status_code=500,
                detail={"code": "APPOINTMENT_KEY_UNREADABLE", "message": "No se pudo recuperar la clave de anulación guardada. Contacta a soporte."},
            ) from None
    return {
        "cita": {
            "codigo_cita": appointment.codigo_cita,
            "estado": appointment.estado,
            "canal": appointment.canal,
            "fecha": appointment.fecha.isoformat(),
            "hora_inicio": appointment.hora_inicio.isoformat(timespec="minutes"),
            "hora_fin": appointment.hora_fin.isoformat(timespec="minutes") if appointment.hora_fin else None,
            "especialidad": appointment.especialidad,
            "consultorio": appointment.consultorio,
            "medico": appointment.medico,
            "financiamiento": appointment.financiamiento,
            "indicaciones": [row.descripcion for row in appointment.indicaciones],
            "anulable_hasta": appointment.anulable_hasta.isoformat() if appointment.anulable_hasta else None,
        },
        "clave_anulacion": key,
    }


def availability(session: P1Session, specialty_id: str, month: str):
    _assert_reservable(session.id, specialty_id)
    try:
        payload = hospital_client.patient_request(
            session.id,
            f"/especialidades/{specialty_id}/disponibilidad",
            params={"mes": month},
        )
    except HospitalError as error:
        _fail_hospital(error)
    return _availability_payload(payload)


def slots(session: P1Session, specialty_id: str, selected_date: date):
    _assert_reservable(session.id, specialty_id)
    try:
        payload = hospital_client.patient_request(
            session.id,
            f"/especialidades/{specialty_id}/cupos",
            params={"fecha": selected_date.isoformat()},
        )
    except HospitalError as error:
        _fail_hospital(error)
    return _slots_payload(payload)


def _appointment_payload(payload: dict):
    if any(field not in payload for field in APPOINTMENT_FIELDS):
        raise HTTPException(status_code=502, detail={"code": "INVALID_HOSPITAL_RESPONSE", "message": "El servicio creó una cita, pero devolvió información incompleta. No vuelvas a reservar; conserva el mismo intento y contacta a soporte."})
    if not isinstance(payload.get("codigo_cita"), str) or not payload["codigo_cita"]:
        raise HTTPException(status_code=502, detail={"code": "INVALID_HOSPITAL_RESPONSE", "message": "El servicio devolvió una cita sin código."})
    if not isinstance(payload.get("indicaciones"), list) or not all(isinstance(item, str) for item in payload["indicaciones"]):
        raise HTTPException(status_code=502, detail={"code": "INVALID_HOSPITAL_RESPONSE", "message": "El servicio devolvió indicaciones con formato inválido."})
    cancellation_key = payload.get("clave_anulacion")
    if not isinstance(cancellation_key, str) or not cancellation_key:
        raise HTTPException(status_code=502, detail={"code": "INVALID_HOSPITAL_RESPONSE", "message": "El servicio no devolvió la clave de anulación. Conserva el código de cita y contacta a soporte."})
    try:
        appointment_date = date.fromisoformat(payload["fecha"])
        start_time = time.fromisoformat(payload["hora_inicio"])
        end_time = time.fromisoformat(payload["hora_fin"]) if payload["hora_fin"] else None
        cancellable_until = datetime.fromisoformat(payload["anulable_hasta"]) if payload["anulable_hasta"] else None
    except (TypeError, ValueError):
        raise HTTPException(status_code=502, detail={"code": "INVALID_HOSPITAL_RESPONSE", "message": "El servicio devolvió una cita con fecha u hora inválida."}) from None
    safe = {field: payload[field] for field in APPOINTMENT_FIELDS}
    safe["fecha"] = appointment_date.isoformat()
    safe["hora_inicio"] = start_time.isoformat(timespec="minutes")
    safe["hora_fin"] = end_time.isoformat(timespec="minutes") if end_time else None
    return safe, cancellation_key, appointment_date, start_time, end_time, cancellable_until


def reserve(db: Session, session: P1Session, user: P1User, data: AppointmentRequest):
    fernet = _fernet()
    request_body = {
        "cupo_id": data.slot_id,
        "referencia_id": data.reference_id,
        "telefono_contacto": data.contact_phone,
    }
    fingerprint = hashlib.sha256(
        json.dumps(request_body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    existing = db.query(LocalAppointment).filter_by(
        id_usuario=user.id,
        idempotency_key=data.idempotency_key,
    ).first()
    if existing:
        if existing.idempotency_fingerprint != fingerprint:
            raise HTTPException(
                status_code=409,
                detail={"code": "IDEMPOTENCY_KEY_REUSED", "message": "Esta clave ya se utilizó con otros datos. Inicia un nuevo intento de reserva."},
            )
        return _saved_response(existing, fernet)

    _, specialty = _assert_reservable(session.id, data.specialty_id)
    if data.reference_id not in (specialty.get("referencias") or []):
        raise HTTPException(status_code=403, detail={"code": "REFERENCE_NOT_ALLOWED", "message": "La referencia seleccionada no está habilitada para esta especialidad."})

    try:
        payload = hospital_client.patient_request(
            session.id,
            "/citas",
            method="POST",
            json=request_body,
            idempotency_key=data.idempotency_key,
        )
    except HospitalError as error:
        _fail_hospital(error)

    safe, cancellation_key, appointment_date, start_time, end_time, cancellable_until = _appointment_payload(payload)
    appointment = LocalAppointment(
        id_usuario=user.id,
        codigo_cita=safe["codigo_cita"],
        clave_anulacion_cifrada=fernet.encrypt(cancellation_key.encode()).decode(),
        idempotency_key=data.idempotency_key,
        idempotency_fingerprint=fingerprint,
        estado=safe["estado"],
        canal=safe["canal"],
        fecha=appointment_date,
        hora_inicio=start_time,
        hora_fin=end_time,
        especialidad=safe["especialidad"],
        consultorio=safe["consultorio"],
        medico=safe["medico"],
        financiamiento=safe["financiamiento"],
        anulable_hasta=cancellable_until,
        fecha_registro=datetime.now(timezone.utc),
        fecha_sincronizacion=datetime.now(timezone.utc),
    )
    db.add(appointment)
    for order, instruction in enumerate(safe["indicaciones"], start=1):
        appointment.indicaciones.append(AppointmentInstruction(descripcion=instruction, orden=order))
    try:
        db.commit()
        db.refresh(appointment)
    except IntegrityError:
        db.rollback()
        existing = db.query(LocalAppointment).filter_by(
            id_usuario=user.id,
            idempotency_key=data.idempotency_key,
        ).first()
        if existing:
            if existing.idempotency_fingerprint != fingerprint:
                raise HTTPException(
                    status_code=409,
                    detail={"code": "IDEMPOTENCY_KEY_REUSED", "message": "Esta clave ya se utilizó con otros datos. Inicia un nuevo intento de reserva."},
                ) from None
            return _saved_response(existing, fernet)
        raise HTTPException(
            status_code=409,
            detail={"code": "APPOINTMENT_PERSISTENCE_CONFLICT", "message": "El servicio pudo reservar la cita, pero no se pudo registrar localmente. Reintenta con la misma clave de idempotencia."},
        ) from None
    return {"cita": safe, "clave_anulacion": cancellation_key}
