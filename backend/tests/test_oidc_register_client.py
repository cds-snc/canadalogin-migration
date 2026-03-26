from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.rp.schemas import LegacyIdpSchema
from app.utils.oidc import register_client


def _build_request():
    return SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(request_client=MagicMock()))
    )


def _build_idp():
    return LegacyIdpSchema(
        client_id="cid",
        client_name="SIC",
        client_secret="secret",
        openid_configuration="https://idp.example.test/.well-known/openid-configuration",
        redirect_uris=["https://rp.example.test/callback"],
        scope="openid",
        max_age=0,
        code_challenge_method="S256",
    )


def _build_metadata():
    return {
        "authorization_endpoint": "https://idp.example.test/authorize",
        "token_endpoint": "https://idp.example.test/token",
        "jwks_uri": "https://idp.example.test/jwks",
    }


@pytest.mark.asyncio
async def test_register_client_uses_configured_acr_values():
    request = _build_request()
    idp = _build_idp()

    with (
        patch(
            "app.utils.oidc.get_legacy_idp_metadata",
            new=AsyncMock(return_value=_build_metadata()),
        ),
        patch("app.utils.oidc.oauth.register") as mock_register,
    ):
        await register_client(
            request,
            client_name="rpname_SIC",
            idp=idp,
            ui_locales="en-CA",
            acr_values="gckey, mfa",
        )

    authorize_params = mock_register.call_args.kwargs["authorize_params"]
    assert authorize_params["ui_locales"] == "en-CA"
    assert authorize_params["acr_values"] == "gckey,mfa"


@pytest.mark.asyncio
async def test_register_client_omits_acr_values_when_blank():
    request = _build_request()
    idp = _build_idp()

    with (
        patch(
            "app.utils.oidc.get_legacy_idp_metadata",
            new=AsyncMock(return_value=_build_metadata()),
        ),
        patch("app.utils.oidc.oauth.register") as mock_register,
    ):
        await register_client(
            request,
            client_name="rpname_SIC",
            idp=idp,
            ui_locales="en-CA",
            acr_values="",
        )

    authorize_params = mock_register.call_args.kwargs["authorize_params"]
    assert authorize_params["ui_locales"] == "en-CA"
    assert "acr_values" not in authorize_params


@pytest.mark.asyncio
async def test_register_client_preserves_acr_value_casing():
    request = _build_request()
    idp = _build_idp()

    with (
        patch(
            "app.utils.oidc.get_legacy_idp_metadata",
            new=AsyncMock(return_value=_build_metadata()),
        ),
        patch("app.utils.oidc.oauth.register") as mock_register,
    ):
        await register_client(
            request,
            client_name="rpname_SIC",
            idp=idp,
            ui_locales="en-CA",
            acr_values="gckey, MFA",
        )

    authorize_params = mock_register.call_args.kwargs["authorize_params"]
    assert authorize_params["ui_locales"] == "en-CA"
    assert authorize_params["acr_values"] == "gckey,MFA"


@pytest.mark.asyncio
async def test_register_client_omits_client_secret_when_missing():
    request = _build_request()
    idp = _build_idp()
    idp.client_secret = None

    with (
        patch(
            "app.utils.oidc.get_legacy_idp_metadata",
            new=AsyncMock(return_value=_build_metadata()),
        ),
        patch("app.utils.oidc.oauth.register") as mock_register,
    ):
        await register_client(
            request,
            client_name="rpname_SIC",
            idp=idp,
            ui_locales="en-CA",
            acr_values="",
        )

    assert "client_secret" not in mock_register.call_args.kwargs
