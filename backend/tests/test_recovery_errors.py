import json
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import Request
from redis.exceptions import AuthenticationError, ConnectionError, TimeoutError

from app.auth.services import auth_user_session
from app.auth.services import auth
from app.main import app, configuration, session_store
from app.rp.services import config as rp_config
from app.utils.request_error_handler import RequestErrorHandler
from app.utils.recovery_errors import (
    RecoveryError,
    SessionEndedError,
    SessionStoreErrorMiddleware,
    recovery_response,
)


def request_for(path="/v1/auth/me", query=b"", session=None, accept="application/json"):
    return Request(
        {
            "type": "http",
            "method": "GET",
            "scheme": "https",
            "server": ("api.example.test", 443),
            "path": path,
            "query_string": query,
            "headers": [(b"accept", accept.encode())],
            "session": session if session is not None else {},
        }
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure", [ConnectionError, TimeoutError, AuthenticationError]
)
async def test_session_store_read_failure_has_recovery_code_and_cors(failure, caplog):
    error = failure("Redis diagnostic: session read failed")
    with patch.object(session_store, "read", new=AsyncMock(side_effect=error)):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.get(
                "/v1/auth/me",
                headers={
                    "Accept": "application/json",
                    "Origin": configuration.cors_origins_list[0],
                    "Cookie": f"{configuration.session_config.SESSION_COOKIE_NAME}=old-session",
                },
            )

    assert response.status_code == 503
    assert response.json()["code"] == "service-unavailable"
    assert (
        response.headers["access-control-allow-origin"]
        == configuration.cors_origins_list[0]
    )
    assert response.headers["access-control-allow-credentials"] == "true"
    assert response.headers["cache-control"] == "no-store"
    assert str(error) not in response.text
    record = next(
        record
        for record in caplog.records
        if record.getMessage() == "Redis unavailable while handling session"
    )
    assert record.exc_info[0] is failure
    assert record.exc_info[1] is error
    assert record.exc_info[2] is not None
    assert str(error) in caplog.text


@pytest.mark.asyncio
async def test_session_store_read_failure_redirects_navigation_without_loaded_session():
    with patch.object(
        session_store, "read", new=AsyncMock(side_effect=TimeoutError("offline"))
    ):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.get(
                "/v1/auth/login?clientId=rp-123&lang=fr",
                headers={
                    "Accept": "text/html",
                    "Cookie": f"{configuration.session_config.SESSION_COOKIE_NAME}=old-session",
                },
            )
    assert response.status_code == 303
    assert response.headers["location"].endswith("/fr/error/service-unavailable")


@pytest.mark.asyncio
@pytest.mark.parametrize("failed_operation", ["read", "write"])
async def test_session_store_failure_sends_readable_sse_recovery_event(
    failed_operation,
):
    read = AsyncMock(return_value=b'{"token":{"userinfo":{"sid":"sid-123"}}}')
    write = AsyncMock(return_value="session")
    (read if failed_operation == "read" else write).side_effect = TimeoutError(
        "offline"
    )
    with (
        patch.object(session_store, "read", new=read),
        patch.object(session_store, "write", new=write),
        patch.object(
            auth_user_session,
            "get_session_data_by_id",
            new=AsyncMock(return_value=None),
        ),
        patch.object(
            auth_user_session,
            "is_backchannel_logout",
            new=AsyncMock(return_value=False),
        ),
    ):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.get(
                "/v1/auth/session-status",
                headers={
                    "Accept": "text/event-stream",
                    "Origin": configuration.cors_origins_list[0],
                    "Cookie": f"{configuration.session_config.SESSION_COOKIE_NAME}=session",
                },
            )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-accel-buffering"] == "no"
    assert (
        response.headers["access-control-allow-origin"]
        == configuration.cors_origins_list[0]
    )
    assert response.headers["access-control-allow-credentials"] == "true"
    assert response.text.count("event: error\n") == 1
    assert response.text.endswith("\n\n")
    payload = json.loads(response.text.split("data: ", 1)[1])
    assert payload["status"] == "error"
    assert payload["code"] == "service-unavailable"


