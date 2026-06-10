from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import status
from fastapi.responses import JSONResponse

from app.main import app
from app.routers.health import HealthResponse
from app.routers.health import health_check


def _build_request(*, request_client_initialized: bool, redis_client=None):
    state = SimpleNamespace(redis_client=redis_client)
    if request_client_initialized:
        state.request_client = MagicMock()
    return SimpleNamespace(app=SimpleNamespace(state=state))


@pytest.mark.asyncio
async def test_health_check_returns_healthy_when_dependencies_are_ready():
    redis_client = SimpleNamespace(ping=AsyncMock(return_value=True))
    request = _build_request(
        request_client_initialized=True,
        redis_client=redis_client,
    )
    payload = await health_check(request)

    assert payload == HealthResponse(
        status="healthy",
        timestamp=payload.timestamp,
        service="gc-signin-migration-backend",
    )


@pytest.mark.asyncio
async def test_health_check_returns_503_when_redis_is_unavailable():
    request = _build_request(
        request_client_initialized=True,
        redis_client=None,
    )
    payload = await health_check(request)
    parsed_payload = HealthResponse.model_validate_json(payload.body)

    assert isinstance(payload, JSONResponse)
    assert payload.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert parsed_payload == HealthResponse(
        status="unhealthy",
        timestamp=parsed_payload.timestamp,
        service="gc-signin-migration-backend",
    )


@pytest.mark.asyncio
async def test_health_check_returns_503_when_request_client_not_initialized():
    redis_client = SimpleNamespace(ping=AsyncMock(return_value=True))
    request = _build_request(
        request_client_initialized=False,
        redis_client=redis_client,
    )
    payload = await health_check(request)
    parsed_payload = HealthResponse.model_validate_json(payload.body)

    assert isinstance(payload, JSONResponse)
    assert payload.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert parsed_payload == HealthResponse(
        status="unhealthy",
        timestamp=parsed_payload.timestamp,
        service="gc-signin-migration-backend",
    )


def test_health_check_openapi_documents_503_response_model():
    responses = app.openapi()["paths"]["/health"]["get"]["responses"]

    assert responses["503"]["description"] == "Service dependencies are unavailable"
    assert (
        responses["503"]["content"]["application/json"]["schema"]["$ref"]
        == "#/components/schemas/HealthResponse"
    )
