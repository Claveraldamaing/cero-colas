"""Behavioral tests use a disposable database, never the configured application DB."""

import json
import re
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import hash_password, hash_token, utcnow, verify_password
from app.p1 import auth
from app.p1.auth_models import P1Session, P1User


PASSWORD = "PrototipoSeguro123"


@pytest.fixture
def context(tmp_path, monkeypatch, isolated_engine):
    engine = isolated_engine
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    app = FastAPI()
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(auth.admin_router, prefix="/api/v1")

    def db_override():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = db_override
    original_option = auth.option
    overrides = {"COOKIE_SECURE": False, "ENVIRONMENT": "development", "LOCAL_MAIL_ENABLED": True, "LOCAL_MAILBOX_DIR": str(tmp_path), "SMTP_HOST": ""}
    monkeypatch.setattr(auth, "option", lambda key, default=None: overrides.get(key, original_option(key, default)))
    monkeypatch.setattr(auth, "forget_hospital_sessions", lambda ids: None)
    with TestClient(app) as client:
        yield client, factory, tmp_path
    engine.dispose()


def challenge(client):
    response = client.get("/api/v1/auth/challenge")
    assert response.status_code == 200
    data = response.json()
    numbers = [int(x) for x in re.findall(r"\d+", data["prompt"])]
    return {"challenge_id": data["challenge_id"], "challenge_answer": str(sum(numbers))}


def register(client, email="paciente@example.com"):
    return client.post("/api/v1/auth/register", json={"name": "Ana Paciente", "email": email, "password": PASSWORD, **challenge(client)})


def login(client, email="paciente@example.com", password=PASSWORD):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password, **challenge(client)})


def csrf(response):
    return {"X-CSRF-Token": response.json()["csrf_token"]}


def test_register_normalizes_account_and_never_stores_password_or_raw_session(context):
    client, factory, _ = context
    response = register(client, "  ANA@EXAMPLE.COM  ")
    assert response.status_code == 201
    assert response.json()["user"]["email"] == "ana@example.com"
    assert response.json()["user"]["role"] == "PACIENTE"
    assert "password_hash" not in response.json()["user"]
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie
    with factory() as db:
        user = db.query(P1User).one()
        session = db.query(P1Session).one()
        assert user.password_hash != PASSWORD and verify_password(PASSWORD, user.password_hash)
        assert session.token_hash == hash_token(client.cookies[auth.COOKIE_NAME])
        assert session.csrf_hash == hash_token(response.json()["csrf_token"])
    assert client.get("/api/v1/auth/me").json()["user"]["id"] == response.json()["user"]["id"]


def test_challenge_is_single_use_on_wrong_answer_and_expired_challenge_rejected(context):
    client, _, _ = context
    fields = challenge(client)
    body = {"email": "unknown@example.com", "password": PASSWORD, **fields}
    bad = client.post("/api/v1/auth/login", json={**body, "challenge_answer": "999"})
    assert bad.status_code == 400 and bad.json()["detail"]["code"] == "CHALLENGE_INVALID"
    retry = client.post("/api/v1/auth/login", json=body)
    assert retry.status_code == 400 and retry.json()["detail"]["code"] == "CHALLENGE_EXPIRED"


def test_profile_requires_csrf_and_cannot_escalate_role(context):
    client, _, _ = context
    response = register(client)
    assert client.patch("/api/v1/auth/profile", json={"name": "Ana Actualizada"}).status_code == 403
    assert client.patch("/api/v1/auth/profile", headers=csrf(response), json={"role": "ADMIN"}).status_code == 422
    updated = client.patch("/api/v1/auth/profile", headers=csrf(response), json={"name": "Ana Actualizada", "preferences": {"theme": "dark"}})
    assert updated.status_code == 200
    assert updated.json()["user"]["preferences"] == {"theme": "dark", "language": "es", "email_notifications": True}
    assert client.get("/api/v1/admin/users").status_code == 403


