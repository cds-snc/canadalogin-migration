import json
import logging
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
    payload = patching_payload("customKey", ["value1"])
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
        patching_payload("customKey", None)

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
async def test_patch_custom_attribute_returns_unauthorized_error():
    http_client = AsyncMock()
    response = MagicMock(status_code=401)
    response.json = MagicMock(
        return_value={"detail": "invalid token", "access_token": "secret"}
    )
    http_client.patch = AsyncMock(return_value=response)

    with patch(
        "app.users.services.patch.get_admin_token",
        new=AsyncMock(return_value="admin-token"),
    ):
        result = await patch_custom_attribute(http_client, "ibm1", '{"x":"y"}')

    assert result == {"error": "Unauthorized: Invalid credentials or token"}


@pytest.mark.asyncio
async def test_patch_custom_attribute_returns_http_error(caplog):
    http_client = AsyncMock()
    response = MagicMock(status_code=500)
    response.json = MagicMock(
        return_value={"detail": "upstream patch failed", "access_token": "secret"}
    )
    http_client.patch = AsyncMock(return_value=response)

    caplog.set_level(logging.ERROR)
    with patch(
        "app.users.services.patch.get_admin_token",
        new=AsyncMock(return_value="admin-token"),
    ):
        result = await patch_custom_attribute(http_client, "ibm1", '{"x":"y"}')

    assert result == {"error": "HTTP error: 500"}
    assert "upstream patch failed" in caplog.text
    assert "secret" not in caplog.text


@pytest.mark.asyncio
async def test_patch_processing_data_creates_new_record_on_empty_attributes():
    http_client = AsyncMock()

    with patch(
        "app.users.services.patch.patch_custom_attribute",
        new=AsyncMock(return_value=MagicMock(status_code=204)),
    ) as mock_patch:
        await patch_processing_data(
            http_client,
            "ibm1",
            "rp-123",
            [],
            correlation_id="corr-123",
            attempt_id="attempt-123",
        )

    mock_patch.assert_awaited_once()
    assert mock_patch.await_args.args[0] is http_client
    patch_payload = mock_patch.await_args.kwargs["patch_payload"]
    values = _extract_custom_attribute_values(patch_payload)
    parsed = json.loads(values[0])
    assert parsed["client_id"] == "rp-123"
    assert parsed["retry_count"] == 0
    assert parsed["first_attempt_timestamp"] == parsed["timestamp"]
    assert parsed["last_attempt_timestamp"] == parsed["timestamp"]
    assert parsed["correlation_id"] == "corr-123"
    assert parsed["attempt_id"] == "attempt-123"
    assert "attempts" not in parsed


@pytest.mark.asyncio
async def test_patch_processing_data_updates_existing_client_summary():
    http_client = AsyncMock()
    existing = {
        "client_id": "rp-123",
        "retry_count": 1,
        "timestamp": "2020-01-01 00:00:00",
    }

    with (
        patch(
            "app.users.services.patch.get_custom_attribute",
            new=MagicMock(return_value=[json.dumps(existing)]),
        ),
        patch(
            "app.users.services.patch.patch_custom_attribute",
            new=AsyncMock(return_value=MagicMock(status_code=204)),
        ) as mock_patch,
    ):
        await patch_processing_data(
            http_client,
            "ibm1",
            "rp-123",
            [],
            correlation_id="corr-456",
            attempt_id="attempt-456",
        )

    patch_payload = mock_patch.await_args.kwargs["patch_payload"]
    assert mock_patch.await_args.args[0] is http_client
    values = _extract_custom_attribute_values(patch_payload)
    parsed_values = [json.loads(value) for value in values]

    assert len(parsed_values) == 1
    assert parsed_values[0]["client_id"] == "rp-123"
    assert parsed_values[0]["retry_count"] == 1
    assert parsed_values[0]["first_attempt_timestamp"] == "2020-01-01 00:00:00"
    assert parsed_values[0]["last_attempt_timestamp"] == parsed_values[0]["timestamp"]
    assert parsed_values[0]["correlation_id"] == "corr-456"
    assert parsed_values[0]["attempt_id"] == "attempt-456"
    assert "attempts" not in parsed_values[0]


