"""Password-recovery delivery: SMTP in production, filesystem mailbox in development."""
import json
import os
import smtplib
import ssl
from datetime import timedelta
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import quote

from app.core.security import utcnow
from . import service


def local_mail_enabled():
    return service.option("ENVIRONMENT", "development") == "development" and service.truthy(service.option("LOCAL_MAIL_ENABLED", True))


def mailbox_path():
    # mail.py lives three levels below backend; keep the fallback at backend/.local-mail.
    directory = service.option("LOCAL_MAILBOX_DIR", str(Path(__file__).resolve().parents[3] / ".local-mail"))
    return (Path(directory) / "recovery.jsonl").resolve()


def deliver_recovery(email: str, token: str):
    base = str(service.option("FRONTEND_URL", "http://localhost:5173")).rstrip("/")
    link = base + "/?reset_token=" + quote(token)
    if service.option("SMTP_HOST", ""):
        message = EmailMessage()
        message["Subject"] = "Cero Colas · Recuperar contraseña"
        message["From"] = service.option("SMTP_FROM", "") or service.option("SMTP_USERNAME", "")
        message["To"] = email
        message.set_content("Solicitaste cambiar tu contraseña de Cero Colas. El enlace vence en 30 minutos y funciona una sola vez.\n\n" + link + "\n\nSi no hiciste esta solicitud, ignora este mensaje.")
        use_ssl = service.truthy(service.option("SMTP_SSL", False))
        smtp_class = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
        kwargs = {"context": ssl.create_default_context()} if use_ssl else {}
        with smtp_class(service.option("SMTP_HOST"), int(service.option("SMTP_PORT", 465 if use_ssl else 587)), timeout=10, **kwargs) as smtp:
            if not use_ssl and service.truthy(service.option("SMTP_STARTTLS", True)):
                smtp.starttls(context=ssl.create_default_context())
            if service.option("SMTP_USERNAME", ""):
                smtp.login(service.option("SMTP_USERNAME"), service.option("SMTP_PASSWORD", ""))
            smtp.send_message(message)
        return
    if not local_mail_enabled():
        raise RuntimeError("Recovery delivery is not configured")
    path = mailbox_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # This developer mailbox is a filesystem artifact, never an HTTP endpoint.
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"to": email, "url": link, "expires_at": (utcnow() + timedelta(minutes=30)).isoformat() + "Z"}, ensure_ascii=False) + "\n")
    if os.name != "nt":
        path.chmod(0o600)
