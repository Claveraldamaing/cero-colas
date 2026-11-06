"""Contract/security tests using explicit synthetic fixtures, never a real hospital."""
import copy
import json
import re
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import Base, get_db
from app.integrations import hospital
from app.integrations.hospital import HospitalClient, HospitalError
from app.modules.admin.router import portal_dashboard_router
from app.modules.auth import router as auth_router
from app.modules.auth.models import P1Session, P1User
from app.modules.portal import router as portal_router
from app.modules.portal import service as portal_service
from app.modules.reservations import router as reservations_router
from app.modules.reservations import service as reservations_service
from app.modules.reservations.models import AppointmentInstruction, LocalAppointment
from app.modules.surveys import router as surveys_router
from app.modules.surveys.models import P1Survey, P1UsageEvent


def sample_eligibility():
    return {"elegible": True, "motivos": [], "condicion": "CONTINUADOR", "sis": {"estado": "VIGENTE", "verificado_en": "2026-10-20T12:00:00-05:00"}, "proxima_reserva_desde": None, "referencias": [{"referencia_id": "test-ref", "numero": "TEST-001", "estado": "ACEPTADA", "fecha_envio": datetime.now(hospital.LIMA).date().isoformat(), "establecimiento_origen": "Establecimiento de prueba", "especialidad_destino": {"codigo": "test-up", "nombre": "Prueba"}, "especialidades_coincidentes": ["test-specialty"]}], "especialidades": [{"especialidad_id": "test-specialty", "nombre": "Especialidad de prueba", "referencias": ["test-ref"]}]}


