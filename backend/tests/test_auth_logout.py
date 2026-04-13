from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.auth.services.auth_logout import backchannel_logout, logout_user
from app.utils.redis import get_redis_client


def _build_request_without_redis():
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))


def test_get_redis_client_raises_value_error_when_missing():
    request = _build_request_without_redis()

    with pytest.raises(ValueError, match="Redis client is not initialized in app state"):
        get_redis_client(request)


@pytest.mark.asyncio
async def test_logout_user_raises_503_when_redis_is_unavailable():
    request = MagicMock()
    request.app.state.config = SimpleNamespace(
        end_session_endpoint="https://verify.example.test/logout"
    )
    request.session = MagicMock()

    with (
        patch(
            "app.auth.services.auth_logout.get_user_info",
            new=AsyncMock(return_value={"sid": "sid-123", "locale": "en"}),
        ),
        patch(
            "app.auth.services.auth_logout.get_base_profile_management_url",
            return_value="https://profile.example.test",
        ),
        patch(
            "app.auth.services.auth_logout.get_redis_client",
            side_effect=ValueError("Redis client is not initialized in app state"),
        ),
    ):
        with pytest.raises(HTTPException) as raised:
            await logout_user(request, "id-token")

    assert raised.value.status_code == 503
    assert raised.value.detail == "Redis unavailable"


@pytest.mark.asyncio
async def test_backchannel_logout_raises_503_when_redis_is_unavailable():
    request = MagicMock()

    with (
        patch(
            "app.auth.services.auth_logout.validate_logout_token",
            new=AsyncMock(return_value={"sid": "sid-123", "jti": "jti-123"}),
        ),
        patch(
            "app.auth.services.auth_logout.is_logout_processed",
            new=AsyncMock(return_value=False),
        ),
        patch(
            "app.auth.services.auth_logout.get_redis_client",
            side_effect=ValueError("Redis client is not initialized in app state"),
        ),
    ):
        with pytest.raises(HTTPException) as raised:
            await backchannel_logout(request)

    assert raised.value.status_code == 503
    assert raised.value.detail == "Redis unavailable"
