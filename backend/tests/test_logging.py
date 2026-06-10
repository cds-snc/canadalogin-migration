import pytest
import logging
import json

from app.auth.services.auth_user_session import get_users_current_session
from app.main import app
from app.utils.auth_flow_logging import hash_identifier, log_auth_flow_event
from app.utils.correlation_id import (
    bind_attempt_id,
    bind_correlation_id,
    reset_attempt_id,
    reset_correlation_id,
)
from fastapi.testclient import TestClient
from fastapi import HTTPException, status
from fastapi.routing import APIRoute

client = TestClient(app)


def override_health_endpoint(monkeypatch, new_endpoint):
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path == "/health":
            monkeypatch.setattr(route, "endpoint", new_endpoint, raising=True)
            monkeypatch.setattr(route.dependant, "call", new_endpoint, raising=True)
            return
    raise AssertionError("/health route not found")


@pytest.mark.asyncio
async def test_log_status_400(monkeypatch, caplog):
    caplog.set_level(logging.WARNING)

    def mock_auth_user_session():
        return {}

    app.dependency_overrides[get_users_current_session] = mock_auth_user_session

    def mock_400(*args, **kwargs):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Bad Request"
        )

    override_health_endpoint(monkeypatch, mock_400)

    client.get("/health")

    record = caplog.records[0]
    log_json = json.loads(record.message)
    assert log_json["level"] == "WARNING"
    assert log_json["context"]["response"]["status_code"] == 400


@pytest.mark.asyncio
async def test_log_status_500(monkeypatch, caplog):
    caplog.set_level(logging.WARNING)

    def mock_auth_user_session():
        return {}

    app.dependency_overrides[get_users_current_session] = mock_auth_user_session

    def mock_500(*args, **kwargs):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal Server Erroer",
        )

    override_health_endpoint(monkeypatch, mock_500)

    client.get("/health")

    record = caplog.records[0]
    log_json = json.loads(record.message)
    assert log_json["level"] == "ERROR"
    assert log_json["context"]["response"]["status_code"] == 500


@pytest.mark.asyncio
async def test_log_request_get(monkeypatch, caplog):
    caplog.set_level(logging.WARNING)

    def mock_auth_user_session():
        return {}

    app.dependency_overrides[get_users_current_session] = mock_auth_user_session

    def mock_500(*args, **kwargs):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal Server Erroer",
        )

    override_health_endpoint(monkeypatch, mock_500)

    client.get("/health")

    record = caplog.records[0]
    log_json = json.loads(record.message)
    assert log_json["context"]["request"]["method"] == "GET"
    assert log_json["context"]["request"]["path"] == "/health"


@pytest.mark.asyncio
async def test_log_request_post(monkeypatch, caplog):
    caplog.set_level(logging.WARNING)

    def mock_auth_user_session():
        return {}

    app.dependency_overrides[get_users_current_session] = mock_auth_user_session

    def mock_500(*args, **kwargs):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal Server Erroer",
        )

    override_health_endpoint(monkeypatch, mock_500)

    client.post("/health")

    record = caplog.records[0]
    log_json = json.loads(record.message)
    assert log_json["context"]["request"]["method"] == "POST"
    assert log_json["context"]["request"]["path"] == "/health"


@pytest.mark.asyncio
async def test_log_request_query_string(monkeypatch, caplog):
    caplog.set_level(logging.WARNING)

    def mock_auth_user_session():
        return {}

    app.dependency_overrides[get_users_current_session] = mock_auth_user_session

    def mock_500(*args, **kwargs):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal Server Erroer",
        )

    override_health_endpoint(monkeypatch, mock_500)

    client.get("/health?test=data")

    record = caplog.records[0]
    log_json = json.loads(record.message)
    assert log_json["context"]["request"]["query_string"] == "test=data"