@pytest.fixture
def setup(monkeypatch, isolated_engine):
    engine = isolated_engine
    tables = [table for table in Base.metadata.sorted_tables if table.name.startswith("p1_") or table.name in {"cita_local", "cita_indicacion", "auditoria_api"}]
    Base.metadata.create_all(engine, tables=tables)
    factory = sessionmaker(bind=engine)

    def db_dependency():
        with factory() as db:
            yield db

    state = {"requests": [], "eligibility": sample_eligibility(), "error": None, "created_appointment": None}

    def transport(request):
        state["requests"].append(request)
        path = request.url.path
        if state["error"] and path == state["error"][0]:
            return httpx.Response(state["error"][1], json=state["error"][2], headers=state["error"][3] if len(state["error"]) > 3 else {})
        if path == "/oauth/token":
            return httpx.Response(200, json={"access_token": "TEST-CLIENT-SECRET-TOKEN", "token_type": "Bearer", "expires_in": 900, "scope": "portal.leer portal.citar"})
        if path == "/pacientes/identificacion":
            return httpx.Response(200, json={"paciente_token": "TEST-PATIENT-SECRET-TOKEN", "expira_en": 900, "paciente": {"nombre_enmascarado": "PA** PR***", "edad": 40}, "undocumented_secret": "must-not-leak"})
        if path == "/elegibilidad":
            return httpx.Response(200, json=state["eligibility"])
        if path.endswith("/disponibilidad"):
            tomorrow = (datetime.now(hospital.LIMA).date() + timedelta(days=1)).isoformat()
            return httpx.Response(200, json={"datos": [{"fecha": tomorrow, "cupos_libres": 2}]})
        if path.endswith("/cupos"):
            tomorrow = (datetime.now(hospital.LIMA).date() + timedelta(days=1)).isoformat()
            return httpx.Response(200, json={"datos": [{"cupo_id": "TEST-SLOT", "fecha": tomorrow, "hora_inicio": "10:00", "hora_fin": "10:30", "consultorio": "Consultorio de prueba", "medico": "Doctora de prueba"}]})
        if path == "/citas" and request.method == "POST":
            tomorrow = (datetime.now(hospital.LIMA).date() + timedelta(days=1)).isoformat()
            state["created_appointment"] = {"codigo_cita": "TEST-BOOKING", "estado": "RESERVADA", "canal": "EN_LINEA", "fecha": tomorrow, "hora_inicio": "10:00", "hora_fin": "10:30", "especialidad": "Prueba", "consultorio": "Consultorio de prueba", "medico": "Doctora de prueba", "financiamiento": "SIS", "indicaciones": ["Traer documento de identidad."], "anulable_hasta": None, "clave_anulacion": "AB12CD"}
            return httpx.Response(201, json=state["created_appointment"])
        if path == "/citas":
            tomorrow = (datetime.now(hospital.LIMA).date() + timedelta(days=1)).isoformat()
            return httpx.Response(200, json={"datos": [{"codigo_cita": "TEST-CITA", "estado": "RESERVADA", "canal": "EN_LINEA", "fecha": tomorrow, "hora_inicio": "10:00", "hora_fin": "10:30", "especialidad": "Prueba", "consultorio": "Prueba", "medico": "Prueba", "financiamiento": "SIS", "indicaciones": [], "anulable_hasta": None}]})
        if path == "/salud":
            return httpx.Response(200, json={"canal_abierto": True, "verificacion_sis": "DISPONIBLE", "hora_servidor": "2026-10-20T12:00:00-05:00"})
        if path == "/politicas":
            return httpx.Response(200, json={"ventana": {"desde": "2026-10-21", "hasta": "2026-11-30"}, "reservas_por_dia": 1, "dias_entre_reservas": 2, "horas_minimas_para_anular": 24, "intentos_identificacion": 5, "sesion_paciente_segundos": 900})
        raise AssertionError(f"Unexpected test request {path}")

    config = SimpleNamespace(HOSPITAL_MODE="simulator", HOSPITAL_API_BASE_URL="http://127.0.0.1:4010", HOSPITAL_CLIENT_ID="test-client", HOSPITAL_CLIENT_SECRET="test-secret", HOSPITAL_API_TIMEOUT_SECONDS=1, REFERENCE_MAX_AGE_DAYS=None)
    service = HospitalClient(config, httpx.MockTransport(transport))
    monkeypatch.setattr(portal_service, "hospital_client", service)
    monkeypatch.setattr(reservations_service, "hospital_client", service)
    monkeypatch.setattr(hospital, "hospital_client", service)
    monkeypatch.setattr(settings, "COOKIE_SECURE", False)
    monkeypatch.setattr(settings, "HOSPITAL_PRIVACY_POLICY_APPROVED", False)
    monkeypatch.setattr(settings, "HOSPITAL_PRIVACY_POLICY_TEXT", "")
    monkeypatch.setattr(settings, "CITA_ENCRYPTION_KEY", "")
    app = FastAPI()
    app.include_router(auth_router.router, prefix="/api/v1")
    app.include_router(portal_router.router, prefix="/api/v1")
    app.include_router(reservations_router.router, prefix="/api/v1")
    app.include_router(surveys_router.router, prefix="/api/v1")
    app.include_router(portal_dashboard_router, prefix="/api/v1")
    app.dependency_overrides[get_db] = db_dependency
    with TestClient(app) as client:
        challenge = solve_challenge(client)
        result = client.post("/api/v1/auth/register", json={"name": "Usuario Prueba", "email": "test@example.test", "password": "ClavePrueba123!", **challenge})
        assert result.status_code == 201, result.text
        client.headers["X-CSRF-Token"] = result.json()["csrf_token"]
        yield SimpleNamespace(client=client, service=service, state=state, factory=factory, engine=engine, app=app)
    engine.dispose()


def solve_challenge(client):
    challenge = client.get("/api/v1/auth/challenge").json()
    numbers = re.findall(r"\d+", challenge["prompt"])
    return {"challenge_id": challenge["challenge_id"], "challenge_answer": str(sum(map(int, numbers)))}


def identify(test):
    return test.client.post("/api/v1/portal/identify", json={"numero_documento": "12345678", "fecha_nacimiento": "1986-01-01", "consent": True, **solve_challenge(test.client)})


def session_id(test):
    with test.factory() as db:
        return db.query(P1Session).first().id


