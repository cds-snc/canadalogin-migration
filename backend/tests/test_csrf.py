"""Exercise the production routes with real starsessions cookie/storage handling."""

import json
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from authlib.jose import JsonWebKey, jwt
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from starsessions import SessionMiddleware
from starsessions.stores.memory import InMemoryStore

from app.auth.services import auth, auth_user_session
from app.auth import v1_router as auth_router
from app.auth.services.csrf import validate_csrf_token
from app.auth_legacy.services import skip
from app.constants.session_keys import SessionKeys
from app.constants.redis_keys import RedisKeys
from app.main import app

API = "/v1/auth"
FRONTEND_ORIGIN = "https://frontend.example.test"


class RecordingStore(InMemoryStore):
    def __init__(self):
        super().__init__()
        self.writes = 0

    async def write(self, session_id, data, lifetime, ttl):
        self.writes += 1
        return await super().write(session_id, data, lifetime, ttl)


@pytest.fixture
def browser_app(monkeypatch):
    store = RecordingStore()
    for middleware in app.user_middleware:
        if middleware.cls is SessionMiddleware:
            monkeypatch.setitem(middleware.kwargs, "store", store)
            monkeypatch.setitem(middleware.kwargs, "cookie_name", "session")
            monkeypatch.setitem(middleware.kwargs, "cookie_domain", None)
            monkeypatch.setitem(middleware.kwargs, "cookie_https_only", False)
        elif middleware.cls is CORSMiddleware:
            monkeypatch.setitem(middleware.kwargs, "allow_origins", [FRONTEND_ORIGIN])

    monkeypatch.setattr(app, "middleware_stack", None)
    monkeypatch.setattr(app, "dependency_overrides", {})
    monkeypatch.setattr(app.router, "routes", list(app.router.routes))
    # Avoid real identity-provider traffic while keeping route dependencies real.
    introspect = AsyncMock(return_value={"active": True})
    monkeypatch.setattr(auth_user_session, "introspect_user_token", introspect)
    monkeypatch.setattr(app.state, "request_client", MagicMock(), raising=False)
    effects = {"dependency": 0, "handler": 0}

    async def route_dependency():
        effects["dependency"] += 1

    async def change_state(request: Request, unused=Depends(route_dependency)):
        effects["handler"] += 1
        request.session["changed"] = True
        return {"success": True}

    app.add_api_route(
        "/csrf-test/change", change_state, methods=["POST", "PUT", "PATCH", "DELETE"]
    )
    client = TestClient(app)
    yield SimpleNamespace(
        client=client, store=store, effects=effects, introspect=introspect
    )
    client.close()
    app.middleware_stack = None


def token_for(client):
    response = client.get(f"{API}/csrf-token")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    return response.json()["csrf_token"]


def session_data(browser_app):
    sid = browser_app.client.cookies.get("session")
    return json.loads(browser_app.store.data[sid])


def authenticate(browser_app):
    token = token_for(browser_app.client)
    sid = browser_app.client.cookies.get("session")
    data = session_data(browser_app)
    data.update(
        {
            "access_token": "user-access-token",
            "rp_client_id": "original-rp",
            "token": {
                "access_token": "user-access-token",
                "id_token": "id-token",
                "userinfo": {"sid": sid, "sub": "user-id"},
            },
        }
    )
    browser_app.store.data[sid] = json.dumps(data).encode()
    return token


def test_token_bootstrap_creates_session_and_reuses_token(browser_app):
    token = token_for(browser_app.client)

    assert len(token) >= 43  # 32 random bytes, encoded for transport.
    assert session_data(browser_app)[SessionKeys.CSRF_TOKEN.value] == token
    assert token_for(browser_app.client) == token


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
@pytest.mark.parametrize("supplied", [None, "wrong-token", b"\xff"])
def test_invalid_tokens_rejected_before_dependencies_and_session_save(
    browser_app, method, supplied
):
    authenticate(browser_app)
    stored = dict(browser_app.store.data)
    writes = browser_app.store.writes
    headers = {"Origin": FRONTEND_ORIGIN}
    if supplied is not None:
        headers["X-CSRF-Token"] = supplied

    response = browser_app.client.request(method, "/csrf-test/change", headers=headers)

    assert response.status_code == 403
    assert response.json()["message"] == "Missing or invalid CSRF token"
    assert response.headers["access-control-allow-origin"] == FRONTEND_ORIGIN
    assert "set-cookie" not in response.headers
    assert browser_app.effects == {"dependency": 0, "handler": 0}
    assert browser_app.store.data == stored
    assert browser_app.store.writes == writes
    browser_app.introspect.assert_not_awaited()


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_matching_token_allows_state_change(browser_app, method):
    token = token_for(browser_app.client)

    response = browser_app.client.request(
        method, "/csrf-test/change", headers={"X-CSRF-Token": token}
    )

    assert response.status_code == 200
    assert browser_app.effects == {"dependency": 1, "handler": 1}
    assert session_data(browser_app)["changed"] is True


