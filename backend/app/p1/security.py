"""Small, explicit security primitives; no credentials are stored in clear text."""

import base64
import hashlib
import hmac
import re
import secrets
from datetime import datetime, timezone


def utcnow():
    # All database timestamps are UTC. Naive UTC also round-trips through SQLite.
    return datetime.now(timezone.utc).replace(tzinfo=None)


def hash_token(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def new_token() -> str:
    return secrets.token_urlsafe(48)


def csrf_for_token(token: str) -> str:
    return hmac.new(token.encode(), b"cerocolas:csrf:v1", hashlib.sha256).hexdigest()


def password_problem(password: str):
    if not 10 <= len(password) <= 128:
        return "La contraseña debe tener entre 10 y 128 caracteres."
    if not (re.search(r"[a-z]", password) and re.search(r"[A-Z]", password) and re.search(r"\d", password)):
        return "Incluye al menos una mayúscula, una minúscula y un número."
    return None


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=16384, r=8, p=1, dklen=32)
    return "scrypt$16384$8$1$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(digest).decode()


def verify_password(password: str, stored: str) -> bool:
    try:
        method, n, r, p, salt, expected = stored.split("$")
        if method != "scrypt" or (int(n), int(r), int(p)) != (16384, 8, 1):
            return False
        digest = hashlib.scrypt(password.encode("utf-8"), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(digest, base64.b64decode(expected))
    except (TypeError, ValueError):
        return False


# Used for unknown emails so invalid-password work is equivalent for existing accounts.
DUMMY_PASSWORD_HASH = hash_password(new_token())
