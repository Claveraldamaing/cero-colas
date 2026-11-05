"""Local operator commands for P1 accounts and the development mailbox."""
import argparse
import getpass
import json

from app.core.database import Base, SessionLocal, engine
from app.core.security import hash_password, password_problem
from app.modules.auth import mail
from app.modules.auth.models import P1User, default_preferences
from app.modules.auth.schemas import normalize_email


def operator_cli():
    parser = argparse.ArgumentParser(description="Administración local de cuentas P1")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create-admin", help="Crear un administrador sin contraseña predeterminada")
    create.add_argument("--email", required=True)
    create.add_argument("--name", required=True)
    sub.add_parser("local-mail", help="Consultar el último enlace del buzón local de desarrollo")
    args = parser.parse_args()
    if args.command == "local-mail":
        if not mail.local_mail_enabled():
            parser.error("El buzón local solo está disponible en desarrollo.")
        path = mail.mailbox_path()
        if not path.exists() or not path.read_text(encoding="utf-8").strip():
            print("El buzón local no contiene solicitudes.")
            return
        item = json.loads(path.read_text(encoding="utf-8").splitlines()[-1])
        print("Para:", item["to"], "\nVence:", item["expires_at"], "\nEnlace:", item["url"])
        return
    try:
        email = normalize_email(args.email)
    except ValueError as exc:
        parser.error(str(exc))
    name = " ".join(args.name.split())
    if not 2 <= len(name) <= 120:
        parser.error("El nombre debe tener entre 2 y 120 caracteres.")
    password = getpass.getpass("Contraseña del administrador: ")
    issue = password_problem(password)
    if issue:
        parser.error(issue)
    if password != getpass.getpass("Repite la contraseña: "):
        parser.error("Las contraseñas no coinciden.")
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        if db.query(P1User).filter(P1User.email == email).first():
            parser.error("El correo ya está registrado. No se modificó la cuenta existente.")
        db.add(P1User(name=name, email=email, password_hash=hash_password(password), role="ADMIN", active=True, preferences=default_preferences()))
        db.commit()
    print("Administrador creado. Ya puede iniciar sesión.")


if __name__ == "__main__":
    operator_cli()