def test_token_alone_cannot_create_or_authenticate_session(browser_app):
    token = token_for(browser_app.client)
    other_browser = TestClient(app)
    try:
        response = other_browser.post(
            "/csrf-test/change", headers={"X-CSRF-Token": token}
        )
        assert response.status_code == 403
        assert "set-cookie" not in response.headers

        other_token = token_for(other_browser)
        assert token != other_token
        response = other_browser.post(
            "/csrf-test/change", headers={"X-CSRF-Token": token}
        )
        assert response.status_code == 403
        assert browser_app.effects == {"dependency": 0, "handler": 0}
    finally:
        other_browser.close()


def test_expired_session_does_not_accept_its_old_token(browser_app):
    token = authenticate(browser_app)
    browser_app.store.data.clear()

    response = browser_app.client.post(
        f"{API}/keep-alive", headers={"X-CSRF-Token": token}
    )

    assert response.status_code == 403
    assert browser_app.store.data == {}
    assert "set-cookie" not in response.headers


def test_token_endpoint_initializes_session_without_autoload_middleware():
    test_app = FastAPI(dependencies=[Depends(validate_csrf_token)])
    test_app.include_router(auth_router.router, prefix=API)
    test_app.add_middleware(
        SessionMiddleware, store=InMemoryStore(), cookie_https_only=False
    )
    client = TestClient(test_app)
    try:
        assert token_for(client)
        assert client.cookies.get("session")
    finally:
        client.close()