@pytest.mark.asyncio
async def test_patch_processing_data_keeps_summary_retry_count_without_ids():
    http_client = AsyncMock()
    existing = {
        "client_id": "rp-123",
        "retry_count": 3,
        "timestamp": "2020-01-04 00:00:00",
        "first_attempt_timestamp": "2020-01-01 00:00:00",
        "last_attempt_timestamp": "2020-01-04 00:00:00",
    }

    with (
        patch(
            "app.users.services.patch.get_custom_attribute",
            new=MagicMock(return_value=[json.dumps(existing)]),
        ),
        patch(
            "app.users.services.patch.patch_custom_attribute",
            new=AsyncMock(return_value=MagicMock(status_code=204)),
        ) as mock_patch,
    ):
        await patch_processing_data(
            http_client,
            "ibm1",
            "rp-123",
            [],
        )

    patch_payload = mock_patch.await_args.kwargs["patch_payload"]
    values = _extract_custom_attribute_values(patch_payload)
    parsed_values = [json.loads(value) for value in values]

    assert len(parsed_values) == 1
    assert parsed_values[0]["retry_count"] == 4
    assert parsed_values[0]["first_attempt_timestamp"] == "2020-01-01 00:00:00"
    assert parsed_values[0]["last_attempt_timestamp"] == parsed_values[0]["timestamp"]
    assert "correlation_id" not in parsed_values[0]
    assert "attempt_id" not in parsed_values[0]


@pytest.mark.asyncio
async def test_patch_processing_data_summarizes_existing_attempts():
    http_client = AsyncMock()
    existing = {
        "client_id": "rp-123",
        "retry_count": 1,
        "timestamp": "2020-01-02 00:00:00",
        "correlation_id": "corr-previous",
        "attempts": [
            {
                "correlation_id": "corr-123",
                "attempt_id": "attempt-123",
                "timestamp": "2020-01-01 00:00:00",
            },
            {
                "correlation_id": "corr-456",
                "attempt_id": "attempt-456",
                "timestamp": "2020-01-02 00:00:00",
            },
        ],
    }

    with (
        patch(
            "app.users.services.patch.get_custom_attribute",
            new=MagicMock(return_value=[json.dumps(existing)]),
        ),
        patch(
            "app.users.services.patch.patch_custom_attribute",
            new=AsyncMock(return_value=MagicMock(status_code=204)),
        ) as mock_patch,
    ):
        await patch_processing_data(
            http_client,
            "ibm1",
            "rp-123",
            [],
            correlation_id="corr-789",
            attempt_id="attempt-789",
        )

    patch_payload = mock_patch.await_args.kwargs["patch_payload"]
    values = _extract_custom_attribute_values(patch_payload)
    parsed_values = [json.loads(value) for value in values]

    assert len(parsed_values) == 1
    assert parsed_values[0]["client_id"] == "rp-123"
    assert parsed_values[0]["retry_count"] == 2
    assert parsed_values[0]["first_attempt_timestamp"] == "2020-01-01 00:00:00"
    assert parsed_values[0]["last_attempt_timestamp"] == parsed_values[0]["timestamp"]
    assert parsed_values[0]["correlation_id"] == "corr-789"
    assert parsed_values[0]["attempt_id"] == "attempt-789"
    assert all("attempts" not in value for value in parsed_values)
    assert all(len(value) < 1000 for value in values)


