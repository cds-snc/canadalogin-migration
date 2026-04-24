import json
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.constants.patch_keys import PatchKeys
from app.users.schemas import CustomAttribute
from app.users.services.patch import patch_legacy_pai


def _legacy_pai_custom_attribute(values: list[dict]) -> CustomAttribute:
    return CustomAttribute(
        name=PatchKeys.LEGACY_PAI_DATA_KEY.value,
        values=[json.dumps(item) for item in values],
    )


def _extract_payload_entries(patch_payload: str) -> list[dict]:
    payload = json.loads(patch_payload)
    custom_attributes = payload["Operations"][0]["value"]
    legacy_pai_attr = next(
        item
        for item in custom_attributes
        if item["name"] == PatchKeys.LEGACY_PAI_DATA_KEY.value
    )
    return [json.loads(item) for item in legacy_pai_attr["values"]]


@pytest.mark.asyncio
async def test_patch_legacy_pai_appends_primary_and_dependents_in_one_patch():
    with patch(
        "app.users.services.patch.patch_custom_attribute",
        new=AsyncMock(return_value=SimpleNamespace(status_code=204)),
    ) as mock_patch_custom_attribute:
        await patch_legacy_pai(
            global_http_client=AsyncMock(),
            ibm_id="ibm-1",
            rp_client_id="rp-a",
            custom_attributes=[],
            legacy_pai="legacy-sub",
            target_rp_client_ids=["rp-a", "rp-b"],
        )

    mock_patch_custom_attribute.assert_awaited_once()
    patch_payload = mock_patch_custom_attribute.await_args.kwargs["patch_payload"]
    entries = _extract_payload_entries(patch_payload)
    assert entries == [
        {"client_id": "rp-a", "pai": "legacy-sub"},
        {"client_id": "rp-b", "pai": "legacy-sub"},
    ]


@pytest.mark.asyncio
async def test_patch_legacy_pai_skips_conflict_and_appends_missing_client_ids():
    existing = _legacy_pai_custom_attribute(
        [
            {"client_id": "rp-a", "pai": "different-sub"},
            {"client_id": "rp-b", "pai": "legacy-sub"},
        ]
    )

    with patch(
        "app.users.services.patch.patch_custom_attribute",
        new=AsyncMock(return_value=SimpleNamespace(status_code=204)),
    ) as mock_patch_custom_attribute:
        await patch_legacy_pai(
            global_http_client=AsyncMock(),
            ibm_id="ibm-1",
            rp_client_id="rp-a",
            custom_attributes=[existing],
            legacy_pai="legacy-sub",
            target_rp_client_ids=["rp-a", "rp-b", "rp-c"],
        )

    mock_patch_custom_attribute.assert_awaited_once()
    patch_payload = mock_patch_custom_attribute.await_args.kwargs["patch_payload"]
    entries = _extract_payload_entries(patch_payload)
    assert entries == [
        {"client_id": "rp-a", "pai": "different-sub"},
        {"client_id": "rp-b", "pai": "legacy-sub"},
        {"client_id": "rp-c", "pai": "legacy-sub"},
    ]


@pytest.mark.asyncio
async def test_patch_legacy_pai_noop_when_no_new_values_to_write():
    existing = _legacy_pai_custom_attribute(
        [
            {"client_id": "rp-a", "pai": "legacy-sub"},
            {"client_id": "rp-b", "pai": "different-sub"},
        ]
    )

    with patch(
        "app.users.services.patch.patch_custom_attribute",
        new=AsyncMock(return_value=SimpleNamespace(status_code=204)),
    ) as mock_patch_custom_attribute:
        response = await patch_legacy_pai(
            global_http_client=AsyncMock(),
            ibm_id="ibm-1",
            rp_client_id="rp-a",
            custom_attributes=[existing],
            legacy_pai="legacy-sub",
            target_rp_client_ids=["rp-a", "rp-b"],
        )

    assert response.status_code == 204
    mock_patch_custom_attribute.assert_not_awaited()


@pytest.mark.asyncio
async def test_patch_legacy_pai_dedupes_existing_client_id_entries():
    existing = _legacy_pai_custom_attribute(
        [
            {
                "client_id": "rp-a",
                "pai": "legacy-sub",
                "correlation_id": "corr-old",
            },
            {
                "client_id": "rp-a",
                "pai": "legacy-sub",
                "correlation_id": "corr-new",
            },
        ]
    )

    with patch(
        "app.users.services.patch.patch_custom_attribute",
        new=AsyncMock(return_value=SimpleNamespace(status_code=204)),
    ) as mock_patch_custom_attribute:
        await patch_legacy_pai(
            global_http_client=AsyncMock(),
            ibm_id="ibm-1",
            rp_client_id="rp-a",
            custom_attributes=[existing],
            legacy_pai="legacy-sub",
            target_rp_client_ids=["rp-a"],
        )

    mock_patch_custom_attribute.assert_awaited_once()
    patch_payload = mock_patch_custom_attribute.await_args.kwargs["patch_payload"]
    entries = _extract_payload_entries(patch_payload)
    assert entries == [
        {
            "client_id": "rp-a",
            "pai": "legacy-sub",
            "correlation_id": "corr-new",
        }
    ]


@pytest.mark.asyncio
async def test_patch_legacy_pai_preserves_conflicting_duplicate_client_id_entries(
    caplog,
):
    existing = _legacy_pai_custom_attribute(
        [
            {"client_id": "rp-a", "pai": "legacy-sub"},
            {"client_id": "rp-a", "pai": "different-sub"},
        ]
    )

    caplog.set_level(logging.WARNING)
    with patch(
        "app.users.services.patch.patch_custom_attribute",
        new=AsyncMock(return_value=SimpleNamespace(status_code=204)),
    ) as mock_patch_custom_attribute:
        response = await patch_legacy_pai(
            global_http_client=AsyncMock(),
            ibm_id="ibm-1",
            rp_client_id="rp-a",
            custom_attributes=[existing],
            legacy_pai="legacy-sub",
            target_rp_client_ids=["rp-a"],
            correlation_id="corr-1",
        )

    assert response.status_code == 204
    mock_patch_custom_attribute.assert_not_awaited()
    warning_message = caplog.records[-1].getMessage()
    assert (
        "Skipping legacy PAI update due to conflicting existing value"
        == warning_message
    )
    assert "rp-a" not in warning_message
    assert "corr-1" not in warning_message
    assert "ibm-1" not in warning_message