def test_logout_invalidates_cookie_session_even_if_replayed(context):
    client, _, _ = context
    response = register(client)
    token = client.cookies[auth.COOKIE_NAME]
    assert client.post("/api/v1/auth/logout", headers=csrf(response)).status_code == 200
    client.cookies.set(auth.COOKIE_NAME, token)
    assert client.get("/api/v1/auth/me").status_code == 401


def test_expired_session_is_rejected(context):
    client, factory, _ = context
    register(client)
    with factory() as db:
        db.query(P1Session).one().expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    assert client.get("/api/v1/auth/me").status_code == 401


@pytest.mark.parametrize("exists", [False, True])
def test_login_locks_unknown_and_existing_accounts_equally(context, exists):
    client, _, _ = context
    if exists:
        register(client)
    for _ in range(5):
        assert login(client, password="InvalidPassword1").status_code == 401
    response = login(client, password=PASSWORD)
    assert response.status_code == 429
    assert response.headers["retry-after"] == "900"


def test_change_password_rotates_session_and_revokes_all_old_sessions(context):
    client, factory, _ = context
    registered = register(client)
    old_token = client.cookies[auth.COOKIE_NAME]
    assert client.post("/api/v1/auth/change-password", headers=csrf(registered), json={"current_password": "Incorrect1", "new_password": "NuevaSegura123"}).status_code == 400
    response = client.post("/api/v1/auth/change-password", headers=csrf(registered), json={"current_password": PASSWORD, "new_password": "NuevaSegura123"})
    assert response.status_code == 200
    assert response.json()["csrf_token"] != registered.json()["csrf_token"]
    with factory() as db:
        assert db.query(P1Session).filter(P1Session.token_hash == hash_token(old_token)).one().revoked_at is not None
    assert login(client, password="NuevaSegura123").status_code == 200


def test_recovery_is_generic_single_use_and_revokes_sessions(context):
    client, _, directory = context
    register(client)
    old_token = client.cookies[auth.COOKIE_NAME]
    existing = client.post("/api/v1/auth/forgot-password", json={"email": "paciente@example.com", **challenge(client)})
    absent = client.post("/api/v1/auth/forgot-password", json={"email": "absent@example.com", **challenge(client)})
    assert existing.status_code == absent.status_code == 200
    assert existing.json() == absent.json()
    assert "token" not in existing.text and "url" not in existing.text
    item = json.loads((directory / "recovery.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    token = parse_qs(urlparse(item["url"]).query)["reset_token"][0]
    payload = {"token": token, "new_password": "RecuperadaSegura123"}
    assert client.post("/api/v1/auth/reset-password", json=payload).status_code == 200
    assert client.post("/api/v1/auth/reset-password", json=payload).status_code == 400
    client.cookies.set(auth.COOKIE_NAME, old_token)
    assert client.get("/api/v1/auth/me").status_code == 401
    client.cookies.clear()
    assert login(client, password="RecuperadaSegura123").status_code == 200


def test_admin_can_manage_accounts_and_cannot_remove_self(context):
    client, factory, _ = context
    patient_id = register(client).json()["user"]["id"]
    with factory() as db:
        admin = P1User(name="Operador", email="admin@example.com", password_hash=hash_password(PASSWORD), role="ADMIN", active=True)
        db.add(admin)
        db.commit()
        admin_id = admin.id
    logged = login(client, email="admin@example.com")
    assert logged.status_code == 200
    assert client.get("/api/v1/admin/users").json()["total"] == 2
    assert client.patch(f"/api/v1/admin/users/{admin_id}", json={"active": False}, headers=csrf(logged)).status_code == 409
    assert client.patch(f"/api/v1/admin/users/{patient_id}", json={"active": False}, headers=csrf(logged)).status_code == 200
    assert login(client).status_code == 401


def test_cross_origin_login_and_weak_password_are_rejected(context):
    client, _, _ = context
    payload = {"name": "Ana Paciente", "email": "ana@example.com", "password": "weak", **challenge(client)}
    assert client.post("/api/v1/auth/register", json=payload).status_code == 422
    payload.update(password=PASSWORD, **challenge(client))
    assert client.post("/api/v1/auth/register", headers={"Origin": "https://untrusted.invalid"}, json=payload).status_code == 403