def test_cors_preflight_does_not_require_token(browser_app):
    response = browser_app.client.options(
        f"{API}/logout",
        headers={
            "Origin": FRONTEND_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "X-CSRF-Token",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == FRONTEND_ORIGIN
    assert "x-csrf-token" in response.headers["access-control-allow-headers"].lower()


@pytest.mark.parametrize(
    "path", ["/logout", "/keep-alive", "/rp-context", "/legacy/skip"]
)
def test_browser_actions_reject_missing_token_before_auth_or_service(
    browser_app, path, monkeypatch, caplog
):
    authenticate(browser_app)
    refresh = AsyncMock()
    monkeypatch.setattr(auth_user_session, "get_user_info", refresh)
    response = browser_app.client.post(f"{API}{path}", json={"rp_client_id": "new-rp"})

    assert response.status_code == 403
    browser_app.introspect.assert_not_awaited()
    refresh.assert_not_awaited()
    assert session_data(browser_app)["rp_client_id"] == "original-rp"
    request_logs = [
        json.loads(record.message)
        for record in caplog.records
        if record.name == "app.utils.standardized_logging"
    ]
    assert len(request_logs) == 1
    assert request_logs[0]["context"]["response"]["status_code"] == 403
    assert "user" not in request_logs[0]["context"]


def test_keep_alive_accepts_valid_token(browser_app):
    token = authenticate(browser_app)

    response = browser_app.client.post(
        f"{API}/keep-alive", headers={"X-CSRF-Token": token}
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "active"


def test_logout_clears_token_and_session(browser_app, monkeypatch):
    token = authenticate(browser_app)
    monkeypatch.setattr(
        app.state,
        "config",
        SimpleNamespace(end_session_endpoint="https://idp.example.test/logout"),
        raising=False,
    )
    mark_logout = AsyncMock()
    monkeypatch.setattr(
        "app.auth.services.auth_logout.mark_session_logout", mark_logout
    )

    response = browser_app.client.post(f"{API}/logout", headers={"X-CSRF-Token": token})

    assert response.status_code == 200
    assert response.json()["data"]["redirect_url"].startswith(
        "https://idp.example.test/logout?"
    )
    mark_logout.assert_awaited_once()
    assert browser_app.store.data == {}
    response = browser_app.client.post(
        f"{API}/keep-alive", headers={"X-CSRF-Token": token}
    )
    assert response.status_code == 403
    assert token_for(browser_app.client) != token


def test_skip_requires_post_and_returns_json_without_redirect(browser_app, monkeypatch):
    token = authenticate(browser_app)
    patch_audit = AsyncMock()
    monkeypatch.setattr(skip, "get_ibm_id", MagicMock(return_value="ibm-id"))
    monkeypatch.setattr(skip, "get_user_custom_attributes", AsyncMock(return_value=[]))
    monkeypatch.setattr(skip, "patch_audit_data", patch_audit)
    monkeypatch.setattr(
        skip,
        "get_config",
        AsyncMock(
            return_value=SimpleNamespace(rp_redirect_uri="https://rp.example.test/")
        ),
    )

    response = browser_app.client.get(f"{API}/legacy/skip")
    assert response.status_code == 405
    patch_audit.assert_not_awaited()
    response = browser_app.client.post(f"{API}/legacy/skip")
    assert response.status_code == 403
    patch_audit.assert_not_awaited()

    response = browser_app.client.post(
        f"{API}/legacy/skip?lang=fr", headers={"X-CSRF-Token": token}
    )
    assert response.status_code == 200
    assert response.json()["redirect_url"].startswith("https://rp.example.test/?")
    assert "lang=fr" in response.json()["redirect_url"]
    assert "location" not in response.headers
    patch_audit.assert_awaited_once()


def test_rp_context_can_only_be_changed_by_authenticated_protected_post(
    browser_app, monkeypatch
):
    token = authenticate(browser_app)
    get_config = AsyncMock()
    monkeypatch.setattr(auth_router, "get_config", get_config)

    # A real GET auth dependency must ignore a forged RP query parameter.
    async def read_context(
        request: Request, unused=Depends(auth_user_session.get_users_current_session)
    ):
        return {"rp_client_id": request.session["rp_client_id"]}

    app.add_api_route("/csrf-test/context", read_context)
    response = browser_app.client.get("/csrf-test/context?rp_client_id=untrusted-rp")
    assert response.status_code == 200
    assert response.json()["rp_client_id"] == "original-rp"

    response = browser_app.client.post(
        f"{API}/rp-context",
        json={"rp_client_id": "new-rp"},
        headers={"X-CSRF-Token": token},
    )
    assert response.status_code == 200
    assert response.json() == {"success": True}
    assert session_data(browser_app)["rp_client_id"] == "new-rp"
    get_config.assert_awaited_once_with("new-rp")


def test_fresh_rp_context_requires_initial_authentication(browser_app, monkeypatch):
    token = token_for(browser_app.client)
    get_config = AsyncMock()
    monkeypatch.setattr(auth_router, "get_config", get_config)

    response = browser_app.client.post(
        f"{API}/rp-context",
        json={"rp_client_id": "new-rp"},
        headers={"X-CSRF-Token": token, "Accept": "application/json"},
    )

    assert response.status_code == 401
    assert response.json()["code"] == "authentication-required"
    assert "rp_client_id" not in session_data(browser_app)
    browser_app.introspect.assert_not_awaited()
    get_config.assert_not_awaited()


@pytest.mark.parametrize("context", [{}, {"rp_client_id": ""}])
def test_fresh_rp_context_requires_valid_body(browser_app, context):
    token = token_for(browser_app.client)

    response = browser_app.client.post(
        f"{API}/rp-context",
        json=context,
        headers={"X-CSRF-Token": token, "Accept": "application/json"},
    )

    assert response.status_code == 400
    assert "rp_client_id" not in session_data(browser_app)
    browser_app.introspect.assert_not_awaited()


def test_expired_rp_context_session_requires_recovery(browser_app, monkeypatch):
    token = authenticate(browser_app)
    browser_app.introspect.return_value = {"active": False}
    get_config = AsyncMock()
    monkeypatch.setattr(auth_router, "get_config", get_config)

    response = browser_app.client.post(
        f"{API}/rp-context",
        json={"rp_client_id": "new-rp"},
        headers={"X-CSRF-Token": token, "Accept": "application/json"},
    )

    assert response.status_code == 401
    assert response.json()["code"] == "session-ended"
    assert browser_app.store.data == {}
    browser_app.introspect.assert_awaited_once()
    get_config.assert_not_awaited()


def test_partial_rp_context_session_requires_recovery(browser_app, monkeypatch):
    token = authenticate(browser_app)
    sid = browser_app.client.cookies.get("session")
    data = session_data(browser_app)
    del data[SessionKeys.SESSION_USER_ACCESS_TOKEN_KEY.value]
    browser_app.store.data[sid] = json.dumps(data).encode()
    get_config = AsyncMock()
    monkeypatch.setattr(auth_router, "get_config", get_config)

    response = browser_app.client.post(
        f"{API}/rp-context",
        json={"rp_client_id": "new-rp"},
        headers={"X-CSRF-Token": token, "Accept": "application/json"},
    )

    assert response.status_code == 401
    assert response.json()["code"] == "session-ended"
    assert session_data(browser_app)["rp_client_id"] == "original-rp"
    browser_app.introspect.assert_not_awaited()
    get_config.assert_not_awaited()


def test_oidc_callback_accepts_get_and_rotates_token(browser_app, monkeypatch):
    previous_token = authenticate(browser_app)
    exchange = AsyncMock(
        return_value={
            "access_token": "new-token",
            "userinfo": {"sid": "new-session-id"},
        }
    )
    monkeypatch.setattr(
        auth,
        "oauth",
        SimpleNamespace(verify=SimpleNamespace(authorize_access_token=exchange)),
    )
    response = browser_app.client.get(
        f"{API}/callback?state=oidc-state", follow_redirects=False
    )

    assert response.status_code == 307
    exchange.assert_awaited_once()
    assert browser_app.client.cookies.get("session") == "new-session-id"
    current_token = token_for(browser_app.client)
    assert previous_token != current_token
    assert (
        browser_app.client.post(
            "/csrf-test/change", headers={"X-CSRF-Token": previous_token}
        ).status_code
        == 403
    )
    assert (
        browser_app.client.post(
            "/csrf-test/change", headers={"X-CSRF-Token": current_token}
        ).status_code
        == 200
    )


def test_backchannel_logout_requires_signed_logout_token_without_csrf(
    browser_app, monkeypatch
):
    validate = AsyncMock(side_effect=ValueError("Invalid logout token"))
    monkeypatch.setattr("app.auth.services.auth_logout.validate_logout_token", validate)

    response = browser_app.client.post(
        f"{API}/backchannel-logout", data={"logout_token": "invalid"}
    )

    assert response.status_code == 400
    assert response.json()["message"] == "Invalid logout token"
    validate.assert_awaited_once()


@pytest.mark.parametrize("valid_signature", [True, False])
def test_backchannel_exception_still_validates_real_jwt_signature(
    browser_app, monkeypatch, valid_signature
):
    signing_key = JsonWebKey.generate_key("RSA", 2048, is_private=True)
    trusted_key = (
        signing_key
        if valid_signature
        else JsonWebKey.generate_key("RSA", 2048, is_private=True)
    )
    client = SimpleNamespace(
        client_id="oidc-client",
        fetch_jwk_set=AsyncMock(return_value={"keys": [trusted_key.as_dict()]}),
    )
    monkeypatch.setattr(
        "app.auth.services.auth_logout.oauth", SimpleNamespace(verify=client)
    )
    redis = SimpleNamespace(
        get=AsyncMock(return_value=None), delete=AsyncMock(), setex=AsyncMock()
    )
    monkeypatch.setattr(app.state, "redis_client", redis, raising=False)
    signed_token = jwt.encode(
        {"alg": "RS256"},
        {
            "aud": "oidc-client",
            "iat": int(time.time()),
            "jti": "logout-event-id",
            "sid": "signed-out-session",
            "events": {"http://schemas.openid.net/event/backchannel-logout": {}},
        },
        signing_key,
    ).decode()

    response = browser_app.client.post(
        f"{API}/backchannel-logout", data={"logout_token": signed_token}
    )

    if valid_signature:
        assert response.status_code == 200
        redis.delete.assert_awaited_once_with(
            f"{RedisKeys.REDIS_SESSION_KEY.value}signed-out-session"
        )
    else:
        assert response.status_code == 400
        redis.delete.assert_not_awaited()


def test_csrf_values_are_redacted_in_query_logs(browser_app, caplog):
    token = authenticate(browser_app)
    browser_app.client.post(f"{API}/logout?csrf_token={token}&x-csrf-token={token}")

    app_logs = "\n".join(
        record.message
        for record in caplog.records
        if record.name == "app.utils.standardized_logging"
    )
    assert token not in app_logs
    assert "REDACTED" in app_logs
