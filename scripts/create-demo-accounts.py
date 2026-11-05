"""Create two explicit local demonstration accounts; passwords never go to stdout."""
from pathlib import Path
import json
import secrets
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.migrate import migrate
from app.modules.auth.models import P1User

if settings.ENVIRONMENT != 'development' or settings.HOSPITAL_MODE != 'simulator':
    raise SystemExit('Solo se permiten cuentas de demostración en desarrollo con simulador.')
migrate()
output = ROOT / '.local' / 'demo-accounts.json'
if output.exists():
    print('Ya existe el archivo local de accesos. No se cambiaron contraseñas.')
    raise SystemExit(0)
accounts = []
with SessionLocal() as db:
    for role, email, name in [('ADMIN', 'admin@cerocolas.test', 'Administrador de prueba'), ('PACIENTE', 'paciente@cerocolas.test', 'Paciente de prueba')]:
        if db.query(P1User).filter_by(email=email).first():
            raise SystemExit('La cuenta de prueba ya existe. Usa recuperación; no se sobrescribirá.')
        password = 'Cc1!' + secrets.token_urlsafe(16)
        db.add(P1User(email=email, name=name, role=role, password_hash=hash_password(password)))
        accounts.append({'email': email, 'password': password, 'role': role})
    db.commit()
output.parent.mkdir(exist_ok=True)
output.write_text(json.dumps(accounts, indent=2), encoding='utf-8')
(output.parent / 'ACCESOS.md').write_text('# Accesos locales de demostración\n\nSolo para el simulador académico. No compartir este archivo.\n\nPortal: http://127.0.0.1:5173\n\n' + '\n\n'.join(f"**{a['role']}**\n\nCorreo: `{a['email']}`\n\nContraseña: `{a['password']}`" for a in accounts) + '\n\nIdentificación de prueba del contrato: DNI `40123456`, nacimiento `1985-03-14`. Prism devuelve ejemplos; no valida identidad real.\n', encoding='utf-8')
print('Cuentas de demostración creadas. Accesos guardados en .local/ACCESOS.md.')
