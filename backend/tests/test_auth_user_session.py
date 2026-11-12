import time
from types import SimpleNamespace

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from authlib.integrations.starlette_client import OAuthError

from app.auth.services import auth_user_session
from app.auth.services.auth_session_index import get_logout_marker_key
from app.constants.redis_keys import RedisKeys
from app.constants.session_keys import SessionKeys
from app.utils.recovery_errors import RecoveryError


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query_params",
    [
        {},
        {"rp_client_id": ""},
        {"rp_client_id": " \t "},
        {"rp_client_id": "untrusted-rp"},
    ],
)
async def test_authentication_does_not_change_rp_context_from_query_string(
    query_params,
):
    mock_request = MagicMock()
    key = SessionKeys.RP_CLIENT_ID_KEY.value
    mock_request.query_params = query_params
    mock_request.session = {
        key: "original-rp",
        SessionKeys.SESSION_USER_ACCESS_TOKEN_KEY.value: "access-token",
    }

    with patch(
        "app.auth.services.auth_user_session.introspect_user_token",
        new=AsyncMock(return_value={"active": True}),
    ):
        await auth_user_session.get_users_current_session(mock_request)

    assert mock_request.session[key] == "original-rp"


@pytest.mark.asyncio
async def test_get_session_data_by_id_returns_none_when_missing():
    mock_request = MagicMock()
    mock_redis = MagicMock()
    mock_redis.get = AsyncMock(return_value=None)

    with patch(
        "app.auth.services.auth_user_session.get_redis_client", return_value=mock_redis
    ):
        result = await auth_user_session.get_session_data_by_id(mock_request, "sid123")
        assert result is None


@pytest.mark.asyncio
async def test_get_session_data_by_id_decodes_bytes_to_dict():
    mock_request = MagicMock()
    session_json = b'{"a": 1, "__metadata__": {"last_access": 10}}'
    mock_redis = MagicMock()
    mock_redis.get = AsyncMock(return_value=session_json)

    with patch(
        "app.auth.services.auth_user_session.get_redis_client", return_value=mock_redis
    ):
        result = await auth_user_session.get_session_data_by_id(mock_request, "sid456")
        assert isinstance(result, dict)
        assert result.get("a") == 1


@pytest.mark.asyncio
async def test_get_session_data_by_id_raises_503_when_redis_is_unavailable():
    mock_request = MagicMock()

    with patch(
        "app.auth.services.auth_user_session.get_redis_client",
        side_effect=ValueError("Redis client is not initialized in app state"),
    ):
        with pytest.raises(HTTPException) as raised:
            await auth_user_session.get_session_data_by_id(mock_request, "sid123")

    assert raised.value.status_code == 503
    assert raised.value.code == "service-unavailable"


@pytest.mark.asyncio
async def test_is_backchannel_logout_false_when_no_sid():
    mock_request = MagicMock()
    result = await auth_user_session.is_backchannel_logout(mock_request, "")
    assert result is False


@pytest.mark.asyncio
async def test_is_backchannel_logout_true_when_backchannel_value():
    mock_request = MagicMock()
    mock_redis = MagicMock()
    mock_redis.get = AsyncMock(return_value=b"backchannel_logout")

    with patch(
        "app.auth.services.auth_user_session.get_redis_client", return_value=mock_redis
    ):
        result = await auth_user_session.is_backchannel_logout(mock_request, "sid789")
        assert result is True


@pytest.mark.asyncio
async def test_is_backchannel_logout_false_for_other_value():
    mock_request = MagicMock()
    mock_redis = MagicMock()
    mock_redis.get = AsyncMock(return_value=b"processed")

    with patch(
        "app.auth.services.auth_user_session.get_redis_client", return_value=mock_redis
    ):
        result = await auth_user_session.is_backchannel_logout(mock_request, "sid000")
        assert result is False


@pytest.mark.asyncio
async def test_is_backchannel_logout_raises_503_when_redis_is_unavailable():
    mock_request = MagicMock()

    with patch(
        "app.auth.services.auth_user_session.get_redis_client",
        side_effect=ValueError("Redis client is not initialized in app state"),
    ):
        with pytest.raises(HTTPException) as raised:
            await auth_user_session.is_backchannel_logout(mock_request, "sid123")

    assert raised.value.status_code == 503
    assert raised.value.code == "service-unavailable"


