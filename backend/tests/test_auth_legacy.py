import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException
from fastapi.responses import RedirectResponse

from app.auth_legacy.services.login import legacy_login, SIC_legacy_login_auth
from app.auth_legacy.services.skip import skip_account_linking
from app.auth_legacy.services.callback import (
    legacy_callback,
    legacy_post_logout_callback,
)
from app.constants.session_keys import SessionKeys


def build_request():
    request = MagicMock()
    request.session = {}
    request.app = MagicMock()
    request.app.state = MagicMock()
    request.app.state.request_client = AsyncMock()
    return request


@pytest.mark.asyncio
async def test_legacy_login_routes_to_sic_handler():
    request = build_request()
    user_access_token = "user-at"
    session_user_token = "user-token"
    rp_client_id = "rp-123"

    legacy_idp = SimpleNamespace(client_name="SIC")
    rp = SimpleNamespace(IDP=[legacy_idp])

    with (
        patch(
            "app.auth_legacy.services.login.get_config", new=AsyncMock(return_value=rp)
        ),
        patch(
            "app.auth_legacy.services.login.SIC_legacy_login_auth",
            new=AsyncMock(return_value="ok"),
        ) as mock_sic,
    ):
        result = await legacy_login(
            request, user_access_token, session_user_token, rp_client_id, lang="en"
        )
        assert result == "ok"
        mock_sic.assert_awaited_once()


@pytest.mark.asyncio
async def test_sic_legacy_login_auth_missing_redirect_uris_raises():
    request = build_request()
    legacy_idp = SimpleNamespace(
        client_name="SIC",
        redirect_uris=[],
        code_challenge_method="S256",
        client_id="cid",
        client_secret="secret",
        scope="openid",
    )
    rp = SimpleNamespace(IDP=[legacy_idp], rp_client_name="rpname")

    with (
        patch(
            "app.auth_legacy.services.login.get_config", new=AsyncMock(return_value=rp)
        ),
        patch("app.auth_legacy.services.login.register_client", new=AsyncMock()),
        patch("app.auth_legacy.services.login.create_client", new=AsyncMock()),
    ):
        with pytest.raises(HTTPException) as raised:
            await SIC_legacy_login_auth(
                request, "user-at", "user-token", "rp-123", "en"
            )
        assert raised.value.status_code == 500


@pytest.mark.asyncio
async def test_skip_account_linking_redirects_to_rp():
    request = build_request()
    rp = SimpleNamespace(rp_redirect_uri="https://rp.example.test/landing")

    with (
        patch(
            "app.auth_legacy.services.skip.get_ibm_id",
            new=AsyncMock(return_value="ibm1"),
        ),
        patch(
            "app.auth_legacy.services.skip.get_user_custom_attributes",
            new=AsyncMock(return_value=[]),
        ),
        patch("app.auth_legacy.services.skip.patch_audit_data", new=AsyncMock()),
        patch(
            "app.auth_legacy.services.skip.get_config", new=AsyncMock(return_value=rp)
        ),
    ):
        response = await skip_account_linking(
            request, "user-at", "user-token", "rp-123"
        )
        assert isinstance(response, RedirectResponse)
        assert response.headers["location"] == rp.rp_redirect_uri


@pytest.mark.asyncio
async def test_legacy_callback_raises_on_patch_failure():
    request = build_request()
    client = MagicMock()
    client.authorize_access_token = AsyncMock(return_value={"id_token": "idtok"})
    client.parse_id_token = AsyncMock(return_value={"sub": "legacy-sub"})
    client.server_metadata = {
        "server_metadata": {"end_session_endpoint": "https://idp/logout"}
    }

    legacy_idp = SimpleNamespace(client_name="SIC")
    rp = SimpleNamespace(IDP=[legacy_idp], rp_client_name="rpname")

    request.session["rpname_SIC_code_verifier"] = "verifier"
    request.session["rpname_SIC_nonce"] = "nonce"
    request.session["rpname_SIC_state"] = "state"

    failing_response = MagicMock(status_code=400)
    failing_response.json = MagicMock(return_value={"detail": "bad"})

    with (
        patch(
            "app.auth_legacy.services.callback.get_config",
            new=AsyncMock(return_value=rp),
        ),
        patch(
            "app.auth_legacy.services.callback.create_client",
            new=AsyncMock(return_value=client),
        ),
        patch(
            "app.auth_legacy.services.callback.get_ibm_id",
            new=AsyncMock(return_value="ibm1"),
        ),
        patch(
            "app.auth_legacy.services.callback.get_user_custom_attributes",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "app.auth_legacy.services.callback.patch_legacy_pai",
            new=AsyncMock(return_value=failing_response),
        ),
    ):
        with pytest.raises(HTTPException) as raised:
            await legacy_callback(request, "user-at", "user-token", "rp-123")
        assert raised.value.status_code == 400


@pytest.mark.asyncio
async def test_legacy_post_logout_callback_builds_redirect():
    request = build_request()
    request.session[SessionKeys.CURRENT_LANGUAGE.value] = "en"

    config = SimpleNamespace(PROFILE_MANAGEMENT_DOMAIN="https://profile.example.test")
    with patch(
        "app.auth_legacy.services.callback.get_configuration",
        return_value=config,
    ):
        response = await legacy_post_logout_callback(request)
    assert isinstance(response, RedirectResponse)
    assert response.headers["location"].endswith("/en/link/success")