@pytest.mark.asyncio
async def test_patch_processing_data_keeps_one_summary_per_client_id():
    http_client = AsyncMock()
    existing = [
        json.dumps(
            {
                "client_id": "rp-123",
                "retry_count": 0,
                "timestamp": "2020-01-01 00:00:00",
                "correlation_id": "corr-old",
                "attempt_id": "attempt-old",
            }
        ),
        json.dumps(
            {
                "client_id": "rp-456",
                "retry_count": 2,
                "timestamp": "2020-01-03 00:00:00",
                "first_attempt_timestamp": "2020-01-01 00:00:00",
                "last_attempt_timestamp": "2020-01-03 00:00:00",
                "correlation_id": "corr-other",
                "attempt_id": "attempt-other",
            }
        ),
    ]

    with (
        patch(
            "app.users.services.patch.get_custom_attribute",
            new=MagicMock(return_value=existing),
        ),
        patch(
            "app.users.services.patch.patch_custom_attribute",
            new=AsyncMock(return_value=MagicMock(status_code=204)),
        ) as mock_patch,
    ):
        await patch_processing_data(
            http_client,
            "ibm1",
            "rp-123",
            [],
            correlation_id="corr-new",
            attempt_id="attempt-new",
        )

    patch_payload = mock_patch.await_args.kwargs["patch_payload"]
    values = _extract_custom_attribute_values(patch_payload)
    parsed_values = [json.loads(value) for value in values]

    assert len(parsed_values) == 2
    assert parsed_values[0]["client_id"] == "rp-123"
    assert parsed_values[0]["retry_count"] == 1
    assert parsed_values[0]["first_attempt_timestamp"] == "2020-01-01 00:00:00"
    assert parsed_values[0]["last_attempt_timestamp"] == parsed_values[0]["timestamp"]
    assert parsed_values[0]["correlation_id"] == "corr-new"
    assert parsed_values[0]["attempt_id"] == "attempt-new"
    assert parsed_values[1] == {
        "client_id": "rp-456",
        "retry_count": 2,
        "timestamp": "2020-01-03 00:00:00",
        "first_attempt_timestamp": "2020-01-01 00:00:00",
        "last_attempt_timestamp": "2020-01-03 00:00:00",
        "correlation_id": "corr-other",
        "attempt_id": "attempt-other",
    }


@pytest.mark.asyncio
async def test_patch_processing_data_raises_on_malformed_json():
    http_client = AsyncMock()

    with patch(
        "app.users.services.patch.get_custom_attribute",
        new=MagicMock(return_value=["{bad json"]),
    ):
        with pytest.raises(Exception):
            await patch_processing_data(http_client, "ibm1", "rp-123", [])


@pytest.mark.asyncio
async def test_patch_processing_data_raises_on_json_serialization_error():
    http_client = AsyncMock()

    with (
        patch(
            "app.users.services.patch.get_custom_attribute",
            new=MagicMock(return_value=[]),
        ),
        patch("app.users.services.patch.json.dumps", side_effect=TypeError("boom")),
    ):
        with pytest.raises(TypeError):
            await patch_processing_data(http_client, "ibm1", "rp-123", [])


@pytest.mark.asyncio
async def test_patch_legacy_pai_creates_new_entry_on_empty_attributes():
    http_client = AsyncMock()

    with patch(
        "app.users.services.patch.patch_custom_attribute",
        new=AsyncMock(return_value=MagicMock(status_code=204)),
    ) as mock_patch:
        await patch_legacy_pai(
            http_client,
            "ibm1",
            "rp-123",
            [],
            "legacy-pai",
            correlation_id="corr-123",
            attempt_id="attempt-123",
        )

    mock_patch.assert_awaited_once()
    assert mock_patch.await_args.args[0] is http_client
    patch_payload = mock_patch.await_args.kwargs["patch_payload"]
    values = _extract_custom_attribute_values(patch_payload)
    parsed = json.loads(values[0])
    assert parsed["client_id"] == "rp-123"
    assert parsed["pai"] == "legacy-pai"
    assert parsed["correlation_id"] == "corr-123"
    assert parsed["attempt_id"] == "attempt-123"


@pytest.mark.asyncio
async def test_patch_legacy_pai_noops_on_conflicting_existing_client_id():
    http_client = AsyncMock()
    existing = {"client_id": "rp-123", "pai": "old-pai"}

    with (
        patch(
            "app.users.services.patch.get_custom_attribute",
            new=MagicMock(return_value=[json.dumps(existing)]),
        ),
        patch(
            "app.users.services.patch.patch_custom_attribute",
            new=AsyncMock(return_value=MagicMock(status_code=204)),
        ) as mock_patch,
    ):
        response = await patch_legacy_pai(
            http_client, "ibm1", "rp-123", [], "legacy-pai"
        )

    assert response.status_code == 204
    mock_patch.assert_not_awaited()


