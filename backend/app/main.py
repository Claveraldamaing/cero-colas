from contextlib import asynccontextmanager
from pathlib import Path
import logging
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from app.core.config import settings
from app.core.database import engine

@asynccontextmanager
async def lifespan(app):
    from app.migrate import migrate
    migrate()
    yield

app = FastAPI(title=settings.PROJECT_NAME, version=settings.VERSION, lifespan=lifespan)
audit_logger = logging.getLogger('cerocolas.hospital')
audit_logger.setLevel(logging.INFO)
if not audit_logger.handlers:
    audit_logger.addHandler(logging.StreamHandler())
audit_logger.propagate = False
app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS,
                   allow_credentials=True, allow_methods=['GET', 'POST', 'PATCH', 'DELETE'],
                   allow_headers=['Content-Type', 'X-CSRF-Token'])

@app.exception_handler(RequestValidationError)
async def invalid_request(request, exc):
    # Pydantic's default errors include submitted input. Never echo passwords or identity.
    return JSONResponse(status_code=422, content={'detail': [
        {'loc': list(error['loc']), 'msg': error['msg'], 'type': error['type']}
        for error in exc.errors()
    ]})

@app.middleware('http')
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'same-origin'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    if request.url.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store'
    if settings.ENVIRONMENT == 'production':
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    return response

@app.get('/api/v1/health')
def health():
    try:
        with engine.connect() as connection:
            connection.execute(text('SELECT 1'))
        return {'status': 'healthy', 'database': engine.dialect.name, 'module': 'P1', 'hospital_mode': settings.HOSPITAL_MODE}
    except Exception:
        return JSONResponse(status_code=503, content={'status': 'unavailable', 'database': 'unavailable'})

from app.modules.admin.router import portal_dashboard_router, router as admin_router
from app.modules.auth.router import router as auth_router
from app.modules.portal.router import router as portal_router
from app.modules.surveys.router import router as surveys_router
app.include_router(auth_router, prefix=settings.API_V1_PREFIX)
app.include_router(admin_router, prefix=settings.API_V1_PREFIX)
app.include_router(portal_router, prefix=settings.API_V1_PREFIX)
app.include_router(surveys_router, prefix=settings.API_V1_PREFIX)
app.include_router(portal_dashboard_router, prefix=settings.API_V1_PREFIX)

# Las rutas del prototipo anterior no se exponen: no tienen autenticación
# y sus datos ficticios no deben confundirse con operaciones hospitalarias.
dist = Path(__file__).resolve().parents[2] / 'frontend' / 'dist'
if dist.is_dir() and (dist / 'assets').is_dir():
    app.mount('/assets', StaticFiles(directory=dist / 'assets'), name='assets')
    @app.get('/')
    def frontend():
        return FileResponse(dist / 'index.html')