@pytest.mark.asyncio
async def test_session_event_sse_generator_yields_error_when_redis_is_unavailable():
    mock_request = MagicMock()
    config = MagicMock(CORS_ORIGINS="https://frontend.example.test")

    with (
        patch(
            "app.auth.services.auth_user_session.get_configuration",
            return_value=config,
        ),
        patch(
            "app.auth.services.auth_user_session.get_user_info",
            new=AsyncMock(return_value={"sid": "sid123"}),
        ),
        patch.object(auth_user_session, "get_session_id", return_value="app-session"),
        patch(
            "app.auth.services.auth_user_session.get_session_data_by_id",
            new=AsyncMock(side_effect=RecoveryError("service-unavailable")),
        ),
    ):
        response = await auth_user_session.session_event_sse_generator(mock_request)
        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk)

    assert isinstance(response, StreamingResponse)

    payload = "".join(chunks)
    assert "event: error" in payload
    assert '"code":"service-unavailable"' in payload


def test_update_session_tokens_updates_session_dict():
    mock_request = MagicMock()
    mock_request.session = {SessionKeys.CSRF_TOKEN.value: "existing-csrf-token"}
    new_tokens = {"access_token": "at-1", "refresh_token": "rt-1"}

    auth_user_session.update_session_tokens(mock_request, new_tokens)

    assert (
        mock_request.session[SessionKeys.SESSION_USER_ACCESS_TOKEN_KEY.value] == "at-1"
    )
    assert mock_request.session[SessionKeys.SESSION_USER_TOKEN.value] == new_tokens
    assert mock_request.session[SessionKeys.CSRF_TOKEN.value] == "existing-csrf-token"


@pytest.mark.asyncio
async def test_get_http_client_returns_client():
    mock_request = MagicMock()
    client = AsyncMock()
    mock_request.app = MagicMock()
    mock_request.app.state = MagicMock()
    mock_request.app.state.request_client = client

    got = await auth_user_session.get_http_client(mock_request)
    assert got is client


@pytest.mark.asyncio
async def test_introspect_user_token_success():
    mock_http_client = AsyncMock()
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json = MagicMock(return_value={"active": True})
    mock_http_client.post = AsyncMock(return_value=response)

    config = MagicMock(
        introspect_token_api_endpoint="https://introspect",
        ibm_verify_config=MagicMock(
            IBM_VERIFY_MIGRATION_API_CLIENT_ID="cid",
            IBM_VERIFY_MIGRATION_API_SECRET="secret",
        ),
    )

    with (
        patch(
            "app.auth.services.auth_user_session.get_admin_token",
            new_callable=AsyncMock,
            return_value="admintok",
        ),
        patch(
            "app.auth.services.auth_user_session.get_auth_request_headers",
            return_value={},
        ),
        patch(
            "app.auth.services.auth_user_session.get_configuration",
            return_value=config,
        ),
    ):
        result = await auth_user_session.introspect_user_token(
            mock_http_client, "user-at-1"
        )
        assert result.get("active") is True


@pytest.mark.asyncio
async def test_introspect_user_token_handles_http_exception_and_other_errors():
    mock_http_client = AsyncMock()

    mock_http_client.post = AsyncMock(side_effect=HTTPException(status_code=500))
    with pytest.raises(HTTPException):
        await auth_user_session.introspect_user_token(mock_http_client, "token")

    mock_http_client.post = AsyncMock(side_effect=ValueError("boom"))
    with patch(
        "app.auth.services.auth_user_session.RequestErrorHandler.handle",
        new=MagicMock(),
    ) as mock_handler:
        with pytest.raises(HTTPException):
            await auth_user_session.introspect_user_token(mock_http_client, "token2")
        assert mock_handler.called


@pytest.mark.asyncio
async def test_get_users_current_session_inactive_clears_and_raises():
    mock_request = MagicMock()
    mock_request.query_params = {}
    mock_request.session = MagicMock()
    mock_request.session.get = MagicMock(return_value="user-at-1")

    with patch(
        "app.auth.services.auth_user_session.introspect_user_token",
        new=AsyncMock(return_value={"active": False}),
    ):
        with pytest.raises(OAuthError):
            await auth_user_session.get_users_current_session(mock_request)
        mock_request.session.clear.assert_called_once()


@pytest.mark.asyncio
async def test_get_users_current_session_missing_token_raises():
    mock_request = MagicMock()
    mock_request.query_params = {}
    mock_request.session = MagicMock()
    mock_request.session.get = MagicMock(return_value=None)

    with pytest.raises(OAuthError):
        await auth_user_session.get_users_current_session(mock_request)


