"""HTTP routes for portal identity, eligibility and patient dashboard."""
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.models import P1Session, P1User
from app.modules.auth.service import current_session, current_user, require_csrf
from . import service
from .schemas import IdentificationInput

router = APIRouter(prefix="/portal", tags=["P1 · Portal"])


@router.get("/policies")
def policies(user: P1User = Depends(current_user)):
    return service.policies()


@router.post("/identify")
def identify(data: IdentificationInput, request: Request, session: P1Session = Depends(require_csrf), db: Session = Depends(get_db)):
    return service.identify(session, request, data, db)


@router.get("/eligibility")
def eligibility(refresh: bool = Query(default=False), session: P1Session = Depends(current_session), db: Session = Depends(get_db)):
    return service.eligibility(session, db, refresh)


@router.delete("/identity")
def clear_identity(session: P1Session = Depends(require_csrf)):
    return service.clear_identity(session)


@router.get("/dashboard")
def patient_dashboard(session: P1Session = Depends(current_session), db: Session = Depends(get_db)):
    return service.dashboard(session, db)