def test_identity_backend_only_and_no_persisted_identifiers(setup):
    result = identify(setup)
    assert result.status_code == 200
    assert result.json()["identity"]["identified"] is True
    assert "TEST-PATIENT-SECRET-TOKEN" not in result.text
    assert "TEST-CLIENT-SECRET-TOKEN" not in result.text
    assert "12345678" not in result.text
    assert "undocumented_secret" not in result.text
    request = next(r for r in setup.state["requests"] if r.url.path == "/pacientes/identificacion")
    assert json.loads(request.content)["tipo_documento"] == "DNI"
    assert request.headers["X-Usuario-IP"] == "testclient"
    assert request.headers["X-Request-Id"]
    for table in inspect(setup.engine).get_table_names():
        assert not any(any(term in col["name"] for term in ("dni", "nacimiento", "paciente_token")) for col in inspect(setup.engine).get_columns(table))


def test_identity_requires_auth_csrf_and_consent(setup):
    setup.client.headers.pop("X-CSRF-Token")
    assert identify(setup).status_code == 403
    setup.client.cookies.clear()
    assert setup.client.get("/api/v1/portal/dashboard").status_code == 401
    assert setup.state["requests"] == []


def test_identification_uses_real_request_ip_not_untrusted_forwarded_header(setup):
    setup.client.headers["X-Forwarded-For"] = "203.0.113.66"
    assert identify(setup).status_code == 200
    request = next(r for r in setup.state["requests"] if r.url.path == "/pacientes/identificacion")
    assert request.headers["X-Usuario-IP"] == "testclient"


def test_cached_eligibility_marks_simulator_override_without_claiming_real_validity(setup):
    assert identify(setup).status_code == 200
    first = setup.client.get("/api/v1/portal/eligibility").json()["eligibility"]
    second = setup.client.get("/api/v1/portal/eligibility").json()["eligibility"]
    assert first == second
    assert first["elegible"] is True
    assert first["reference_policy_pending"] is True
    assert first["reservation_simulation"] is True
    assert first["reserve_ready"] is True
    assert first["referencias"][0]["validity"] == "simulator_only"
    assert "No es una reserva real" in first["reason_messages"][-1]["message"]
    assert first["specialties_allowed"][0]["especialidad_id"] == "test-specialty"
    assert sum(r.url.path == "/elegibilidad" for r in setup.state["requests"]) == 1
    with setup.factory() as db:
        assert db.query(P1UsageEvent).count() == 1


def test_configured_reference_rule_filters_expired_and_mismatched(setup):
    setup.service.config.REFERENCE_MAX_AGE_DAYS = 30
    payload = sample_eligibility()
    assert setup.service.evaluate_references(payload)["reserve_ready"] is True
    payload["referencias"][0]["fecha_envio"] = (datetime.now(hospital.LIMA).date() - timedelta(days=31)).isoformat()
    assert setup.service.evaluate_references(payload)["reserve_ready"] is False
    payload = sample_eligibility()
    payload["referencias"][0]["especialidades_coincidentes"] = ["another-specialty"]
    assert setup.service.evaluate_references(payload)["reserve_ready"] is False


def test_unknown_eligibility_reason_is_tolerated_and_blocks_reserve(setup):
    setup.service.config.REFERENCE_MAX_AGE_DAYS = 30
    payload = sample_eligibility()
    payload["motivos"] = ["FUTURE_HOSPITAL_REASON"]
    result = setup.service.evaluate_references(payload)
    assert result["reserve_ready"] is False
    assert result["reason_messages"][0]["code"] == "FUTURE_HOSPITAL_REASON"


def test_identity_expiration_and_logout_clear_hospital_memory(setup):
    assert identify(setup).status_code == 200
    identity = setup.service.identity(session_id(setup))
    identity.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    response = setup.client.get("/api/v1/portal/eligibility")
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "SESION_PACIENTE_INVALIDA"
    assert identify(setup).status_code == 200
    assert setup.client.post("/api/v1/auth/logout").status_code == 200
    assert setup.service._identities == {}