@pytest.mark.asyncio
@pytest.mark.parametrize("backchannel", [False, True])
async def test_session_stream_reads_app_session_and_checks_oidc_logout(
    monkeypatch, backchannel
):
    request = MagicMock()
    config = SimpleNamespace(
        CORS_ORIGINS="https://frontend.example.test",
        session_config=SimpleNamespace(SESSION_LIFETIME=1800),
    )
    read = AsyncMock(side_effect=[{"__metadata__": {"last_access": 100}}, None])
    logout = AsyncMock(return_value=backchannel)
    monkeypatch.setattr(auth_user_session, "get_configuration", lambda: config)
    monkeypatch.setattr(
        auth_user_session, "get_user_info", AsyncMock(return_value={"sid": "oidc-sid"})
    )
    monkeypatch.setattr(auth_user_session, "get_session_id", lambda _: "app-session")
    monkeypatch.setattr(auth_user_session, "get_session_data_by_id", read)
    monkeypatch.setattr(auth_user_session, "is_backchannel_logout", logout)
    monkeypatch.setattr(auth_user_session.asyncio, "sleep", AsyncMock())

    response = await auth_user_session.session_event_sse_generator(request)
    body = "".join([chunk async for chunk in response.body_iterator])

    assert "event: notification" in body
    assert ('"expire":1870') in body
    assert f"event: {'terminated' if backchannel else 'expired'}" in body
    assert read.await_count == 2
    assert all(call.args == (request, "app-session") for call in read.await_args_list)
    logout.assert_awaited_once_with(request, "oidc-sid")


@pytest.mark.asyncio
async def test_session_stream_error_does_not_log_session_ids(monkeypatch, caplog):
    request = MagicMock()
    monkeypatch.setattr(
        auth_user_session,
        "get_user_info",
        AsyncMock(return_value={"sid": "sensitive-oidc-sid"}),
    )
    monkeypatch.setattr(
        auth_user_session, "get_session_id", lambda _: "sensitive-app-id"
    )
    monkeypatch.setattr(
        auth_user_session,
        "get_session_data_by_id",
        AsyncMock(side_effect=RuntimeError("broken session data")),
    )

    response = await auth_user_session.session_event_sse_generator(request)
    body = "".join([chunk async for chunk in response.body_iterator])

    assert "event: error" in body
    assert "Error in session event stream" in caplog.text
    assert "sensitive-oidc-sid" not in caplog.text
    assert "sensitive-app-id" not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("expired", [False, True])
async def test_keep_alive_refreshes_index_only_for_active_session(monkeypatch, expired):
    request = MagicMock()
    request.session = {"token": "existing-token"}
    now = time.time()
    associate = AsyncMock()
    monkeypatch.setattr(
        auth_user_session, "get_user_info", AsyncMock(return_value={"sid": "oidc-sid"})
    )
    monkeypatch.setattr(auth_user_session, "get_session_id", lambda _: "app-session")
    monkeypatch.setattr(
        auth_user_session,
        "get_session_metadata",
        lambda _: {"last_access": now, "created": now - (43201 if expired else 60)},
    )
    monkeypatch.setattr(auth_user_session, "associate_oidc_session", associate)

    result = await auth_user_session.session_extend(request)

    if expired:
        assert result.data.status == "terminated"
        assert request.session == {}
        associate.assert_not_awaited()
    else:
        assert result.data.status == "active"
        associate.assert_awaited_once_with(request, "oidc-sid", "app-session")


@pytest.mark.asyncio
@pytest.mark.parametrize("transport", ["sse", "keep-alive"])
@pytest.mark.parametrize(
    "sid,app_session_id", [(None, "app-session"), ("oidc-sid", None)]
)
async def test_session_status_requires_both_session_ids(
    monkeypatch, transport, sid, app_session_id
):
    request = MagicMock()
    monkeypatch.setattr(
        auth_user_session, "get_user_info", AsyncMock(return_value={"sid": sid})
    )
    monkeypatch.setattr(auth_user_session, "get_session_id", lambda _: app_session_id)
    associate = AsyncMock()
    read = AsyncMock()
    monkeypatch.setattr(auth_user_session, "associate_oidc_session", associate)
    monkeypatch.setattr(auth_user_session, "get_session_data_by_id", read)

    if transport == "sse":
        response = await auth_user_session.session_event_sse_generator(request)
        body = "".join([chunk async for chunk in response.body_iterator])
        assert "event: error" in body
        assert '"code":"session-ended"' in body
    else:
        response = await auth_user_session.session_extend(request)
        assert response.data.status == "non-authenticated"
    associate.assert_not_awaited()
    read.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("legacy", [False, True])
@pytest.mark.parametrize("value", [b"backchannel_logout", "backchannel_logout"])
async def test_session_logout_status_reads_hashed_and_legacy_markers(
    monkeypatch, legacy, value
):
    redis = SimpleNamespace(
        get=AsyncMock(side_effect=[None, value] if legacy else [value])
    )
    monkeypatch.setattr(auth_user_session, "get_redis_client", lambda _: redis)

    assert await auth_user_session.is_backchannel_logout(MagicMock(), "oidc-sid")

    keys = [call.args[0] for call in redis.get.await_args_list]
    assert keys[0] == get_logout_marker_key("oidc-sid")
    if legacy:
        assert keys[1] == f"{RedisKeys.REDIS_LOGOUT_SESSION_KEY.value}oidc-sid"
    else:
        assert len(keys) == 1
