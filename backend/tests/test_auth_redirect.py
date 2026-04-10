import json
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.auth.services.auth import redirect_user_to_idp_verify
from app.constants.session_keys import SessionKeys
from app.utils.auth_flow_logging import hash_identifier


def build_request():
    request = MagicMock()
    request.session = {}
    request.url_for = MagicMock(return_value="http://localhost/v1/auth/callback")
    request.state = MagicMock()
    return request


@pytest.mark.asyncio
async def test_redirect_user_to_idp_verify_creates_session_correlation_id():
    request = build_request()
    oauth = SimpleNamespace(
        verify=SimpleNamespace(authorize_redirect=AsyncMock(return_value="ok"))
    )

    with (
        patch(
            "app.auth.services.auth.get_configuration",
            return_value=SimpleNamespace(ENVIRONMENT="local"),
        ),
        patch("app.auth.services.auth.oauth", new=oauth),
    ):
        result = await redirect_user_to_idp_verify(request, "rp-123", "en")

    assert result == "ok"
    assert request.session[SessionKeys.RP_CLIENT_ID_KEY.value] == "rp-123"
    assert request.session[SessionKeys.CORRELATION_ID.value]
    assert (
        request.state.correlation_id
        == request.session[SessionKeys.CORRELATION_ID.value]
    )
    oauth.verify.authorize_redirect.assert_awaited_once_with(
        request,
        "http://localhost/v1/auth/callback?lang=en",
        ui_locales="en",
    )


@pytest.mark.asyncio
async def test_redirect_user_to_idp_verify_reuses_existing_session_correlation_id():
    request = build_request()
    request.session[SessionKeys.CORRELATION_ID.value] = "corr-existing"
    oauth = SimpleNamespace(
        verify=SimpleNamespace(authorize_redirect=AsyncMock(return_value="ok"))
    )

    with (
        patch(
            "app.auth.services.auth.get_configuration",
            return_value=SimpleNamespace(ENVIRONMENT="local"),
        ),
        patch("app.auth.services.auth.oauth", new=oauth),
    ):
        await redirect_user_to_idp_verify(request, "rp-123", "en")

    assert request.session[SessionKeys.CORRELATION_ID.value] == "corr-existing"
    assert request.state.correlation_id == "corr-existing"


@pytest.mark.asyncio
async def test_redirect_user_to_idp_verify_logs_auth_flow_events(caplog):
    request = build_request()
    oauth = SimpleNamespace(
        verify=SimpleNamespace(authorize_redirect=AsyncMock(return_value="ok"))
    )

    caplog.set_level(logging.INFO)
    with (
        patch(
            "app.auth.services.auth.get_configuration",
            return_value=SimpleNamespace(ENVIRONMENT="local"),
        ),
        patch("app.auth.services.auth.oauth", new=oauth),
    ):
        await redirect_user_to_idp_verify(request, "rp-123", "en")

    auth_flow_logs = [
        json.loads(record.message)
        for record in caplog.records
        if '"event": "auth_flow"' in record.message
    ]
    assert auth_flow_logs == [
        {
            "code": "GCAuth.Migration.INFO.AUTH_FLOW",
            "event": "auth_flow",
            "flow": "verify",
            "step": "authorize_redirect",
            "outcome": "started",
            "context": {
                "correlation_id": request.session[SessionKeys.CORRELATION_ID.value],
                "rp_client_id_hash": hash_identifier("rp-123"),
                "lang": "en",
            },
        },
        {
            "code": "GCAuth.Migration.INFO.AUTH_FLOW",
            "event": "auth_flow",
            "flow": "verify",
            "step": "authorize_redirect",
            "outcome": "succeeded",
            "context": {
                "correlation_id": request.session[SessionKeys.CORRELATION_ID.value],
                "rp_client_id_hash": hash_identifier("rp-123"),
                "lang": "en",
            },
        },
    ]
