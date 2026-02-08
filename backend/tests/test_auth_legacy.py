import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException
from fastapi.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuthError

from app.auth_legacy.services.login import legacy_login, SIC_legacy_login_auth
from app.auth_legacy.services.skip import skip_account_linking
from app.auth_legacy.services.callback import (
    legacy_callback,
    legacy_post_logout_callback,
)
from app.constants.session_keys import SessionKeys
from app.constants.audit_status_keys import AuditStatusKeys


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
async def test_sic_legacy_login_auth_missing_rp_client_id_raises():
    request = build_request()

    with pytest.raises(HTTPException) as raised:
        await SIC_legacy_login_auth(request, "user-at", "user-token", None, "en")

    assert raised.value.status_code == 400


@pytest.mark.asyncio
async def test_sic_legacy_login_auth_missing_legacy_idp_config_raises():
    request = build_request()
    rp = SimpleNamespace(IDP=[], rp_client_name="rpname")

    with patch(
        "app.auth_legacy.services.login.get_config", new=AsyncMock(return_value=rp)
    ):
        with pytest.raises(HTTPException) as raised:
            await SIC_legacy_login_auth(
                request, "user-at", "user-token", "rp-123", "en"
            )

    assert raised.value.status_code == 400


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
async def test_legacy_callback_patches_audit_with_linked_status():
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

    ok_response = MagicMock(status_code=204)

    with (
        patch(
            "app.auth_legacy.services.callback.config",
            new=SimpleNamespace(LEGACY_IDP_LOGOUT_ENABLED=True, ENVIRONMENT="local"),
        ),
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
            new=AsyncMock(return_value=ok_response),
        ),
        patch(
            "app.auth_legacy.services.callback.patch_audit_data",
            new=AsyncMock(return_value=ok_response),
        ) as mock_patch_audit,
    ):
        result = await legacy_callback(request, "user-at", "user-token", "rp-123")

    assert isinstance(result, RedirectResponse)
    mock_patch_audit.assert_awaited_once()
    args = mock_patch_audit.await_args.args
    assert args[1] == "ibm1"
    assert args[2] == "rp-123"
    assert args[4] == AuditStatusKeys.LINKED_KEY.value


@pytest.mark.asyncio
async def test_legacy_callback_uses_session_rp_client_id():
    request = build_request()
    request.session[SessionKeys.RP_CLIENT_ID_KEY.value] = "rp-from-session"

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

    ok_response = MagicMock(status_code=204)

    with (
        patch(
            "app.auth_legacy.services.callback.config",
            new=SimpleNamespace(LEGACY_IDP_LOGOUT_ENABLED=True, ENVIRONMENT="local"),
        ),
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
            new=AsyncMock(return_value=ok_response),
        ),
        patch(
            "app.auth_legacy.services.callback.patch_audit_data",
            new=AsyncMock(return_value=ok_response),
        ) as mock_patch_audit,
    ):
        await legacy_callback(request, "user-at", "user-token", "rp-123")

    args = mock_patch_audit.await_args.args
    assert args[2] == "rp-from-session"


@pytest.mark.asyncio
async def test_legacy_callback_raises_on_missing_rp_client_id():
    request = build_request()

    with pytest.raises(HTTPException) as raised:
        await legacy_callback(request, "user-at", "user-token", None)

    assert raised.value.status_code == 400


@pytest.mark.asyncio
async def test_legacy_callback_handles_oauth_error():
    request = build_request()
    client = MagicMock()
    client.authorize_access_token = AsyncMock(side_effect=OAuthError("bad"))

    legacy_idp = SimpleNamespace(client_name="SIC")
    rp = SimpleNamespace(IDP=[legacy_idp], rp_client_name="rpname")

    request.session["rpname_SIC_code_verifier"] = "verifier"

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
            "app.auth_legacy.services.callback.RequestErrorHandler.handle",
            side_effect=OAuthError("bad"),
        ) as mock_handler,
    ):
        with pytest.raises(OAuthError):
            await legacy_callback(request, "user-at", "user-token", "rp-123")

    mock_handler.assert_called_once()