@pytest.mark.asyncio
async def test_patch_legacy_pai_raises_on_json_serialization_error():
    http_client = AsyncMock()

    with (
        patch(
            "app.users.services.patch.get_custom_attribute",
            new=MagicMock(return_value=[]),
        ),
        patch("app.users.services.patch.json.dumps", side_effect=TypeError("boom")),
    ):
        with pytest.raises(TypeError):
            await patch_legacy_pai(http_client, "ibm1", "rp-123", [], "legacy-pai")


@pytest.mark.asyncio
async def test_patch_audit_data_creates_new_entry_with_timestamp():
    http_client = AsyncMock()

    with patch(
        "app.users.services.patch.patch_custom_attribute",
        new=AsyncMock(return_value=MagicMock(status_code=204)),
    ) as mock_patch:
        await patch_audit_data(
            http_client,
            "ibm1",
            "rp-123",
            [],
            status="LINKED",
            correlation_id="corr-123",
            attempt_id="attempt-123",
        )

    mock_patch.assert_awaited_once()
    assert mock_patch.await_args.args[0] is http_client
    patch_payload = mock_patch.await_args.kwargs["patch_payload"]
    values = _extract_custom_attribute_values(patch_payload)
    parsed = json.loads(values[0])
    assert parsed["client_id"] == "rp-123"
    assert parsed["status"] == "LINKED"
    assert parsed["correlation_id"] == "corr-123"
    assert parsed["attempt_id"] == "attempt-123"
    datetime.strptime(parsed["timestamp"], "%Y-%m-%d %H:%M:%S")


@pytest.mark.asyncio
async def test_patch_audit_data_updates_existing_client_entry():
    http_client = AsyncMock()
    existing = {
        "client_id": "rp-123",
        "legacy_idp": "",
        "timestamp": "2020-01-01 00:00:00",
        "status": "SKIPPED",
        "correlation_id": "corr-old",
        "attempt_id": "attempt-old",
    }
    other_existing = {
        "client_id": "rp-456",
        "legacy_idp": "",
        "timestamp": "2020-01-02 00:00:00",
        "status": "LINKED",
    }

    with (
        patch(
            "app.users.services.patch.get_custom_attribute",
            new=MagicMock(
                return_value=[json.dumps(existing), json.dumps(other_existing)]
            ),
        ),
        patch(
            "app.users.services.patch.patch_custom_attribute",
            new=AsyncMock(return_value=MagicMock(status_code=204)),
        ) as mock_patch,
    ):
        await patch_audit_data(
            http_client,
            "ibm1",
            "rp-123",
            [],
            status="LINKED",
            correlation_id="corr-new",
            attempt_id="attempt-new",
        )

    patch_payload = mock_patch.await_args.kwargs["patch_payload"]
    values = _extract_custom_attribute_values(patch_payload)
    parsed_values = [json.loads(value) for value in values]

    assert len(parsed_values) == 2
    assert parsed_values[0]["client_id"] == "rp-123"
    assert parsed_values[0]["status"] == "LINKED"
    assert parsed_values[0]["correlation_id"] == "corr-new"
    assert parsed_values[0]["attempt_id"] == "attempt-new"
    assert parsed_values[1] == other_existing


@pytest.mark.asyncio
async def test_patch_audit_data_raises_on_json_serialization_error():
    http_client = AsyncMock()

    with (
        patch(
            "app.users.services.patch.get_custom_attribute",
            new=MagicMock(return_value=[]),
        ),
        patch("app.users.services.patch.json.dumps", side_effect=TypeError("boom")),
    ):
        with pytest.raises(TypeError):
            await patch_audit_data(http_client, "ibm1", "rp-123", [], status="LINKED")
