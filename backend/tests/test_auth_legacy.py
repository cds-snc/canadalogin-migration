import base64
import hashlib
import json
import logging
import httpx
import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

from fastapi import HTTPException
from fastapi.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuthError

from app.auth_legacy.services.login import legacy_login, oidc_legacy_login_auth
from app.auth_legacy.services.skip import skip_account_linking
from app.auth_legacy.services.callback import (
    get_target_rp_client_ids,
    legacy_callback,
    legacy_post_logout_callback,
)
from app.constants.session_keys import SessionKeys
from app.constants.audit_status_keys import AuditStatusKeys
from app.utils.auth_flow_logging import hash_identifier


def build_request():
    request = MagicMock()
    request.session = {}
    request.query_params = {}
    request.app = MagicMock()
    request.app.state = MagicMock()
    request.app.state.request_client = AsyncMock()
    return request


def seed_legacy_session(
    request,
    *,
    client_name: str = "rpname_SIC",
    state: str = "state",
    nonce: str = "nonce",
    verifier: str = "verifier",
):
    request.session["legacy_provider"] = "SIC"
    request.session["legacy_client_name"] = client_name
    request.session[f"{client_name}_code_verifier"] = verifier
    request.session[f"{client_name}_nonce"] = nonce
    request.session[f"{client_name}_state"] = state
    request.session[f"_state_{client_name}_{state}"] = {
        "data": {"nonce": nonce, "code_verifier": verifier},
        "exp": 9999999999,
    }


def test_get_target_rp_client_ids_dedupes_and_preserves_order():
    result = get_target_rp_client_ids("rp-a", ["rp-b", "rp-c", "rp-a", "rp-b"])
    assert result == ["rp-a", "rp-b", "rp-c"]


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["SIC", "GCCF", " gccf "])
async def test_legacy_login_routes_supported_providers_to_oidc_handler(provider):
    request = build_request()
    user_access_token = "user-at"
    session_user_token = "user-token"
    rp_client_id = "rp-123"

    legacy_idp = SimpleNamespace(client_name=provider)
    rp = SimpleNamespace(IDP=[legacy_idp])

    with (
        patch(
            "app.auth_legacy.services.login.get_config", new=AsyncMock(return_value=rp)
        ),
        patch(
            "app.auth_legacy.services.login.oidc_legacy_login_auth",
            new=AsyncMock(return_value="ok"),
        ) as mock_oidc,
    ):
        result = await legacy_login(
            request, user_access_token, session_user_token, rp_client_id, lang="en"
        )
        assert result == "ok"
        mock_oidc.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("rp_client_id", [None, ""])
async def test_legacy_login_rejects_missing_rp_client_id(rp_client_id):
    with pytest.raises(HTTPException) as raised:
        await legacy_login(build_request(), "user-at", "user-token", rp_client_id)

    assert raised.value.status_code == 400


@pytest.mark.asyncio
@pytest.mark.parametrize("legacy_idps", [[], [SimpleNamespace(client_name="unknown")]])
async def test_legacy_login_rejects_missing_or_unsupported_provider(legacy_idps):
    with patch(
        "app.auth_legacy.services.login.get_config",
        new=AsyncMock(return_value=SimpleNamespace(IDP=legacy_idps)),
    ):
        with pytest.raises(HTTPException) as raised:
            await legacy_login(build_request(), "user-at", "user-token", "rp-123")

    assert raised.value.status_code == 400


@pytest.mark.asyncio
async def test_oidc_legacy_login_auth_missing_redirect_uris_raises():
    request = build_request()
    legacy_idp = SimpleNamespace(
        client_name="SIC",
        redirect_uris=[],
        code_challenge_method="S256",
        client_id="cid",
        client_secret="secret",
        scope="openid",
    )
    rp = SimpleNamespace(
        IDP=[legacy_idp], rp_client_name="rpname", dependent_client_ids=[]
    )

    with (
        patch(
            "app.auth_legacy.services.login.get_config", new=AsyncMock(return_value=rp)
        ),
        patch("app.auth_legacy.services.login.register_client", new=AsyncMock()),
        patch("app.auth_legacy.services.login.create_client", new=AsyncMock()),
    ):
        with pytest.raises(HTTPException) as raised:
            await oidc_legacy_login_auth(
                request, "user-at", "user-token", "rp-123", "en"
            )
        assert raised.value.status_code == 500


@pytest.mark.asyncio
async def test_oidc_legacy_login_auth_missing_rp_client_id_raises():
    request = build_request()

    with pytest.raises(HTTPException) as raised:
        await oidc_legacy_login_auth(request, "user-at", "user-token", None, "en")

    assert raised.value.status_code == 400


