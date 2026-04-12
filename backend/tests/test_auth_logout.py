from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.auth.services.auth_logout import backchannel_logout, logout_user
from app.constants.redis_keys import RedisKeys


def build_request():
    request = MagicMock()
    request.session = {
        "legacy_client_name": "rpname_SIC",
        "rpname_SIC_state": "legacy-state",
    }
    request.app = MagicMock()
    request.app.state = MagicMock()
    request.app.state.config = SimpleNamespace(
        end_session_endpoint="https://verify.example.test/logout"
    )
    request.app.state.redis_client = MagicMock()
    request.app.state.redis_client.delete = AsyncMock()
    return request


@pytest.mark.asyncio
async def test_logout_user_clears_session_and_marks_logout():
    request = build_request()

    with (
        patch(
            "app.auth.services.auth_logout.get_user_info",
            new=AsyncMock(return_value={"locale": "fr", "sid": "sid-123"}),
        ),
        patch(
            "app.auth.services.auth_logout.get_base_profile_management_url",
            return_value="https://profile.example.test",
        ),
        patch(
            "app.auth.services.auth_logout.mark_session_logout",
            new=AsyncMock(),
        ) as mock_mark_session_logout,
    ):
        result = await logout_user(request, "id-token-123")

    assert result.success is True
    assert result.message == "Redirect url to logout"
    assert request.session == {}
    assert (
        result.data.redirect_url
        == "https://verify.example.test/logout?id_token_hint=id-token-123&post_logout_redirect_uri=https%3A%2F%2Fprofile.example.test&ui_locales=fr"
    )
    mock_mark_session_logout.assert_awaited_once_with(
        request, sid="sid-123", source="logout_button"
    )


@pytest.mark.asyncio
async def test_backchannel_logout_deletes_session_and_marks_processed():
    request = build_request()

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
            "app.auth.services.auth_logout.mark_session_logout",
            new=AsyncMock(),
        ) as mock_mark_session_logout,
    ):
        result = await backchannel_logout(request)

    assert result.success is True
    assert result.message == "Backchannel logout successful"
    request.app.state.redis_client.delete.assert_awaited_once_with(
        f"{RedisKeys.REDIS_SESSION_KEY.value}sid-123"
    )
    mock_mark_session_logout.assert_awaited_once_with(
        request, "sid-123", source="backchannel_logout"
    )


@pytest.mark.asyncio
async def test_backchannel_logout_ignores_duplicate_sid():
    request = build_request()

    with (
        patch(
            "app.auth.services.auth_logout.validate_logout_token",
            new=AsyncMock(return_value={"sid": "sid-123", "jti": "jti-123"}),
        ),
        patch(
            "app.auth.services.auth_logout.is_logout_processed",
            new=AsyncMock(return_value=True),
        ),
    ):
        result = await backchannel_logout(request)

    assert result.success is True
    assert result.message == "Backchannel logout already processed"
    request.app.state.redis_client.delete.assert_not_awaited()
