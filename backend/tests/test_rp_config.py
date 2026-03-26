import json
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.rp.services.config import get_config, get_config_json, get_rp_config_details


def _sample_rp_config(include_inline_secret: bool = False):
    idp_entry = {
        "client_id": "cid",
        "client_name": "SIC",
        "openid_configuration": "https://idp.example.test/.well-known/openid-configuration",
        "redirect_uris": ["https://rp.example.test/callback"],
        "scope": "openid",
        "max_age": 3600,
        "code_challenge_method": "S256",
    }
    if include_inline_secret:
        idp_entry["client_secret"] = "secret"

    return [
        {
            "rp_client_id": "rp-123",
            "rp_client_name": "rp",
            "rp_client_name_en": "rp en",
            "rp_client_name_fr": "rp fr",
            "rp_redirect_uri": "https://rp.example.test/landing",
            "acr_values": "",
            "IDP": [idp_entry],
        }
    ]


def _sample_rp_secrets():
    return [{"client_id": "cid", "client_secret": "secret"}]


@pytest.mark.asyncio
async def test_get_config_returns_matching_rp(monkeypatch):
    monkeypatch.setenv("RP_MIGRATION_CONFIG", json.dumps(_sample_rp_config()))
    monkeypatch.setenv("RP_MIGRATION_CONFIG_SECRETS", json.dumps(_sample_rp_secrets()))

    with patch("app.rp.services.config._CONFIG_JSON_CACHE", None):
        rp = await get_config("rp-123")

    assert rp.rp_client_id == "rp-123"
    assert rp.IDP[0].client_name == "SIC"
    assert rp.IDP[0].client_secret == "secret"


@pytest.mark.asyncio
async def test_get_config_raises_when_missing(monkeypatch):
    monkeypatch.setenv("RP_MIGRATION_CONFIG", json.dumps(_sample_rp_config()))
    monkeypatch.setenv("RP_MIGRATION_CONFIG_SECRETS", json.dumps(_sample_rp_secrets()))

    with patch("app.rp.services.config._CONFIG_JSON_CACHE", None):
        with pytest.raises(HTTPException) as raised:
            await get_config("missing")

    assert raised.value.status_code == 404


@pytest.mark.asyncio
async def test_get_config_json_raises_on_invalid_json(monkeypatch):
    monkeypatch.setenv("RP_MIGRATION_CONFIG", "not-json")

    with patch("app.rp.services.config._CONFIG_JSON_CACHE", None):
        with pytest.raises(ValueError):
            await get_config_json()


@pytest.mark.asyncio
async def test_get_config_raises_on_invalid_schema(monkeypatch):
    invalid = _sample_rp_config()
    invalid[0].pop("rp_client_name", None)
    monkeypatch.setenv("RP_MIGRATION_CONFIG", json.dumps(invalid))
    monkeypatch.setenv("RP_MIGRATION_CONFIG_SECRETS", json.dumps(_sample_rp_secrets()))

    with patch("app.rp.services.config._CONFIG_JSON_CACHE", None):
        with pytest.raises(ValidationError):
            await get_config("rp-123")


@pytest.mark.asyncio
async def test_get_config_json_raises_on_unexpected_structure(monkeypatch):
    monkeypatch.setenv("RP_MIGRATION_CONFIG", json.dumps({"foo": "bar"}))

    with patch("app.rp.services.config._CONFIG_JSON_CACHE", None):
        with pytest.raises(ValueError):
            await get_config_json()


@pytest.mark.asyncio
async def test_get_rp_config_details_marks_gckey_only_when_configured(monkeypatch):
    config = _sample_rp_config()
    config[0]["acr_values"] = "gckey, MFA"
    monkeypatch.setenv("RP_MIGRATION_CONFIG", json.dumps(config))
    monkeypatch.setenv("RP_MIGRATION_CONFIG_SECRETS", json.dumps(_sample_rp_secrets()))

    with patch("app.rp.services.config._CONFIG_JSON_CACHE", None):
        details = await get_rp_config_details("rp-123")

    assert details["acr_values"] == "gckey, MFA"
    assert details["is_gckey_only"] is True


@pytest.mark.asyncio
async def test_get_rp_config_details_marks_not_gckey_only_when_blank(monkeypatch):
    monkeypatch.setenv("RP_MIGRATION_CONFIG", json.dumps(_sample_rp_config()))
    monkeypatch.setenv("RP_MIGRATION_CONFIG_SECRETS", json.dumps(_sample_rp_secrets()))

    with patch("app.rp.services.config._CONFIG_JSON_CACHE", None):
        details = await get_rp_config_details("rp-123")

    assert details["acr_values"] == ""
    assert details["is_gckey_only"] is False