@pytest.mark.asyncio
async def test_oidc_legacy_login_auth_missing_legacy_idp_config_raises():
    request = build_request()
    rp = SimpleNamespace(IDP=[], rp_client_name="rpname")

    with patch(
        "app.auth_legacy.services.login.get_config", new=AsyncMock(return_value=rp)
    ):
        with pytest.raises(HTTPException) as raised:
            await oidc_legacy_login_auth(
                request, "user-at", "user-token", "rp-123", "en"
            )

    assert raised.value.status_code == 400


@pytest.mark.asyncio
async def test_oidc_legacy_login_auth_raises_when_processing_patch_returns_dict_error():
    request = build_request()
    legacy_idp = SimpleNamespace(
        client_name="SIC",
        redirect_uris=["https://legacy.example.test/callback"],
        code_challenge_method="S256",
        client_id="cid",
        client_secret="secret",
        scope="openid",
    )
    rp = SimpleNamespace(
        IDP=[legacy_idp], rp_client_name="rpname", dependent_client_ids=[]
    )
    client = MagicMock()
    client.authorize_redirect = AsyncMock()

    with (
        patch(
            "app.auth_legacy.services.login.get_config", new=AsyncMock(return_value=rp)
        ),
        patch("app.auth_legacy.services.login.register_client", new=AsyncMock()),
        patch(
            "app.auth_legacy.services.login.create_client",
            new=AsyncMock(return_value=client),
        ),
        patch(
            "app.auth_legacy.services.login.get_ibm_id",
            new=MagicMock(return_value="ibm1"),
        ),
        patch(
            "app.auth_legacy.services.login.get_user_custom_attributes",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "app.auth_legacy.services.login.patch_processing_data",
            new=AsyncMock(return_value={"error": "HTTP error: 500"}),
        ),
    ):
        with pytest.raises(HTTPException) as raised:
            await oidc_legacy_login_auth(
                request, "user-at", "user-token", "rp-123", "en"
            )

    assert raised.value.status_code == 502
    assert raised.value.detail == "HTTP error: 500"


@pytest.mark.asyncio
async def test_skip_account_linking_returns_rp_redirect_url():
    request = build_request()
    seed_legacy_session(request)
    request.session[SessionKeys.CUSTOM_PARAMETERS.value] = {
        "fakeparam1": "value-1",
        "fakeparam2": "value-2",
    }
    request.session[SessionKeys.CURRENT_LANGUAGE.value] = "fr"
    rp = SimpleNamespace(
        rp_redirect_uri="https://rp.example.test/landing",
        rp_redirect_uri_en="https://rp.example.test/landing/en",
        rp_redirect_uri_fr="https://rp.example.test/landing/fr",
    )

    with (
        patch(
            "app.auth_legacy.services.skip.get_ibm_id",
            new=MagicMock(return_value="ibm1"),
        ),
        patch(
            "app.auth_legacy.services.skip.get_user_custom_attributes",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "app.auth_legacy.services.skip.patch_audit_data",
            new=AsyncMock(),
        ) as mock_patch_audit,
        patch(
            "app.auth_legacy.services.skip.get_config", new=AsyncMock(return_value=rp)
        ),
    ):
        response = await skip_account_linking(
            request, "user-at", "user-token", "rp-123"
        )
        assert response.redirect_url
        assert mock_patch_audit.await_args.kwargs["correlation_id"]
        assert SessionKeys.CORRELATION_ID.value in request.session
        assert SessionKeys.LEGACY_LINKING_ATTEMPT_ID.value not in request.session
        assert "legacy_client_name" not in request.session
        assert "legacy_provider" not in request.session
        assert "rpname_SIC_code_verifier" not in request.session
        assert "rpname_SIC_nonce" not in request.session
        assert "rpname_SIC_state" not in request.session
        assert "_state_rpname_SIC_state" not in request.session
        assert (
            response.redirect_url
            == "https://rp.example.test/landing/fr?fakeparam1=value-1&fakeparam2=value-2&lang=fr&ui_locales=fr-CA"
        )


