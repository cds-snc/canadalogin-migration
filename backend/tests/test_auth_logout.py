from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
from fastapi import HTTPException

from app.auth.services.auth_logout import (
    backchannel_logout,
    logout_user,
    mark_session_logout,
)
from app.auth.services.auth_session_index import (
    get_logout_marker_key,
    get_oidc_session_index_key,
)
from app.constants.redis_keys import RedisKeys
from app.utils.redis import get_redis_client


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
    request.app.state.redis_client.get = AsyncMock(return_value=None)
    request.app.state.redis_client.smembers = AsyncMock(return_value=set())
    request.app.state.redis_client.delete = AsyncMock()
    request.app.state.redis_client.setex = AsyncMock()
    return request


def build_request_without_redis():
    request = MagicMock()
    request.session = {}
    request.app = MagicMock()
    request.app.state = MagicMock()
    request.app.state.config = SimpleNamespace(
        end_session_endpoint="https://verify.example.test/logout"
    )
    request.app.state.redis_client = None
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
@pytest.mark.parametrize("session_ids", [set(), {b"app-session-1", "app-session-2"}])
async def test_backchannel_logout_deletes_indexed_and_legacy_sessions(
    session_ids, caplog
):
    request = build_request()
    redis_client = request.app.state.redis_client
    redis_client.smembers.return_value = session_ids
    caplog.set_level("DEBUG")

    with patch(
        "app.auth.services.auth_logout.validate_logout_token",
        new=AsyncMock(return_value={"sid": "sid-123", "jti": "jti-123"}),
    ):
        result = await backchannel_logout(request)

    assert result.success is True
    assert result.message == "Backchannel logout successful"
    expected_ids = {"sid-123"}
    if session_ids:
        expected_ids.update({"app-session-1", "app-session-2"})
    expected_keys = sorted(
        f"{RedisKeys.REDIS_SESSION_KEY.value}{session_id}"
        for session_id in expected_ids
    )
    redis_client.smembers.assert_awaited_once_with(
        get_oidc_session_index_key("sid-123")
    )
    assert redis_client.delete.await_args_list == [
        call(*expected_keys),
        call(get_oidc_session_index_key("sid-123")),
    ]
    redis_client.setex.assert_awaited_once_with(
        get_logout_marker_key("sid-123"), 1800, "backchannel_logout"
    )
    assert all(session_id not in caplog.text for session_id in expected_ids)


@pytest.mark.asyncio
@pytest.mark.parametrize("legacy_marker", [False, True])
@pytest.mark.parametrize("marker_value", [b"backchannel_logout", "backchannel_logout"])
async def test_backchannel_logout_ignores_completed_duplicate(
    legacy_marker, marker_value
):
    request = build_request()
    redis_client = request.app.state.redis_client
    marker_key = (
        f"{RedisKeys.REDIS_LOGOUT_SESSION_KEY.value}sid-123"
        if legacy_marker
        else get_logout_marker_key("sid-123")
    )
    redis_client.get.side_effect = lambda key: (
        marker_value if key == marker_key else None
    )

    with patch(
        "app.auth.services.auth_logout.validate_logout_token",
        new=AsyncMock(return_value={"sid": "sid-123", "jti": "jti-123"}),
    ):
        result = await backchannel_logout(request)

    assert result.success is True
    assert result.message == "Backchannel logout already processed"
    redis_client.get.assert_any_await(marker_key)
    redis_client.delete.assert_not_awaited()
    redis_client.smembers.assert_not_awaited()
    redis_client.setex.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("legacy_marker", [False, True])
@pytest.mark.parametrize("marker_value", [b"logout_button", "logout_button"])
async def test_foreground_logout_marker_does_not_skip_sibling_session_logout(
    legacy_marker, marker_value
):
    request = build_request()
    redis_client = request.app.state.redis_client
    redis_client.smembers.return_value = {b"app-session-1", "app-session-2"}
    marker_key = (
        f"{RedisKeys.REDIS_LOGOUT_SESSION_KEY.value}sid-123"
        if legacy_marker
        else get_logout_marker_key("sid-123")
    )
    redis_client.get.side_effect = lambda key: (
        marker_value if key == marker_key else None
    )

    with patch(
        "app.auth.services.auth_logout.validate_logout_token",
        new=AsyncMock(return_value={"sid": "sid-123", "jti": "jti-123"}),
    ):
        result = await backchannel_logout(request)

    assert result.success is True
    assert result.message == "Backchannel logout successful"
    redis_client.get.assert_any_await(marker_key)
    assert redis_client.delete.await_args_list == [
        call(
            f"{RedisKeys.REDIS_SESSION_KEY.value}app-session-1",
            f"{RedisKeys.REDIS_SESSION_KEY.value}app-session-2",
            f"{RedisKeys.REDIS_SESSION_KEY.value}sid-123",
        ),
        call(get_oidc_session_index_key("sid-123")),
    ]
    redis_client.setex.assert_awaited_once_with(
        get_logout_marker_key("sid-123"), 1800, "backchannel_logout"
    )


@pytest.mark.asyncio
async def test_mark_session_logout_uses_hashed_key_and_requested_expiration(caplog):
    request = build_request()
    caplog.set_level("DEBUG")

    await mark_session_logout(
        request, "private-provider-sid", "logout_button", expiration_seconds=60
    )

    request.app.state.redis_client.setex.assert_awaited_once_with(
        get_logout_marker_key("private-provider-sid"), 60, "logout_button"
    )
    marker_key = request.app.state.redis_client.setex.await_args.args[0]
    assert "private-provider-sid" not in marker_key
    assert "private-provider-sid" not in caplog.text


def test_get_redis_client_raises_value_error_when_missing():
    request = build_request_without_redis()

    with pytest.raises(
        ValueError, match="Redis client is not initialized in app state"
    ):
        get_redis_client(request)


@pytest.mark.asyncio
async def test_logout_user_raises_503_when_redis_is_unavailable():
    request = build_request_without_redis()

    with (
        patch(
            "app.auth.services.auth_logout.get_user_info",
            new=AsyncMock(return_value={"locale": "en", "sid": "sid-123"}),
        ),
        patch(
            "app.auth.services.auth_logout.get_base_profile_management_url",
            return_value="https://profile.example.test",
        ),
    ):
        with pytest.raises(HTTPException) as raised:
            await logout_user(request, "id-token")

    assert raised.value.status_code == 503
    assert raised.value.detail == "Redis unavailable"


@pytest.mark.asyncio
async def test_backchannel_logout_raises_503_when_redis_is_unavailable():
    request = build_request_without_redis()

    with (
        patch(
            "app.auth.services.auth_logout.validate_logout_token",
            new=AsyncMock(return_value={"sid": "sid-123", "jti": "jti-123"}),
        ),
        patch(
            "app.auth.services.auth_logout.is_logout_processed",
            new=AsyncMock(return_value=False),
        ),
    ):
        with pytest.raises(HTTPException) as raised:
            await backchannel_logout(request)

    assert raised.value.status_code == 503
    assert raised.value.detail == "Redis unavailable"
