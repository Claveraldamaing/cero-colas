"""Central registration of P1 API routers."""
from fastapi import APIRouter

from app.modules.admin.router import portal_dashboard_router, router as admin_router
from app.modules.auth.router import router as auth_router
from app.modules.portal.router import router as portal_router
from app.modules.surveys.router import router as surveys_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(admin_router)
api_router.include_router(portal_router)
api_router.include_router(surveys_router)
api_router.include_router(portal_dashboard_router)