@pytest.mark.asyncio
async def test_skip_account_linking_logs_auth_flow_events(caplog):
    request = build_request()
    request.session[SessionKeys.CURRENT_LANGUAGE.value] = "fr"
    rp = SimpleNamespace(
        rp_redirect_uri="https://rp.example.test/landing",
        rp_redirect_uri_en="https://rp.example.test/landing/en",
        rp_redirect_uri_fr="https://rp.example.test/landing/fr",
    )

    caplog.set_level(logging.INFO)
    with (
        patch(
            "app.auth_legacy.services.skip.get_ibm_id",
            new=MagicMock(return_value="ibm1"),
        ),
        patch(
            "app.auth_legacy.services.skip.get_user_custom_attributes",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "app.auth_legacy.services.skip.patch_audit_data",
            new=AsyncMock(),
        ),
        patch(
            "app.auth_legacy.services.skip.get_config",
            new=AsyncMock(return_value=rp),
        ),
    ):
        await skip_account_linking(request, "user-at", "user-token", "rp-123")

    auth_flow_logs = [
        json.loads(record.message)
        for record in caplog.records
        if '"event": "auth_flow"' in record.message
    ]

    assert auth_flow_logs[0]["flow"] == "migration"
    assert auth_flow_logs[0]["step"] == "skip_linking"
    assert auth_flow_logs[0]["outcome"] == "started"
    assert auth_flow_logs[0]["context"]["rp_client_id_hash"] == hash_identifier(
        "rp-123"
    )
    assert auth_flow_logs[0]["context"]["user_id_hash"] == hash_identifier("ibm1")

    assert auth_flow_logs[1]["step"] == "audit_patch"
    assert auth_flow_logs[1]["outcome"] == "succeeded"
    assert auth_flow_logs[1]["context"]["audit_status"] == "SKIPPED"

    assert auth_flow_logs[2]["step"] == "skip_linking"
    assert auth_flow_logs[2]["outcome"] == "succeeded"
    assert auth_flow_logs[2]["context"]["lang"] == "fr"


@pytest.mark.asyncio
async def test_legacy_callback_raises_on_patch_failure():
    request = build_request()
    client = MagicMock()
    client.authorize_access_token = AsyncMock(return_value={"id_token": "idtok"})
    client.parse_id_token = AsyncMock(return_value={"sub": "legacy-sub"})
    client.server_metadata = {
        "server_metadata": {"end_session_endpoint": "https://idp/logout"}
    }

    legacy_idp = SimpleNamespace(client_name="SIC", client_id="sic-client-id")
    rp = SimpleNamespace(
        IDP=[legacy_idp],
        rp_client_name="rpname",
        dependent_client_ids=["rp-456", "rp-456", "rp-789"],
    )

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
            "app.auth_legacy.services.callback.register_client",
            new=AsyncMock(),
        ),
        patch(
            "app.auth_legacy.services.callback.create_client",
            new=AsyncMock(return_value=client),
        ),
        patch(
            "app.auth_legacy.services.callback.get_ibm_id",
            new=MagicMock(return_value="ibm1"),
        ),
        patch(
            "app.auth_legacy.services.callback.get_user_custom_attributes",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "app.auth_legacy.services.callback.patch_legacy_pai",
            new=AsyncMock(return_value=failing_response),
        ) as mock_patch_legacy_pai,
    ):
        with pytest.raises(HTTPException) as raised:
            await legacy_callback(request, "user-at", "user-token", "rp-123")
        assert raised.value.status_code == 400
        mock_patch_legacy_pai.assert_awaited_once()
        called_kwargs = mock_patch_legacy_pai.await_args.kwargs
        assert called_kwargs["target_rp_client_ids"] == [
            "rp-123",
            "rp-456",
            "rp-789",
        ]


@pytest.mark.asyncio
async def test_legacy_callback_raises_with_upstream_detail_when_patch_returns_dict_error():
    request = build_request()
    client = MagicMock()
    client.authorize_access_token = AsyncMock(return_value={"id_token": "idtok"})
    client.parse_id_token = AsyncMock(return_value={"sub": "legacy-sub"})
    client.server_metadata = {
        "server_metadata": {"end_session_endpoint": "https://idp/logout"}
    }

    legacy_idp = SimpleNamespace(client_name="SIC", client_id="sic-client-id")
    rp = SimpleNamespace(
        IDP=[legacy_idp], rp_client_name="rpname", dependent_client_ids=[]
    )

    request.session["rpname_SIC_code_verifier"] = "verifier"
    request.session["rpname_SIC_nonce"] = "nonce"
    request.session["rpname_SIC_state"] = "state"

    with (
        patch(
            "app.auth_legacy.services.callback.get_config",
            new=AsyncMock(return_value=rp),
        ),
        patch(
            "app.auth_legacy.services.callback.register_client",
            new=AsyncMock(),
        ),
        patch(
            "app.auth_legacy.services.callback.create_client",
            new=AsyncMock(return_value=client),
        ),
        patch(
            "app.auth_legacy.services.callback.get_ibm_id",
            new=MagicMock(return_value="ibm1"),
        ),
        patch(
            "app.auth_legacy.services.callback.get_user_custom_attributes",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "app.auth_legacy.services.callback.patch_legacy_pai",
            new=AsyncMock(return_value={"error": "HTTP error: 500"}),
        ),
    ):
        with pytest.raises(HTTPException) as raised:
            await legacy_callback(request, "user-at", "user-token", "rp-123")

    assert raised.value.status_code == 502
    assert raised.value.detail == "HTTP error: 500"


