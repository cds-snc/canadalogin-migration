import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.auth.services.auth import verify_audit_status
from app.users.schemas import AuditDataSchema


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
            "app.auth.services.auth.get_http_client",
            new=AsyncMock(side_effect=Exception("boom")),
        ),
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
async def test_verify_audit_status_returns_false_on_missing_custom_attributes():
    request = build_request()

    with (
        patch(
            "app.auth.services.auth.get_users_current_session",
            new=AsyncMock(return_value="token"),
        ),
        patch(
            "app.auth.services.auth.get_user_custom_attributes",
            new=AsyncMock(return_value=None),
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
            new=MagicMock(return_value=["{bad json"]),
        ),
    ):
        result = await verify_audit_status(request)

    assert result is False


@pytest.mark.asyncio
async def test_verify_audit_status_returns_empty_list_on_empty_audit_data():
    request = build_request()

    with (
        patch(
            "app.auth.services.auth.get_users_current_session",
            new=AsyncMock(return_value="token"),
        ),
        patch(
            "app.auth.services.auth.get_user_custom_attributes",
            new=AsyncMock(return_value=[MagicMock()]),
        ),
        patch(
            "app.auth.services.auth.get_custom_attribute",
            new=MagicMock(return_value=[]),
        ),
    ):
        result = await verify_audit_status(request)

    assert result == []


@pytest.mark.asyncio
async def test_verify_audit_status_returns_parsed_audit_list():
    request = build_request()
    audit_json = (
        '{"client_id":"rp-123","legacy_idp":"","timestamp":"2024-01-01 00:00:00","status":"LINKED"}'
    )

    with (
        patch(
            "app.auth.services.auth.get_users_current_session",
            new=AsyncMock(return_value="token"),
        ),
        patch(
            "app.auth.services.auth.get_user_custom_attributes",
            new=AsyncMock(return_value=[MagicMock()]),
        ),
        patch(
            "app.auth.services.auth.get_custom_attribute",
            new=MagicMock(return_value=[audit_json]),
        ),
    ):
        result = await verify_audit_status(request)

    assert isinstance(result, list)
    assert isinstance(result[0], AuditDataSchema)
    assert result[0].client_id == "rp-123"