@pytest.mark.asyncio
async def test_get_rp_config_details_appends_custom_parameters(monkeypatch):
    monkeypatch.setenv("RP_MIGRATION_CONFIG", json.dumps(_sample_rp_config()))
    monkeypatch.setenv("RP_MIGRATION_CONFIG_SECRETS", json.dumps(_sample_rp_secrets()))

    with patch("app.rp.services.config._CONFIG_JSON_CACHE", None):
        details = await get_rp_config_details(
            "rp-123",
            custom_parameters={"fakeparam1": "value-1", "fakeparam2": "value-2"},
        )

    assert (
        details["rp_redirect_url"]
        == "https://rp.example.test/landing?fakeparam1=value-1&fakeparam2=value-2"
    )


@pytest.mark.asyncio
async def test_get_rp_config_details_prefers_language_specific_redirect(monkeypatch):
    config = _sample_rp_config()
    config[0]["rp_redirect_uri_en"] = "https://rp.example.test/landing/en"
    config[0]["rp_redirect_uri_fr"] = "https://rp.example.test/landing/fr"
    monkeypatch.setenv("RP_MIGRATION_CONFIG", json.dumps(config))
    monkeypatch.setenv("RP_MIGRATION_CONFIG_SECRETS", json.dumps(_sample_rp_secrets()))

    with patch("app.rp.services.config._CONFIG_JSON_CACHE", None):
        details = await get_rp_config_details("rp-123", language="fr-CA")

    assert details["rp_redirect_url"] == "https://rp.example.test/landing/fr"


@pytest.mark.asyncio
async def test_get_config_json_tolerates_missing_secret_for_client_id(monkeypatch):
    monkeypatch.setenv("RP_MIGRATION_CONFIG", json.dumps(_sample_rp_config()))
    monkeypatch.delenv("RP_MIGRATION_CONFIG_SECRETS", raising=False)

    with patch("app.rp.services.config._CONFIG_JSON_CACHE", None):
        payload = await get_config_json()

    assert payload[0]["IDP"][0]["client_id"] == "cid"
    assert payload[0]["IDP"][0].get("client_secret") is None


@pytest.mark.asyncio
async def test_get_config_allows_missing_secret_for_client_id(monkeypatch):
    monkeypatch.setenv("RP_MIGRATION_CONFIG", json.dumps(_sample_rp_config()))
    monkeypatch.delenv("RP_MIGRATION_CONFIG_SECRETS", raising=False)

    with patch("app.rp.services.config._CONFIG_JSON_CACHE", None):
        rp = await get_config("rp-123")

    assert rp.IDP[0].client_id == "cid"
    assert rp.IDP[0].client_secret is None


@pytest.mark.asyncio
async def test_get_config_uses_inline_secret_when_secrets_env_missing(monkeypatch):
    monkeypatch.setenv(
        "RP_MIGRATION_CONFIG", json.dumps(_sample_rp_config(include_inline_secret=True))
    )
    monkeypatch.delenv("RP_MIGRATION_CONFIG_SECRETS", raising=False)

    with patch("app.rp.services.config._CONFIG_JSON_CACHE", None):
        rp = await get_config("rp-123")

    assert rp.IDP[0].client_secret == "secret"


@pytest.mark.asyncio
async def test_get_config_json_raises_on_duplicate_secret_client_ids(monkeypatch):
    monkeypatch.setenv("RP_MIGRATION_CONFIG", json.dumps(_sample_rp_config()))
    monkeypatch.setenv(
        "RP_MIGRATION_CONFIG_SECRETS",
        json.dumps(
            [
                {"client_id": "cid", "client_secret": "first"},
                {"client_id": "cid", "client_secret": "second"},
            ]
        ),
    )

    with patch("app.rp.services.config._CONFIG_JSON_CACHE", None):
        with pytest.raises(ValueError, match="Duplicate client_id"):
            await get_config_json()


@pytest.mark.asyncio
async def test_get_config_json_ignores_unused_secret_client_ids(monkeypatch):
    monkeypatch.setenv("RP_MIGRATION_CONFIG", json.dumps(_sample_rp_config()))
    monkeypatch.setenv(
        "RP_MIGRATION_CONFIG_SECRETS",
        json.dumps(
            [
                {"client_id": "cid", "client_secret": "secret"},
                {"client_id": "unused-cid", "client_secret": "unused-secret"},
            ]
        ),
    )

    with patch("app.rp.services.config._CONFIG_JSON_CACHE", None):
        payload = await get_config_json()

    assert payload[0]["IDP"][0]["client_secret"] == "secret"
