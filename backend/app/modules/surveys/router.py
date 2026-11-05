"""HTTP routes for local usage feedback and satisfaction surveys."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.models import P1Session
from app.modules.auth.service import current_session, require_csrf
from . import service
from .schemas import SurveyInput

router = APIRouter(prefix="/portal", tags=["P1 · Encuestas"])


@router.get("/surveys/status")
def survey_status(session: P1Session = Depends(current_session), db: Session = Depends(get_db)):
    return service.feedback_status(db, session)


@router.post("/surveys", status_code=201)
def submit_survey(data: SurveyInput, session: P1Session = Depends(require_csrf), db: Session = Depends(get_db)):
    return service.submit_survey(db, session, data)