def test_hospital_error_has_no_fake_success_and_unknown_errors_safe(setup):
    setup.state["error"] = ("/pacientes/identificacion", 503, {"codigo": "NEW_INTERNAL_CODE", "mensaje": "sensitive hospital internals", "rastreo": "test-trace"})
    response = identify(setup)
    assert response.status_code == 503
    assert response.json()["detail"]["rastreo"] == "test-trace"
    assert "sensitive hospital internals" not in response.text
    assert setup.service._identities == {}


def test_identity_blocked_preserves_retry_after(setup):
    setup.state["error"] = ("/pacientes/identificacion", 423, {"codigo": "IDENTIDAD_BLOQUEADA", "rastreo": "blocked"}, {"Retry-After": "1800"})
    response = identify(setup)
    assert response.status_code == 423
    assert response.headers["Retry-After"] == "1800"


def test_network_failure_is_explicit(setup):
    def broken(request):
        raise httpx.ConnectError("test network failure")
    setup.service.transport = httpx.MockTransport(broken)
    response = identify(setup)
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "SERVICIO_NO_DISPONIBLE"


def test_patient_dashboard_surveys_and_real_admin_aggregates(setup):
    assert setup.client.post("/api/v1/portal/surveys", json={"ease_score": 4, "satisfaction_score": 5}).status_code == 409
    assert identify(setup).status_code == 200
    dashboard = setup.client.get("/api/v1/portal/dashboard").json()
    assert dashboard["next_appointment"]["codigo_cita"] == "TEST-CITA"
    assert dashboard["notifications"] == {"integrated": False, "items": []}
    assert dashboard["survey"]["eligible"] is True
    payload = {"ease_score": 4, "satisfaction_score": 5, "comment": "La navegación fue clara."}
    assert setup.client.post("/api/v1/portal/surveys", json=payload).status_code == 201
    assert setup.client.post("/api/v1/portal/surveys", json=payload).status_code == 409
    status = setup.client.get("/api/v1/portal/surveys/status").json()
    assert status["submitted"] is True and status["eligible"] is False
    assert setup.client.get("/api/v1/portal/admin/dashboard").status_code == 403
    with setup.factory() as db:
        db.query(P1User).first().role = "ADMIN"
        db.commit()
        assert db.query(P1Survey).count() == 1
    admin = setup.client.get("/api/v1/portal/admin/dashboard").json()
    assert admin["users"] == {"total": 1, "active": 1, "inactive": 0, "admins": 1}
    assert admin["survey"]["responses"] == 1
    assert admin["survey"]["average_ease"] == 4
    assert admin["survey"]["average_satisfaction"] == 5
    assert admin["metrics"] == {"reservations": 0, "cancellations": 0, "tickets": None, "chatbot": None}
    assert admin["service"]["canal_abierto"] is True


def test_patients_cannot_read_each_others_hospital_identity(setup):
    assert identify(setup).status_code == 200
    with TestClient(setup.app) as other:
        result = other.post("/api/v1/auth/register", json={"name": "Otro Usuario", "email": "other@example.test", "password": "ClavePrueba123!", **solve_challenge(other)})
        assert result.status_code == 201
        dashboard = other.get("/api/v1/portal/dashboard").json()
        assert dashboard["identity"] == {"identified": False}
        assert dashboard["next_appointment"] is None
        assert other.get("/api/v1/portal/eligibility").status_code == 401


def test_identification_with_real_service_requires_approved_policy(setup):
    setup.service.config.HOSPITAL_MODE = "hospital"
    response = identify(setup)
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "PRIVACY_POLICY_PENDING"
    assert setup.state["requests"] == []


def test_local_identification_limit_20_attempts_per_ip(setup):
    for _ in range(20):
        setup.service.limit_identification("test-ip")
    with pytest.raises(HospitalError) as exc:
        setup.service.limit_identification("test-ip")
    assert exc.value.status == 429


def test_oauth_is_renewed_only_once_for_authorization_error(setup):
    setup.state["error"] = ("/pacientes/identificacion", 401, {"codigo": "NO_AUTORIZADO", "rastreo": "auth-test"})
    response = identify(setup)
    assert response.status_code == 401
    assert sum(r.url.path == "/oauth/token" for r in setup.state["requests"]) == 2
    assert sum(r.url.path == "/pacientes/identificacion" for r in setup.state["requests"]) == 2