@pytest.mark.asyncio
async def test_legacy_callback_raises_http_exception_on_upstream_http_status_error():
    request = build_request()
    client = MagicMock()
    legacy_request = httpx.Request("POST", "https://sic.example.test/token")
    legacy_response = httpx.Response(
        503,
        json={"detail": "legacy idp unavailable"},
        request=legacy_request,
    )
    client.authorize_access_token = AsyncMock(
        side_effect=httpx.HTTPStatusError(
            "service unavailable",
            request=legacy_request,
            response=legacy_response,
        )
    )

    legacy_idp = SimpleNamespace(client_name="SIC", client_id="sic-client-id")
    rp = SimpleNamespace(
        IDP=[legacy_idp], rp_client_name="rpname", dependent_client_ids=[]
    )

    request.session["rpname_SIC_code_verifier"] = "verifier"

    with (
        patch(
            "app.auth_legacy.services.callback.get_config",
            new=AsyncMock(return_value=rp),
        ),
        patch(
            "app.auth_legacy.services.callback.register_client",
            new=AsyncMock(),
        ),
        patch(
            "app.auth_legacy.services.callback.create_client",
            new=AsyncMock(return_value=client),
        ),
    ):
        with pytest.raises(HTTPException) as raised:
            await legacy_callback(request, "user-at", "user-token", "rp-123")

    assert raised.value.status_code == 503
    assert raised.value.detail == "legacy idp unavailable"


@pytest.mark.asyncio
async def test_legacy_callback_patches_audit_with_linked_status():
    request = build_request()
    request.session[SessionKeys.CORRELATION_ID.value] = "corr-123"
    request.session[SessionKeys.LEGACY_LINKING_ATTEMPT_ID.value] = "attempt-123"
    request.session[SessionKeys.CURRENT_LANGUAGE.value] = "fr"
    seed_legacy_session(request)
    client = MagicMock()
    client.authorize_access_token = AsyncMock(return_value={"id_token": "idtok"})
    client.parse_id_token = AsyncMock(return_value={"sub": "legacy-sub"})
    client.server_metadata = {
        "server_metadata": {"end_session_endpoint": "https://idp/logout"}
    }

    legacy_idp = SimpleNamespace(client_name="SIC", client_id="sic-client-id")
    rp = SimpleNamespace(
        IDP=[legacy_idp],
        rp_client_name="rpname",
        dependent_client_ids=[],
        acr_values="MFA",
    )

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
            "app.auth_legacy.services.callback.has_registered_client",
            return_value=False,
        ),
        patch(
            "app.auth_legacy.services.callback.register_client",
            new=AsyncMock(),
        ) as mock_register_client,
        patch(
            "app.auth_legacy.services.callback.create_client",
            new=AsyncMock(return_value=client),
        ),
        patch(
            "app.auth_legacy.services.callback.get_ibm_id",
            new=MagicMock(return_value="ibm1"),
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
    mock_register_client.assert_awaited_once_with(
        request,
        "rpname_SIC",
        legacy_idp,
        "fr-CA",
        "MFA",
    )
    mock_patch_audit.assert_awaited_once()
    kwargs = mock_patch_audit.await_args.kwargs
    assert kwargs["ibm_id"] == "ibm1"
    assert kwargs["rp_client_id"] == "rp-123"
    assert kwargs["status"] == AuditStatusKeys.LINKED_KEY.value
    assert kwargs["correlation_id"] == "corr-123"
    assert kwargs["attempt_id"] == "attempt-123"
    assert request.session[SessionKeys.LEGACY_LINKING_ATTEMPT_ID.value] == "attempt-123"
    assert "legacy_client_name" not in request.session
    assert "legacy_provider" not in request.session
    assert "rpname_SIC_code_verifier" not in request.session
    assert "rpname_SIC_nonce" not in request.session
    assert "rpname_SIC_state" not in request.session
    assert "_state_rpname_SIC_state" not in request.session


@pytest.mark.asyncio
async def test_legacy_callback_reuses_registered_client():
    request = build_request()
    request.session[SessionKeys.CORRELATION_ID.value] = "corr-123"
    request.session[SessionKeys.LEGACY_LINKING_ATTEMPT_ID.value] = "attempt-123"
    seed_legacy_session(request)
    client = MagicMock()
    client.authorize_access_token = AsyncMock(return_value={"id_token": "idtok"})
    client.parse_id_token = AsyncMock(return_value={"sub": "legacy-sub"})
    client.server_metadata = {
        "server_metadata": {"end_session_endpoint": "https://idp/logout"}
    }

    legacy_idp = SimpleNamespace(client_name="SIC", client_id="sic-client-id")
    rp = SimpleNamespace(
        IDP=[legacy_idp],
        rp_client_name="rpname",
        dependent_client_ids=[],
        acr_values="MFA",
    )

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
            "app.auth_legacy.services.callback.has_registered_client",
            return_value=True,
        ),
        patch(
            "app.auth_legacy.services.callback.register_client",
            new=AsyncMock(),
        ) as mock_register_client,
        patch(
            "app.auth_legacy.services.callback.create_client",
            new=AsyncMock(return_value=client),
        ),
        patch(
            "app.auth_legacy.services.callback.get_ibm_id",
            new=MagicMock(return_value="ibm1"),
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
        ),
    ):
        result = await legacy_callback(request, "user-at", "user-token", "rp-123")

    assert isinstance(result, RedirectResponse)
    mock_register_client.assert_not_awaited()