@pytest.mark.asyncio
async def test_other_endpoints_keep_503_json_for_event_stream_accept():
    with patch.object(
        session_store, "read", new=AsyncMock(side_effect=TimeoutError("offline"))
    ):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.get(
                "/v1/auth/me",
                headers={
                    "Accept": "text/event-stream",
                    "Cookie": f"{configuration.session_config.SESSION_COOKIE_NAME}=session",
                },
            )
    assert response.status_code == 503
    assert response.json()["code"] == "service-unavailable"


@pytest.mark.asyncio
async def test_session_store_write_failure_replaces_response_before_headers():
    with patch.object(
        session_store, "write", new=AsyncMock(side_effect=TimeoutError("offline"))
    ) as write:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.get("/v1/auth/csrf-token")
    write.assert_awaited_once()
    assert response.status_code == 503
    assert response.json()["code"] == "service-unavailable"
    assert "set-cookie" not in response.headers


@pytest.mark.asyncio
async def test_expired_redis_session_becomes_session_ended_without_external_requests():
    with patch.object(session_store, "read", new=AsyncMock(return_value=b"")):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.get(
                "/v1/auth/me",
                headers={
                    "Cookie": f"{configuration.session_config.SESSION_COOKIE_NAME}=expired"
                },
            )
    assert response.status_code == 401
    assert response.json()["code"] == "session-ended"


@pytest.mark.asyncio
async def test_initial_entry_can_authenticate_with_expired_cookie():
    with (
        patch.object(session_store, "read", new=AsyncMock(return_value=b"")),
        patch.object(session_store, "write", new=AsyncMock(return_value="new-session")),
    ):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.get(
                "/v1/auth/me?rp_client_id=rp-123",
                headers={
                    "Cookie": f"{configuration.session_config.SESSION_COOKIE_NAME}=expired"
                },
            )
    assert response.status_code == 401
    assert response.json()["code"] == "authentication-required"


@pytest.mark.asyncio
async def test_missing_rp_returns_stable_code_without_loading_configuration():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/v1/rp/rpConfigDetails")
    assert response.status_code == 400
    assert response.json()["code"] == "missing-rp-context"


@pytest.mark.asyncio
@pytest.mark.parametrize("language", ["en", "fr"])
async def test_login_without_rp_redirects_to_error_before_oauth(language):
    with patch.object(auth, "oauth") as oauth:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.get(
                f"/v1/auth/login?lang={language}", headers={"Accept": "text/html"}
            )
    assert response.status_code == 303
    assert response.headers["location"].endswith(
        f"/{language}/error/missing-rp-context"
    )
    oauth.verify.authorize_redirect.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path,status",
    [("/v1/rp/rpConfigDetails", 400), ("/v1/auth/me", 401), ("/favicon.ico", 404)],
)
async def test_logging_does_not_refresh_expired_token_or_replace_error_response(
    path, status
):
    stored_session = b'{"token":{"expires_at":1,"refresh_token":"expired","userinfo":{"sub":"user"}}}'
    with (
        patch.object(session_store, "read", new=AsyncMock(return_value=stored_session)),
        patch.object(session_store, "write", new=AsyncMock(return_value="session")),
        patch.object(
            auth_user_session,
            "refresh_token",
            new=AsyncMock(side_effect=AssertionError("Logging must not refresh")),
        ) as refresh,
    ):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.get(
                path,
                headers={
                    "Cookie": f"{configuration.session_config.SESSION_COOKIE_NAME}=session"
                },
            )
    assert response.status_code == status
    refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_inactive_token_is_not_initial_auth_even_with_explicit_rp():
    request = request_for(
        query=b"rp_client_id=rp-123", session={"access_token": "expired"}
    )
    with (
        patch.object(auth_user_session, "get_http_client", new=AsyncMock()),
        patch.object(
            auth_user_session,
            "introspect_user_token",
            new=AsyncMock(return_value={"active": False}),
        ),
    ):
        with pytest.raises(SessionEndedError):
            await auth_user_session.get_users_current_session(request)
    assert request.session == {}


