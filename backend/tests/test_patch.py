import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from app.users.services.patch import (
    patching_payload,
    patch_custom_attribute,
    patch_processing_data,
    patch_legacy_pai,
    patch_audit_data,
)
from app.constants.patch_keys import PatchKeys


def _extract_custom_attribute_values(payload: str) -> list:
    payload_dict = json.loads(payload)
    operations = payload_dict.get("Operations", [])
    for op in operations:
        if op.get("path") == (
            "urn:ietf:params:scim:schemas:extension:ibm:2.0:User:customAttributes"
        ):
            return op["value"][0]["values"]
    raise AssertionError("customAttributes operation not found")


@pytest.mark.asyncio
async def test_patching_payload_builds_scim_patch():
    payload = await patching_payload("customKey", ["value1"])
    payload_dict = json.loads(payload)

    assert payload_dict["schemas"] == ["urn:ietf:params:scim:api:messages:2.0:PatchOp"]
    assert len(payload_dict["Operations"]) == 2

    custom_op = payload_dict["Operations"][0]
    assert custom_op["op"] == "add"
    assert custom_op["path"].endswith("customAttributes")
    assert custom_op["value"][0]["name"] == "customKey"
    assert custom_op["value"][0]["values"] == ["value1"]

    notify_op = payload_dict["Operations"][1]
    assert notify_op["path"].endswith("Notification:notifyType")
    assert notify_op["value"] == "NONE"


@pytest.mark.asyncio
async def test_patching_payload_raises_on_invalid_values():
    with pytest.raises(HTTPException) as raised:
        await patching_payload("customKey", None)

    assert raised.value.status_code == 422


@pytest.mark.asyncio
async def test_patch_custom_attribute_returns_response():
    http_client = AsyncMock()
    response = MagicMock(status_code=204)
    http_client.patch = AsyncMock(return_value=response)

    with patch(
        "app.users.services.patch.get_admin_token",
        new=AsyncMock(return_value="admin-token"),
    ):
        result = await patch_custom_attribute(http_client, "ibm1", '{"x":"y"}')

    assert result is response
    http_client.patch.assert_awaited_once()


@pytest.mark.asyncio
async def test_patch_processing_data_creates_new_record_on_empty_attributes():
    http_client = AsyncMock()

    with patch(
        "app.users.services.patch.patch_custom_attribute",
        new=AsyncMock(return_value=MagicMock(status_code=204)),
    ) as mock_patch:
        await patch_processing_data(http_client, "ibm1", "rp-123", [])

    mock_patch.assert_awaited_once()
    patch_payload = mock_patch.await_args.kwargs["patch_payload"]
    values = _extract_custom_attribute_values(patch_payload)
    parsed = json.loads(values[0])
    assert parsed["client_id"] == "rp-123"
    assert parsed["retry_count"] == 1


@pytest.mark.asyncio
async def test_patch_processing_data_updates_existing_record():
    http_client = AsyncMock()
    existing = {"client_id": "rp-123", "retry_count": 1, "timestamp": "2020-01-01 00:00:00"}

    with (
        patch(
            "app.users.services.patch.get_custom_attribute",
            new=AsyncMock(return_value=[json.dumps(existing)]),
        ),
        patch(
            "app.users.services.patch.patch_custom_attribute",
            new=AsyncMock(return_value=MagicMock(status_code=204)),
        ) as mock_patch,
    ):
        await patch_processing_data(http_client, "ibm1", "rp-123", [])

    patch_payload = mock_patch.await_args.kwargs["patch_payload"]
    values = _extract_custom_attribute_values(patch_payload)
    parsed = json.loads(values[0])
    assert parsed["client_id"] == "rp-123"
    assert parsed["retry_count"] == 2


@pytest.mark.asyncio
async def test_patch_processing_data_raises_on_malformed_json():
    http_client = AsyncMock()

    with patch(
        "app.users.services.patch.get_custom_attribute",
        new=AsyncMock(return_value=["{bad json"]),
    ):
        with pytest.raises(Exception):
            await patch_processing_data(http_client, "ibm1", "rp-123", [])


@pytest.mark.asyncio
async def test_patch_legacy_pai_creates_new_entry_on_empty_attributes():
    http_client = AsyncMock()

    with patch(
        "app.users.services.patch.patch_custom_attribute",
        new=AsyncMock(return_value=MagicMock(status_code=204)),
    ) as mock_patch:
        await patch_legacy_pai(http_client, "ibm1", "rp-123", [], "legacy-pai")

    mock_patch.assert_awaited_once()
    patch_payload = mock_patch.await_args.kwargs["patch_payload"]
    values = _extract_custom_attribute_values(patch_payload)
    parsed = json.loads(values[0])
    assert parsed["client_id"] == "rp-123"
    assert parsed["pai"] == "legacy-pai"


@pytest.mark.asyncio
async def test_patch_legacy_pai_appends_duplicate_client_id():
    http_client = AsyncMock()
    existing = {"client_id": "rp-123", "pai": "old-pai"}

    with (
        patch(
            "app.users.services.patch.get_custom_attribute",
            new=AsyncMock(return_value=[json.dumps(existing)]),
        ),
        patch(
            "app.users.services.patch.patch_custom_attribute",
            new=AsyncMock(return_value=MagicMock(status_code=204)),
        ) as mock_patch,
    ):
        await patch_legacy_pai(http_client, "ibm1", "rp-123", [], "legacy-pai")

    patch_payload = mock_patch.await_args.kwargs["patch_payload"]
    values = _extract_custom_attribute_values(patch_payload)
    parsed = [json.loads(item) for item in values]
    assert len(parsed) == 2
    assert parsed[0]["client_id"] == "rp-123"
    assert parsed[1]["client_id"] == "rp-123"


@pytest.mark.asyncio
async def test_patch_audit_data_creates_new_entry_with_timestamp():
    http_client = AsyncMock()

    with patch(
        "app.users.services.patch.patch_custom_attribute",
        new=AsyncMock(return_value=MagicMock(status_code=204)),
    ) as mock_patch:
        await patch_audit_data(
            http_client, "ibm1", "rp-123", [], status="LINKED"
        )

    mock_patch.assert_awaited_once()
    patch_payload = mock_patch.await_args.kwargs["patch_payload"]
    values = _extract_custom_attribute_values(patch_payload)
    parsed = json.loads(values[0])
    assert parsed["client_id"] == "rp-123"
    assert parsed["status"] == "LINKED"
    datetime.strptime(parsed["timestamp"], "%Y-%m-%d %H:%M:%S")