@pytest.mark.asyncio
async def test_legacy_callback_uses_session_rp_client_id():
    request = build_request()
    request.session[SessionKeys.RP_CLIENT_ID_KEY.value] = "rp-from-session"
    request.session[SessionKeys.CORRELATION_ID.value] = "corr-123"
    request.session[SessionKeys.LEGACY_LINKING_ATTEMPT_ID.value] = "attempt-123"
    seed_legacy_session(request)

    client = MagicMock()
    client.authorize_access_token = AsyncMock(return_value={"id_token": "idtok"})
    client.parse_id_token = AsyncMock(return_value={"sub": "legacy-sub"})
    client.server_metadata = {
        "server_metadata": {"end_session_endpoint": "https://idp/logout"}
    }

    legacy_idp = SimpleNamespace(client_name="SIC", client_id="sic-client-id")
    rp = SimpleNamespace(
        IDP=[legacy_idp], rp_client_name="rpname", dependent_client_ids=[]
    )

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
            "app.auth_legacy.services.callback.register_client",
            new=AsyncMock(),
        ),
        patch(
            "app.auth_legacy.services.callback.create_client",
            new=AsyncMock(return_value=client),
        ),
        patch(
            "app.auth_legacy.services.callback.get_ibm_id",
            new=MagicMock(return_value="ibm1"),
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

    kwargs = mock_patch_audit.await_args.kwargs
    assert kwargs["rp_client_id"] == "rp-from-session"
    assert kwargs["correlation_id"] == "corr-123"
    assert kwargs["attempt_id"] == "attempt-123"


@pytest.mark.asyncio
async def test_legacy_callback_raises_on_missing_rp_client_id():
    request = build_request()

    with pytest.raises(HTTPException) as raised:
        await legacy_callback(request, "user-at", "user-token", None)

    assert raised.value.status_code == 400


@pytest.mark.asyncio
async def test_legacy_callback_handles_oauth_error():
    request = build_request()
    seed_legacy_session(request)
    client = MagicMock()
    client.authorize_access_token = AsyncMock(side_effect=OAuthError("bad"))

    legacy_idp = SimpleNamespace(client_name="SIC", client_id="sic-client-id")
    rp = SimpleNamespace(
        IDP=[legacy_idp], rp_client_name="rpname", dependent_client_ids=[]
    )

    with (
        patch(
            "app.auth_legacy.services.callback.get_config",
            new=AsyncMock(return_value=rp),
        ),
        patch(
            "app.auth_legacy.services.callback.register_client",
            new=AsyncMock(),
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
    assert SessionKeys.LEGACY_LINKING_ATTEMPT_ID.value not in request.session
    assert "legacy_client_name" not in request.session
    assert "legacy_provider" not in request.session
    assert "rpname_SIC_code_verifier" not in request.session
    assert "rpname_SIC_nonce" not in request.session
    assert "rpname_SIC_state" not in request.session
    assert "_state_rpname_SIC_state" not in request.session


@pytest.mark.asyncio
async def test_legacy_callback_rejects_mismatched_state():
    request = build_request()
    request.session[SessionKeys.LEGACY_LINKING_ATTEMPT_ID.value] = "attempt-123"
    request.query_params = {"state": "other-state"}
    seed_legacy_session(request)

    client = MagicMock()
    legacy_idp = SimpleNamespace(client_name="SIC", client_id="sic-client-id")
    rp = SimpleNamespace(
        IDP=[legacy_idp], rp_client_name="rpname", dependent_client_ids=[]
    )

    with (
        patch(
            "app.auth_legacy.services.callback.get_config",
            new=AsyncMock(return_value=rp),
        ),
        patch(
            "app.auth_legacy.services.callback.register_client",
            new=AsyncMock(),
        ),
        patch(
            "app.auth_legacy.services.callback.create_client",
            new=AsyncMock(return_value=client),
        ),
        patch(
            "app.auth_legacy.services.callback.patch_legacy_pai",
            new=AsyncMock(),
        ) as mock_patch_legacy_pai,
    ):
        with pytest.raises(OAuthError):
            await legacy_callback(request, "user-at", "user-token", "rp-123")

    mock_patch_legacy_pai.assert_not_awaited()
    assert SessionKeys.LEGACY_LINKING_ATTEMPT_ID.value not in request.session
    assert "legacy_client_name" not in request.session
    assert "legacy_provider" not in request.session
    assert "rpname_SIC_code_verifier" not in request.session
    assert "rpname_SIC_nonce" not in request.session
    assert "rpname_SIC_state" not in request.session
    assert "_state_rpname_SIC_state" not in request.session


@pytest.mark.asyncio
async def test_legacy_callback_rejects_invalid_id_token_nonce():
    request = build_request()
    request.session[SessionKeys.LEGACY_LINKING_ATTEMPT_ID.value] = "attempt-123"
    seed_legacy_session(request)

    client = MagicMock()
    client.authorize_access_token = AsyncMock(return_value={"id_token": "idtok"})
    client.parse_id_token = AsyncMock(side_effect=ValueError("bad nonce"))

    legacy_idp = SimpleNamespace(client_name="SIC", client_id="sic-client-id")
    rp = SimpleNamespace(
        IDP=[legacy_idp], rp_client_name="rpname", dependent_client_ids=[]
    )

    with (
        patch(
            "app.auth_legacy.services.callback.get_config",
            new=AsyncMock(return_value=rp),
        ),
        patch(
            "app.auth_legacy.services.callback.register_client",
            new=AsyncMock(),
        ),
        patch(
            "app.auth_legacy.services.callback.create_client",
            new=AsyncMock(return_value=client),
        ),
        patch(
            "app.auth_legacy.services.callback.patch_legacy_pai",
            new=AsyncMock(),
        ) as mock_patch_legacy_pai,
    ):
        with pytest.raises(OAuthError):
            await legacy_callback(request, "user-at", "user-token", "rp-123")

    mock_patch_legacy_pai.assert_not_awaited()
    assert SessionKeys.LEGACY_LINKING_ATTEMPT_ID.value not in request.session
    assert "legacy_client_name" not in request.session
    assert "legacy_provider" not in request.session
    assert "rpname_SIC_code_verifier" not in request.session
    assert "rpname_SIC_nonce" not in request.session
    assert "rpname_SIC_state" not in request.session
    assert "_state_rpname_SIC_state" not in request.session


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
async def test_oidc_legacy_login_auth_sets_session_and_state():
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
            "app.auth_legacy.services.login.create_client",
            new=AsyncMock(return_value=client),
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
            new=MagicMock(return_value="ibm1"),
        ),
        patch(
            "app.auth_legacy.services.login.get_user_custom_attributes",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "app.auth_legacy.services.login.patch_processing_data",
            new=AsyncMock(return_value=MagicMock(status_code=204)),
        ) as mock_patch_processing_data,
    ):
        result = await oidc_legacy_login_auth(
            request, "user-at", "user-token", "rp-123", "en"
        )

    assert result == "ok"
    assert request.session[SessionKeys.CURRENT_LANGUAGE.value] == "en"
    assert request.session["legacy_provider"] == "SIC"
    assert request.session["legacy_client_name"] == "rpname_SIC"
    assert request.session["rpname_SIC_code_verifier"] == "verifier-token"
    assert request.session["rpname_SIC_state"] == "state-token"
    assert request.session["rpname_SIC_nonce"] == "nonce-token"
    assert request.session[SessionKeys.CORRELATION_ID.value]
    assert request.session[SessionKeys.LEGACY_LINKING_ATTEMPT_ID.value]
    assert (
        mock_patch_processing_data.await_args.kwargs["correlation_id"]
        == request.session[SessionKeys.CORRELATION_ID.value]
    )
    assert (
        mock_patch_processing_data.await_args.kwargs["attempt_id"]
        == request.session[SessionKeys.LEGACY_LINKING_ATTEMPT_ID.value]
    )

    client.authorize_redirect.assert_awaited_once()
    args = client.authorize_redirect.await_args.args
    kwargs = client.authorize_redirect.await_args.kwargs
    assert args[1] == "https://idp.example.test/callback"
    assert kwargs["state"] == "state-token"
    assert kwargs["nonce"] == "nonce-token"
    assert kwargs["code_challenge"] == "challenge-token"
    assert kwargs["code_challenge_method"] == "S256"
    assert kwargs["prompt"] == "login"
    assert kwargs["ui_locales"] == "en-CA"


@pytest.mark.asyncio
@pytest.mark.parametrize("acr_values", ["", "gckey"])
@pytest.mark.parametrize("metadata_shape", ["nested", "flat", "missing_logout"])
async def test_gccf_login_and_callback_link_configured_rp(acr_values, metadata_shape):
    request = build_request()
    rp_client_id = "verify-gccf-rp"
    legacy_client_name = "gccf_migration_GCCF"
    request.session[SessionKeys.RP_CLIENT_ID_KEY.value] = rp_client_id
    request.url_for.return_value = (
        "http://migration.example.test/legacy/logout/callback"
    )
    legacy_idp = SimpleNamespace(
        client_name="GCCF",
        client_id="gccf-consolidator-client",
        client_secret="gccf-secret",
        redirect_uris=["https://migration.example.test/legacy/callback"],
        scope="openid",
        code_challenge_method="S256",
    )
    rp = SimpleNamespace(
        IDP=[legacy_idp],
        rp_client_name="gccf_migration",
        dependent_client_ids=[],
        acr_values=acr_values,
    )
    token = {"id_token": "gccf-id-token+/="}
    client = MagicMock()
    client.authorize_redirect = AsyncMock(
        return_value=RedirectResponse("https://gccf.example.test/authorize")
    )
    client.authorize_access_token = AsyncMock(return_value=token)
    client.parse_id_token = AsyncMock(return_value={"sub": "gccf-legacy-pai"})
    metadata = {"end_session_endpoint": "https://gccf.example.test/logout"}
    if metadata_shape == "nested":
        client.server_metadata = {"server_metadata": metadata}
    elif metadata_shape == "flat":
        client.server_metadata = metadata
    else:
        client.server_metadata = {"server_metadata": {}}
    ok_response = MagicMock(status_code=204)

    with (
        patch(
            "app.auth_legacy.services.login.get_config",
            new=AsyncMock(return_value=rp),
        ),
        patch(
            "app.auth_legacy.services.login.register_client", new=AsyncMock()
        ) as register_login_client,
        patch(
            "app.auth_legacy.services.login.create_client",
            new=AsyncMock(return_value=client),
        ),
        patch("app.auth_legacy.services.login.get_ibm_id", return_value="ibm1"),
        patch(
            "app.auth_legacy.services.login.get_user_custom_attributes",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "app.auth_legacy.services.login.patch_processing_data",
            new=AsyncMock(return_value=ok_response),
        ) as patch_processing,
    ):
        response = await legacy_login(
            request, "user-at", "user-token", rp_client_id, lang="fr"
        )

    assert response.headers["location"] == "https://gccf.example.test/authorize"
    register_login_client.assert_awaited_once_with(
        request, legacy_client_name, legacy_idp, "fr-CA", acr_values
    )
    assert request.session["legacy_provider"] == "GCCF"
    assert request.session["legacy_client_name"] == legacy_client_name
    verifier = request.session[f"{legacy_client_name}_code_verifier"]
    nonce = request.session[f"{legacy_client_name}_nonce"]
    state = request.session[f"{legacy_client_name}_state"]
    expected_challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest())
        .rstrip(b"=")
        .decode("ascii")
    )
    client.authorize_redirect.assert_awaited_once_with(
        request,
        legacy_idp.redirect_uris[0],
        nonce=nonce,
        state=state,
        code_challenge=expected_challenge,
        code_challenge_method="S256",
        prompt="login",
        ui_locales="fr-CA",
    )
    assert patch_processing.await_args.kwargs["rp_client_id"] == rp_client_id
    request.query_params = {"code": "gccf-code", "state": state}

    with (
        patch(
            "app.auth_legacy.services.callback.config",
            new=SimpleNamespace(LEGACY_IDP_LOGOUT_ENABLED=True, ENVIRONMENT="test"),
        ),
        patch(
            "app.auth_legacy.services.callback.get_config",
            new=AsyncMock(return_value=rp),
        ),
        patch(
            "app.auth_legacy.services.callback.has_registered_client",
            return_value=False,
        ),
        patch(
            "app.auth_legacy.services.callback.register_client", new=AsyncMock()
        ) as register_callback_client,
        patch(
            "app.auth_legacy.services.callback.create_client",
            new=AsyncMock(return_value=client),
        ),
        patch("app.auth_legacy.services.callback.get_ibm_id", return_value="ibm1"),
        patch(
            "app.auth_legacy.services.callback.get_user_custom_attributes",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "app.auth_legacy.services.callback.patch_legacy_pai",
            new=AsyncMock(return_value=ok_response),
        ) as patch_pai,
        patch(
            "app.auth_legacy.services.callback.patch_audit_data",
            new=AsyncMock(return_value=ok_response),
        ) as patch_audit,
        patch(
            "app.auth_legacy.services.callback.get_base_profile_management_url",
            return_value="https://profile.example.test",
        ),
    ):
        response = await legacy_callback(request, "user-at", "user-token", rp_client_id)

    register_callback_client.assert_awaited_once_with(
        request, legacy_client_name, legacy_idp, "fr-CA", acr_values
    )
    client.authorize_access_token.assert_awaited_once_with(
        request, code_verifier=verifier
    )
    client.parse_id_token.assert_awaited_once_with(token, nonce)
    assert patch_pai.await_args.kwargs["legacy_pai"] == "gccf-legacy-pai"
    assert patch_pai.await_args.kwargs["rp_client_id"] == rp_client_id
    assert patch_pai.await_args.kwargs["target_rp_client_ids"] == [rp_client_id]
    assert patch_audit.await_args.kwargs["status"] == AuditStatusKeys.LINKED_KEY.value
    assert "legacy_client_name" not in request.session
    assert f"{legacy_client_name}_code_verifier" not in request.session
    if metadata_shape == "missing_logout":
        assert (
            response.headers["location"]
            == "https://profile.example.test/fr/link/lang-sync"
        )
        assert SessionKeys.LEGACY_LINKING_ATTEMPT_ID.value not in request.session
    else:
        logout_url = urlparse(response.headers["location"])
        assert (
            f"{logout_url.scheme}://{logout_url.netloc}{logout_url.path}"
            == metadata["end_session_endpoint"]
        )
        assert parse_qs(logout_url.query) == {
            "client_id": [legacy_idp.client_id],
            "id_token_hint": [token["id_token"]],
            "post_logout_redirect_uri": [
                "https://migration.example.test/legacy/logout/callback"
            ],
            "state": [state],
        }