@pytest.mark.asyncio
async def test_expiring_token_refreshes_and_updates_session():
    request = request_for(
        session={"token": {"expires_at": 1, "refresh_token": "refresh-me"}}
    )
    new_token = {"access_token": "new-access", "expires_at": 9999999999}
    with patch.object(
        auth_user_session, "refresh_token", new=AsyncMock(return_value=new_token)
    ) as refresh:
        result = await auth_user_session.ensure_user_token(request)
    refresh.assert_awaited_once_with("refresh-me")
    assert result == {**new_token, "refresh_token": "refresh-me"}
    assert request.session["token"] == result
    assert request.session["access_token"] == "new-access"


@pytest.mark.asyncio
@pytest.mark.parametrize("rotate_tokens", [False, True])
async def test_refresh_preserves_identity_and_omitted_tokens(rotate_tokens):
    user_info = {"sub": "user-123", "sid": "session-123"}
    request = request_for(
        session={
            "token": {
                "access_token": "old-access",
                "refresh_token": "old-refresh",
                "id_token": "old-id",
                "expires_at": 1,
                "userinfo": user_info,
            }
        }
    )
    refreshed = {"access_token": "new-access", "expires_at": 9999999999}
    if rotate_tokens:
        refreshed.update({"refresh_token": "new-refresh", "id_token": "new-id"})
    with patch.object(
        auth_user_session, "refresh_token", new=AsyncMock(return_value=refreshed)
    ) as refresh:
        actual_user_info = await auth_user_session.get_user_info(request)
        id_token = await auth_user_session.get_user_id_token(request)
        refresh_token = await auth_user_session.get_user_refresh_token(request)
    refresh.assert_awaited_once_with("old-refresh")
    assert actual_user_info == user_info
    assert id_token == ("new-id" if rotate_tokens else "old-id")
    assert refresh_token == ("new-refresh" if rotate_tokens else "old-refresh")
    assert request.session["access_token"] == "new-access"
    assert request.session["token"]["expires_at"] == refreshed["expires_at"]


