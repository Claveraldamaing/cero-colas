"""HTTP routes for administrative account management."""
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.models import P1User
from app.modules.auth.service import require_admin, require_csrf
from . import service
from .schemas import AccountInput

router = APIRouter(prefix="/admin", tags=["P1 · Administración de usuarios"])


@router.get("/users")
def list_users(response: Response, user: P1User = Depends(require_admin), db: Session = Depends(get_db), offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), q: str = Query("", max_length=120)):
    items, total = service.list_accounts(db, q, offset, limit)
    response.headers["Cache-Control"] = "no-store"
    return {"items": items, "total": total, "offset": offset, "limit": limit}


@router.patch("/users/{user_id}", dependencies=[Depends(require_csrf)])
def update_account(user_id: str, payload: AccountInput, user: P1User = Depends(require_admin), db: Session = Depends(get_db)):
    return service.update_account(db, user, user_id, payload)
