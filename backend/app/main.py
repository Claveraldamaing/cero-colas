from contextlib import asynccontextmanager
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from app.api.router import api_router
from app.core.config import settings
from app.core.database import engine

@asynccontextmanager
async def lifespan(app):
    from app.db.migrate import migrate
    migrate()
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
)
audit_logger = logging.getLogger('cerocolas.hospital')
audit_logger.setLevel(logging.INFO)
if not audit_logger.handlers:
    audit_logger.addHandler(logging.StreamHandler())
audit_logger.propagate = False
app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS,
                allow_credentials=True, allow_methods=['GET', 'POST', 'PATCH', 'DELETE'],
                allow_headers=['Content-Type', 'X-CSRF-Token'])
app.include_router(api_router, prefix=settings.API_V1_PREFIX)

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
        return {'status': 'healthy', 'database': engine.dialect.name, 'module': 'P1+P2', 'hospital_mode': settings.HOSPITAL_MODE}
    except Exception:
        return JSONResponse(status_code=503, content={'status': 'unavailable', 'database': 'unavailable'})

dist = Path(__file__).resolve().parents[2] / 'frontend' / 'dist'
if dist.is_dir() and (dist / 'assets').is_dir():
    app.mount('/assets', StaticFiles(directory=dist / 'assets'), name='assets')
    @app.get('/')
    def frontend():
        return FileResponse(dist / 'index.html')