@pytest.mark.asyncio
async def test_streaming_failure_does_not_send_second_response():
    async def broken_stream(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        raise ConnectionError("offline")

    messages = []

    async def send(message):
        messages.append(message)

    with pytest.raises(ConnectionError):
        await SessionStoreErrorMiddleware(broken_stream)(
            request_for().scope, AsyncMock(), send
        )
    assert len(messages) == 1
    assert messages[0]["status"] == 200


@pytest.mark.asyncio
async def test_unrelated_error_is_not_reported_as_redis_failure():
    async def broken_app(scope, receive, send):
        raise ValueError("unrelated bug")

    with pytest.raises(ValueError, match="unrelated bug"):
        await SessionStoreErrorMiddleware(broken_app)(
            request_for().scope, AsyncMock(), AsyncMock()
        )


@pytest.mark.parametrize(
    "language,expected", [("fr", "fr"), ("EN", "en"), ("../../x", "en")]
)
def test_error_navigation_uses_allowlisted_language(language, expected):
    request = request_for(session={"lang": language}, accept="text/html")
    response = recovery_response(request, "missing-rp-context")
    assert response.headers["location"].endswith(
        f"/{expected}/error/missing-rp-context"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [ConnectionError, TimeoutError])
@pytest.mark.parametrize("transport", ["json", "sse"])
async def test_session_lookup_preserves_redis_diagnostics_in_logs_only(
    failure, transport, caplog
):
    error = failure("Redis diagnostic: session GET failed")
    redis_client = SimpleNamespace(get=AsyncMock(side_effect=error))
    request = request_for(path="/v1/auth/session-status")
    with (
        patch.object(auth_user_session, "get_redis_client", return_value=redis_client),
        patch.object(
            auth_user_session,
            "get_user_info",
            new=AsyncMock(return_value={"sid": "session-123"}),
        ),
    ):
        if transport == "sse":
            response = await auth_user_session.session_event_sse_generator(request)
            body = "".join([chunk async for chunk in response.body_iterator])
            assert "event: error\n" in body
            payload = json.loads(body.split("data: ", 1)[1])
        else:
            with pytest.raises(RecoveryError) as raised:
                await auth_user_session.get_session_data_by_id(request, "session-123")
            response = recovery_response(request, raised.value.code)
            assert response.status_code == 503
            body = response.body.decode()
            payload = json.loads(body)

    assert payload["code"] == "service-unavailable"
    assert str(error) not in body
    record = next(
        record
        for record in caplog.records
        if record.getMessage() == "Redis unavailable during session status flow"
    )
    assert record.exc_info[0] is failure
    assert record.exc_info[1] is error
    assert record.exc_info[2] is not None
    assert str(error) in caplog.text


@pytest.mark.parametrize(
    "failure", [ConnectionError, TimeoutError, AuthenticationError]
)
def test_request_error_handler_preserves_passed_redis_exception(caplog, failure):
    # The handler accepts exception objects even after the except block ends.
    error = failure("Redis diagnostic: connection setup failed")
    try:
        raise error
    except failure:
        pass

    with pytest.raises(RecoveryError) as raised:
        RequestErrorHandler.handle(error, context="legacy metadata request")

    assert raised.value.code == "service-unavailable"
    assert str(error) not in raised.value.detail
    record = next(
        record
        for record in caplog.records
        if record.getMessage() == "Redis unavailable during legacy metadata request"
    )
    assert record.exc_info == (failure, error, error.__traceback__)
    assert record.exc_info[2] is not None
    assert str(error) in caplog.text


@pytest.mark.asyncio
async def test_metadata_client_initialization_failure_keeps_lookup_context(caplog):
    error = ValueError("Redis client is not initialized in app state")
    with patch.object(rp_config, "get_redis_client", side_effect=error):
        with pytest.raises(RecoveryError) as raised:
            await rp_config.get_legacy_idp_metadata(
                request_for(),
                "https://idp.example.test/.well-known/openid-configuration",
            )

    assert raised.value.code == "service-unavailable"
    assert str(error) not in raised.value.detail
    record = next(
        record
        for record in caplog.records
        if record.getMessage() == "Redis unavailable during legacy IdP metadata lookup"
    )
    assert record.exc_info[0] is ValueError
    assert record.exc_info[1] is error
    assert record.exc_info[2] is not None
    assert str(error) in caplog.text


@pytest.mark.parametrize(
    "code,status,level",
    [
        ("missing-rp-context", 400, logging.WARNING),
        ("session-ended", 401, logging.WARNING),
        ("service-unavailable", 503, logging.ERROR),
    ],
)
@pytest.mark.parametrize(
    "accept", ["application/json", "text/html", "text/event-stream"]
)
def test_recovery_logs_reason_for_every_response_format(
    code, status, level, accept, caplog
):
    request = request_for(
        path="/v1/auth/session-status", query=b"code=private-code", accept=accept
    )
    response = recovery_response(request, code)

    expected_status = {"text/html": 303, "text/event-stream": 200}.get(accept, status)
    assert response.status_code == expected_status
    records = [
        record
        for record in caplog.records
        if record.getMessage().startswith("Migration recovery:")
    ]
    assert len(records) == 1
    assert records[0].levelno == level
    assert records[0].getMessage() == (
        f"Migration recovery: code={code} status={status} "
        "method=GET path=/v1/auth/session-status"
    )
    assert "private-code" not in caplog.text