@pytest.mark.asyncio
async def test_log_request_query_string_blacklist(monkeypatch, caplog):
    caplog.set_level(logging.WARNING)

    def mock_auth_user_session():
        return {}

    app.dependency_overrides[get_users_current_session] = mock_auth_user_session

    def mock_500(*args, **kwargs):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal Server Erroer",
        )

    override_health_endpoint(monkeypatch, mock_500)

    client.get("/health?test=data&secret=password")

    record = caplog.records[0]
    log_json = json.loads(record.message)
    assert log_json["context"]["request"]["query_string"] == "test=data&secret=REDACTED"


@pytest.mark.asyncio
async def test_log_signed_in(monkeypatch, caplog):
    caplog.set_level(logging.WARNING)

    def mock_auth_user_session():
        return {}

    app.dependency_overrides[get_users_current_session] = mock_auth_user_session

    def mock_500(*args, **kwargs):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal Server Erroer",
        )

    override_health_endpoint(monkeypatch, mock_500)

    async def mock_get_user_info(*args, **kwargs):
        return {"sub": "12345678", "amr": ["password"]}

    monkeypatch.setattr(
        "app.utils.standardized_logging.get_user_info", mock_get_user_info
    )

    client.get("/health")

    record = caplog.records[0]
    log_json = json.loads(record.message)
    assert "user" in log_json["context"]
    assert (
        log_json["context"]["user"]["id"]
        == "ef797c8118f02dfb649607dd5d3f8c7623048c9c063d532cc95c5ed7a898a64f"
    )
    assert log_json["context"]["user"]["auth_methods"] == ["password"]


@pytest.mark.asyncio
async def test_log_signed_out(monkeypatch, caplog):
    caplog.set_level(logging.WARNING)

    def mock_auth_user_session():
        return {}

    app.dependency_overrides[get_users_current_session] = mock_auth_user_session

    def mock_500(*args, **kwargs):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal Server Erroer",
        )

    override_health_endpoint(monkeypatch, mock_500)

    client.get("/health")

    record = caplog.records[0]
    log_json = json.loads(record.message)
    assert "user" not in log_json["context"]


@pytest.mark.asyncio
async def test_log_includes_request_correlation_and_attempt_ids(monkeypatch, caplog):
    caplog.set_level(logging.WARNING)

    def mock_auth_user_session():
        return {}

    app.dependency_overrides[get_users_current_session] = mock_auth_user_session

    async def mock_500(request):
        request.state.correlation_id = "corr-123"
        request.state.attempt_id = "attempt-123"
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal Server Error",
        )

    override_health_endpoint(monkeypatch, mock_500)

    client.get("/health")

    record = caplog.records[0]
    log_json = json.loads(record.message)
    assert log_json["context"]["correlation_id"] == "corr-123"
    assert log_json["context"]["attempt_id"] == "attempt-123"


def test_log_auth_flow_event_hashes_sensitive_identifiers(caplog):
    correlation_token = bind_correlation_id("corr-123")
    attempt_token = bind_attempt_id("attempt-123")
    logger = logging.getLogger("tests.auth_flow")

    caplog.set_level(logging.INFO)
    try:
        log_auth_flow_event(
            logger,
            flow="verify",
            step="token_exchange",
            outcome="succeeded",
            rp_client_id="rp-123",
            user_id="user-123",
            session_id_hash=hash_identifier("sid-123"),
        )
    finally:
        reset_correlation_id(correlation_token)
        reset_attempt_id(attempt_token)

    record = caplog.records[-1]
    log_json = json.loads(record.message)
    assert log_json["code"] == "GCAuth.Migration.INFO.AUTH_FLOW"
    assert log_json["event"] == "auth_flow"
    assert log_json["flow"] == "verify"
    assert log_json["step"] == "token_exchange"
    assert log_json["outcome"] == "succeeded"
    assert log_json["context"]["correlation_id"] == "corr-123"
    assert log_json["context"]["attempt_id"] == "attempt-123"
    assert log_json["context"]["rp_client_id_hash"] == hash_identifier("rp-123")
    assert log_json["context"]["user_id_hash"] == hash_identifier("user-123")
    assert log_json["context"]["session_id_hash"] == hash_identifier("sid-123")
    assert "rp-123" not in record.message
    assert "user-123" not in record.message
    assert "sid-123" not in record.message
