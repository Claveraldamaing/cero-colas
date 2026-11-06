from pathlib import Path
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # core/config.py lives two levels below backend; keep .env at backend/.env.
    model_config = SettingsConfigDict(env_file=Path(__file__).resolve().parents[2] / '.env', extra='ignore')
    PROJECT_NAME: str = 'Cero Colas · Portal P1'
    VERSION: str = '2.0.0'
    API_V1_PREFIX: str = '/api/v1'
    ENVIRONMENT: str = 'development'
    DATABASE_URL: str = 'postgresql+psycopg2://cerocolas:change-me@127.0.0.1:55432/cerocolas_p1'
    CORS_ORIGINS: list[str] = ['http://localhost:5173', 'http://127.0.0.1:5173']
    SESSION_TTL_SECONDS: int = Field(default=28800, ge=300, le=86400)
    COOKIE_SECURE: bool = False
    HOSPITAL_API_BASE_URL: str = 'http://127.0.0.1:4010'
    HOSPITAL_MODE: str = 'simulator'
    HOSPITAL_CLIENT_ID: str = 'simulator'
    HOSPITAL_CLIENT_SECRET: str = ''
    HOSPITAL_API_TIMEOUT_SECONDS: float = 15.0
    HOSPITAL_PRIVACY_POLICY_TEXT: str = ''
    HOSPITAL_PRIVACY_POLICY_APPROVED: bool = False
    REFERENCE_MAX_AGE_DAYS: int | None = Field(default=None, ge=1)
    CITA_ENCRYPTION_KEY: str = ''
    SURVEY_MIN_SCORE: int = 1
    SURVEY_MAX_SCORE: int = 5
    SMTP_HOST: str = ''
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ''
    SMTP_PASSWORD: str = ''
    SMTP_FROM: str = ''
    SMTP_STARTTLS: bool = True
    FRONTEND_URL: str = 'http://127.0.0.1:5173'
    LOCAL_MAILBOX_DIR: str = str(Path(__file__).resolve().parents[2] / '.local' / 'mailbox')

    @model_validator(mode='after')
    def production_requirements(self):
        if self.HOSPITAL_MODE not in {'simulator', 'hospital'}:
            raise ValueError('HOSPITAL_MODE debe ser simulator o hospital.')
        if self.ENVIRONMENT == 'production':
            if not self.COOKIE_SECURE or not self.FRONTEND_URL.startswith('https://'):
                raise ValueError('Producción requiere cookies seguras y FRONTEND_URL HTTPS.')
            if not self.DATABASE_URL.startswith('postgresql'):
                raise ValueError('Producción requiere PostgreSQL.')
            if not self.SMTP_HOST:
                raise ValueError('Producción requiere SMTP para recuperación de cuentas.')
        return self


settings = Settings()
