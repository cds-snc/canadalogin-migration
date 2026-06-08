import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.rp.schemas import LegacyIdpSchema
from app.utils import oidc
from app.utils.oidc import create_client, has_registered_client, register_client


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


def test_has_registered_client_reads_oauth_registry():
    with patch.dict(
        "app.utils.oidc.oauth._clients", {"rpname_SIC": object()}, clear=True
    ):
        assert has_registered_client("rpname_SIC") is True
        assert has_registered_client("other_client") is False


@pytest.mark.asyncio
async def test_create_client_raises_when_client_is_not_registered():
    with patch("app.utils.oidc.oauth.create_client", return_value=None):
        with pytest.raises(HTTPException) as raised:
            await create_client("missing-client")

    assert raised.value.status_code == 500
    assert raised.value.detail == "Failed to create OIDC client"


@pytest.mark.asyncio
async def test_create_client_waits_for_in_progress_registration():
    request = _build_request()
    idp = _build_idp()
    client_name = "rpname_SIC"
    previous_client = object()
    registered_client = object()
    registration_gap_open = asyncio.Event()
    allow_registration_to_finish = asyncio.Event()

    async def delayed_metadata(_request, _openid_configuration):
        registration_gap_open.set()
        await allow_registration_to_finish.wait()
        return _build_metadata()

    def store_registered_client(**kwargs):
        oidc.oauth._clients[kwargs["name"]] = registered_client

    with (
        patch.dict(oidc.oauth._clients, {client_name: previous_client}, clear=True),
        patch(
            "app.utils.oidc.get_legacy_idp_metadata",
            new=AsyncMock(side_effect=delayed_metadata),
        ),
        patch("app.utils.oidc.oauth.register", side_effect=store_registered_client),
        patch(
            "app.utils.oidc.oauth.create_client",
            side_effect=lambda name: oidc.oauth._clients.get(name),
        ),
    ):
        register_task = asyncio.create_task(
            register_client(
                request,
                client_name=client_name,
                idp=idp,
                ui_locales="en-CA",
                acr_values="",
            )
        )
        await registration_gap_open.wait()
        assert client_name not in oidc.oauth._clients

        create_task = asyncio.create_task(create_client(client_name))
        await asyncio.sleep(0)
        assert not create_task.done()

        allow_registration_to_finish.set()
        await register_task
        assert await create_task is registered_client
