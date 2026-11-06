import re
from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.models import P1Session, P1User
from app.modules.auth.service import current_session, current_user, require_csrf
from . import service
from .schemas import AppointmentRequest

router = APIRouter(prefix="/reservations", tags=["P2 · Reservas"])


def validate_specialty_id(value: str):
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", value):
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_SPECIALTY", "message": "El identificador de especialidad no tiene un formato válido."},
        )
    return value


@router.get("/availability")
def availability(
    specialty_id: str = Query(min_length=1, max_length=100),
    month: str = Query(pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$"),
    session: P1Session = Depends(current_session),
):
    specialty_id = validate_specialty_id(specialty_id)
    return service.availability(session, quote(specialty_id, safe=""), month)


@router.get("/slots")
def slots(
    specialty_id: str = Query(min_length=1, max_length=100),
    selected_date: date = Query(alias="date"),
    session: P1Session = Depends(current_session),
):
    specialty_id = validate_specialty_id(specialty_id)
    return service.slots(session, quote(specialty_id, safe=""), selected_date)


@router.post("", status_code=201)
def reserve(
    data: AppointmentRequest,
    response: Response,
    session: P1Session = Depends(require_csrf),
    user: P1User = Depends(current_user),
    db: Session = Depends(get_db),
):
    result = service.reserve(db, session, user, data)
    response.headers["Cache-Control"] = "no-store"
    return result