@pytest.mark.asyncio
async def test_legacy_callback_handles_unexpected_exception():
    request = build_request()

    with (
        patch(
            "app.auth_legacy.services.callback.get_config",
            side_effect=Exception("boom"),
        ),
        patch(
            "app.auth_legacy.services.callback.RequestErrorHandler.handle",
            side_effect=HTTPException(status_code=500, detail="fail"),
        ) as mock_handler,
    ):
        with pytest.raises(HTTPException):
            await legacy_callback(request, "user-at", "user-token", "rp-123")

    mock_handler.assert_called_once()


@pytest.mark.asyncio
async def test_sic_legacy_login_auth_sets_session_and_state():
    request = build_request()
    legacy_idp = SimpleNamespace(
        client_name="SIC",
        redirect_uris=["https://idp.example.test/callback"],
        code_challenge_method="S256",
        client_id="cid",
        client_secret="secret",
        scope="openid",
    )
    rp = SimpleNamespace(IDP=[legacy_idp], rp_client_name="rpname")

    client = MagicMock()
    client.authorize_redirect = AsyncMock(return_value="ok")

    with (
        patch(
            "app.auth_legacy.services.login.get_config", new=AsyncMock(return_value=rp)
        ),
        patch("app.auth_legacy.services.login.register_client", new=AsyncMock()),
        patch(
            "app.auth_legacy.services.login.create_client", new=AsyncMock(return_value=client)
        ),
        patch(
            "app.auth_legacy.services.login.generate_secure_token",
            side_effect=["state-token", "nonce-token"],
        ),
        patch(
            "app.auth_legacy.services.login.generate_code_verifier",
            return_value="verifier-token",
        ),
        patch(
            "app.auth_legacy.services.login.generate_code_challenge",
            return_value="challenge-token",
        ),
        patch(
            "app.auth_legacy.services.login.get_ibm_id",
            new=AsyncMock(return_value="ibm1"),
        ),
        patch(
            "app.auth_legacy.services.login.get_user_custom_attributes",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "app.auth_legacy.services.login.patch_processing_data",
            new=AsyncMock(return_value=MagicMock(status_code=204)),
        ),
    ):
        result = await SIC_legacy_login_auth(
            request, "user-at", "user-token", "rp-123", "en"
        )

    assert result == "ok"
    assert request.session[SessionKeys.CURRENT_LANGUAGE.value] == "en"
    assert request.session["legacy_provider"] == "SIC"
    assert request.session["legacy_client_name"] == "rpname_SIC"
    assert request.session["rpname_SIC_code_verifier"] == "verifier-token"
    assert request.session["rpname_SIC_state"] == "state-token"
    assert request.session["rpname_SIC_nonce"] == "nonce-token"

    client.authorize_redirect.assert_awaited_once()
    args = client.authorize_redirect.await_args.args
    kwargs = client.authorize_redirect.await_args.kwargs
    assert args[1] == "https://idp.example.test/callback"
    assert kwargs["state"] == "state-token"
    assert kwargs["nonce"] == "nonce-token"
    assert kwargs["code_challenge"] == "challenge-token"
    assert kwargs["code_challenge_method"] == "S256"
    assert kwargs["ui_locales"] == "en-CA"


@pytest.mark.asyncio
async def test_legacy_post_logout_callback_builds_redirect():
    request = build_request()
    request.session[SessionKeys.CURRENT_LANGUAGE.value] = "en"

    config = SimpleNamespace(MIGRATON_SOLUTION_DOMAIN="https://profile.example.test")
    with patch(
        "app.auth_legacy.services.callback.get_configuration",
        return_value=config,
    ):
        response = await legacy_post_logout_callback(request)
    assert isinstance(response, RedirectResponse)
    assert response.headers["location"].endswith("/en/link/success")