def test_local_simulator_allows_reservations_without_reference_age_rule(setup):
    assert identify(setup).status_code == 200
    eligibility = setup.client.get("/api/v1/portal/eligibility").json()["eligibility"]
    assert eligibility["reference_policy_pending"] is True
    assert eligibility["reservation_simulation"] is True
    assert eligibility["reserve_ready"] is True
    assert eligibility["specialties_allowed"][0]["especialidad_id"] == "test-specialty"

    response = setup.client.get(
        "/api/v1/reservations/availability",
        params={"specialty_id": "test-specialty", "month": "2026-11"},
    )
    assert response.status_code == 200
    assert response.json()["items"]


def test_hospital_mode_still_blocks_until_reference_policy_is_configured(setup):
    from app.integrations.hospital.policy import evaluate_references

    config = SimpleNamespace(
        HOSPITAL_MODE="hospital",
        HOSPITAL_API_BASE_URL="https://hospital.example.test",
        REFERENCE_MAX_AGE_DAYS=None,
    )
    eligibility = evaluate_references(sample_eligibility(), config)
    assert eligibility["reference_policy_pending"] is True
    assert eligibility["reservation_simulation"] is False
    assert eligibility["reserve_ready"] is False
    assert eligibility["specialties_allowed"] == []


def test_booking_flow_uses_authenticated_user_and_persists_idempotently(setup, monkeypatch):
    from cryptography.fernet import Fernet

    monkeypatch.setattr(settings, "CITA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    assert identify(setup).status_code == 200
    eligibility = setup.client.get("/api/v1/portal/eligibility").json()["eligibility"]
    assert eligibility["reserve_ready"] is True
    assert eligibility["reservation_simulation"] is True
    today = datetime.now(hospital.LIMA).date()
    tomorrow = (today + timedelta(days=1)).isoformat()

    availability = setup.client.get(
        "/api/v1/reservations/availability",
        params={"specialty_id": "test-specialty", "month": today.strftime("%Y-%m")},
    )
    assert availability.status_code == 200, availability.text
    assert availability.json()["items"] == [{"date": tomorrow, "available_slots": 2}]

    slots = setup.client.get(
        "/api/v1/reservations/slots",
        params={"specialty_id": "test-specialty", "date": tomorrow},
    )
    assert slots.status_code == 200, slots.text
    assert slots.json()["items"][0]["slot_id"] == "TEST-SLOT"

    payload = {
        "specialty_id": "test-specialty",
        "slot_id": "TEST-SLOT",
        "reference_id": "test-ref",
        "contact_phone": "987654321",
        "idempotency_key": "test-idempotency-key",
    }
    created = setup.client.post("/api/v1/reservations", json=payload)
    assert created.status_code == 201, created.text
    assert created.json()["cita"]["codigo_cita"] == "TEST-BOOKING"
    assert created.json()["clave_anulacion"] == "AB12CD"
    assert "AB12CD" not in setup.state["created_appointment"].get("clave_anulacion_cifrada", "")

    replay = setup.client.post("/api/v1/reservations", json=payload)
    assert replay.status_code == 201
    assert replay.json() == created.json()
    conflicting_replay = setup.client.post(
        "/api/v1/reservations",
        json={**payload, "slot_id": "DIFFERENT-SLOT"},
    )
    assert conflicting_replay.status_code == 409
    assert conflicting_replay.json()["detail"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert sum(request.url.path == "/citas" and request.method == "POST" for request in setup.state["requests"]) == 1
    with setup.factory() as db:
        appointment = db.query(LocalAppointment).one()
        assert appointment.codigo_cita == "TEST-BOOKING"
        assert appointment.id_usuario == db.query(P1User).one().id
        assert appointment.clave_anulacion_cifrada != "AB12CD"
        assert db.query(AppointmentInstruction).one().descripcion == "Traer documento de identidad."