@pytest.mark.asyncio
async def test_legacy_post_logout_callback_builds_redirect():
    request = build_request()
    request.session[SessionKeys.CURRENT_LANGUAGE.value] = "en"
    request.session[SessionKeys.CORRELATION_ID.value] = "corr-123"
    request.session[SessionKeys.LEGACY_LINKING_ATTEMPT_ID.value] = "attempt-123"
    seed_legacy_session(request)

    config = SimpleNamespace(MIGRATION_SOLUTION_DOMAIN="https://profile.example.test")
    with patch(
        "app.auth_legacy.services.callback.get_configuration",
        return_value=config,
    ):
        response = await legacy_post_logout_callback(request)
    assert isinstance(response, RedirectResponse)
    assert request.state.correlation_id == "corr-123"
    assert request.state.attempt_id == "attempt-123"
    assert SessionKeys.CORRELATION_ID.value in request.session
    assert SessionKeys.LEGACY_LINKING_ATTEMPT_ID.value not in request.session
    assert "legacy_client_name" not in request.session
    assert "legacy_provider" not in request.session
    assert "rpname_SIC_code_verifier" not in request.session
    assert "rpname_SIC_nonce" not in request.session
    assert "rpname_SIC_state" not in request.session
    assert "_state_rpname_SIC_state" not in request.session
    assert response.headers["location"].endswith("/en/link/lang-sync")


@pytest.mark.asyncio
async def test_legacy_post_logout_callback_defaults_to_en_when_lang_missing():
    request = build_request()

    response = await legacy_post_logout_callback(request)

    assert isinstance(response, RedirectResponse)
    assert response.headers["location"].endswith("/en/link/lang-sync")


@pytest.mark.asyncio
async def test_legacy_post_logout_callback_defaults_to_en_when_lang_unsupported():
    request = build_request()
    request.session[SessionKeys.CURRENT_LANGUAGE.value] = "es"

    response = await legacy_post_logout_callback(request)

    assert isinstance(response, RedirectResponse)
    assert response.headers["location"].endswith("/en/link/lang-sync")
