import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.auth.services.auth import verify_audit_status


def build_request():
    request = MagicMock()
    request.session = {}
    request.app = MagicMock()
    request.app.state = MagicMock()
    request.app.state.request_client = AsyncMock()
    return request


@pytest.mark.asyncio
async def test_verify_audit_status_returns_false_on_session_error():
    request = build_request()

    with (
        patch(
            "app.auth.services.auth.get_users_current_session",
            new=AsyncMock(side_effect=Exception("boom")),
        ),
    ):
        result = await verify_audit_status(request)

    assert result is False


@pytest.mark.asyncio
async def test_verify_audit_status_returns_false_on_custom_attributes_error():
    request = build_request()

    with (
        patch(
            "app.auth.services.auth.get_users_current_session",
            new=AsyncMock(return_value="token"),
        ),
        patch(
            "app.auth.services.auth.get_user_custom_attributes",
            new=AsyncMock(side_effect=Exception("boom")),
        ),
    ):
        result = await verify_audit_status(request)

    assert result is False


@pytest.mark.asyncio
async def test_verify_audit_status_returns_false_on_malformed_audit_json():
    request = build_request()

    with (
        patch(
            "app.auth.services.auth.get_users_current_session",
            new=AsyncMock(return_value="token"),
        ),
        patch(
            "app.auth.services.auth.get_user_custom_attributes",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "app.auth.services.auth.get_custom_attribute",
            new=AsyncMock(return_value=["{bad json"]),
        ),
    ):
        result = await verify_audit_status(request)

    assert result is False


@pytest.mark.asyncio
async def test_verify_audit_status_returns_none_on_empty_audit_data():
    request = build_request()

    with (
        patch(
            "app.auth.services.auth.get_users_current_session",
            new=AsyncMock(return_value="token"),
        ),
        patch(
            "app.auth.services.auth.get_user_custom_attributes",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "app.auth.services.auth.get_custom_attribute",
            new=AsyncMock(return_value=[]),
        ),
    ):
        result = await verify_audit_status(request)

    assert result is None
