from copy import deepcopy
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from fastapi import Response

from app.auth_legacy.v1_router import handle_skip_account_linking
from app.constants.session_keys import SessionKeys
from app.rp.v1_router import handle_get_rp_config_details


def build_request(language):
    request = MagicMock()
    request.session = {
        SessionKeys.RP_CLIENT_ID_KEY.value: "rp-123",
        SessionKeys.SESSION_USER_TOKEN.value: "user-token",
        SessionKeys.CURRENT_LANGUAGE.value: language,
        SessionKeys.CUSTOM_PARAMETERS.value: {
            "state": "original RP transaction / 123",
            "lang": "stale",
            "ui_locales": "stale",
        },
    }
    request.app.state.request_client = AsyncMock()
    return request


@pytest.mark.asyncio
@pytest.mark.parametrize("language", ["en", "fr"])
@pytest.mark.parametrize("localized", [True, False], ids=["localized", "legacy-uri"])
async def test_recovery_uses_completion_and_skip_destination(language, localized):
    rp = {
        "rp_client_id": "rp-123",
        "rp_client_name": "Test service",
        "rp_client_name_en": "Test service",
        "rp_client_name_fr": "Service de test",
        "rp_redirect_uri": "https://service.example/account?source=config#continue",
        "IDP": [],
    }
    if localized:
        rp.update(
            rp_redirect_uri_en="https://service.example/en/account?source=config#continue",
            rp_redirect_uri_fr="https://service.example/fr/account?source=config#continue",
        )

    previous_language = "fr" if language == "en" else "en"
    recovery_request = build_request(previous_language)
    original_session = deepcopy(recovery_request.session)
    recovery_response = Response()

    with (
        patch(
            "app.rp.services.config.get_config_json",
            new=AsyncMock(return_value=[rp]),
        ),
        patch(
            "app.auth_legacy.services.skip.get_migration_attributes",
            new=AsyncMock(return_value=[]),
        ) as read_migration,
        patch("app.auth_legacy.services.skip.get_ibm_id", return_value="ibm-user"),
        patch(
            "app.auth_legacy.services.skip.patch_audit_data",
            new=AsyncMock(return_value=httpx.Response(204)),
        ) as patch_audit,
    ):
        recovery = await handle_get_rp_config_details(
            recovery_request, recovery_response, lang=language
        )
        completion = await handle_get_rp_config_details(
            build_request(language), Response()
        )

        # Reading the return destination must neither repeat migration nor
        # change the session when the recovery page switches language.
        read_migration.assert_not_awaited()
        patch_audit.assert_not_awaited()
        assert recovery_request.session == original_session

        skipped = await handle_skip_account_linking(
            build_request(previous_language),
            lang=language,
            user_access_token="user-access-token",
        )

    assert recovery["rp_client_id"] == "rp-123"
    assert recovery_response.headers["Cache-Control"] == "no-store"
    assert recovery["rp_redirect_url"] == completion["rp_redirect_url"]
    assert recovery["rp_redirect_url"] == skipped.redirect_url
    destination = urlsplit(recovery["rp_redirect_url"])
    assert destination.scheme == "https"
    assert destination.netloc == "service.example"
    expected_path = f"/{language}/account" if localized else "/account"
    assert destination.path == expected_path
    assert destination.fragment == "continue"
    assert parse_qs(destination.query) == {
        "source": ["config"],
        "state": ["original RP transaction / 123"],
        "lang": [language],
        "ui_locales": [f"{language}-CA"],
    }
    patch_audit.assert_awaited_once()
