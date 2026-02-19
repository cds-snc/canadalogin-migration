import json
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.rp.services.config import get_config, get_config_json


def _sample_rp_config():
    return [
        {
            "rp_client_id": "rp-123",
            "rp_client_name": "rp",
            "rp_client_name_en": "rp en",
            "rp_client_name_fr": "rp fr",
            "rp_redirect_uri": "https://rp.example.test/landing",
            "IDP": [
                {
                    "client_id": "cid",
                    "client_name": "SIC",
                    "client_secret": "secret",
                    "openid_configuration": "https://idp.example.test/.well-known/openid-configuration",
                    "redirect_uris": ["https://rp.example.test/callback"],
                    "scope": "openid",
                    "max_age": 3600,
                    "code_challenge_method": "S256",
                }
            ],
        }
    ]


@pytest.mark.asyncio
async def test_get_config_returns_matching_rp(monkeypatch):
    monkeypatch.setenv("RP_MIGRATION_CONFIG", json.dumps(_sample_rp_config()))

    with patch("app.rp.services.config._CONFIG_JSON_CACHE", None):
        rp = await get_config("rp-123")

    assert rp.rp_client_id == "rp-123"
    assert rp.IDP[0].client_name == "SIC"


@pytest.mark.asyncio
async def test_get_config_raises_when_missing(monkeypatch):
    monkeypatch.setenv("RP_MIGRATION_CONFIG", json.dumps(_sample_rp_config()))

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

    with patch("app.rp.services.config._CONFIG_JSON_CACHE", None):
        with pytest.raises(ValidationError):
            await get_config("rp-123")


@pytest.mark.asyncio
async def test_get_config_json_raises_on_unexpected_structure(monkeypatch):
    monkeypatch.setenv("RP_MIGRATION_CONFIG", json.dumps({"foo": "bar"}))

    with patch("app.rp.services.config._CONFIG_JSON_CACHE", None):
        with pytest.raises(ValueError):
            await get_config_json()
