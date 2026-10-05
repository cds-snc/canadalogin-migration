import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import HTTPException

from app.auth_legacy.services import login, skip, status
from app.constants.patch_keys import PatchKeys
from app.users.schemas import CustomAttribute
from app.utils.recovery_errors import RecoveryError


def audit_record(client_id="rp-123", audit_status="LINKED"):
    return {
        "client_id": client_id,
        "legacy_idp": "",
        "timestamp": "2026-10-05 10:00:00",
        "status": audit_status,
    }


def attribute(key, records):
    return CustomAttribute(
        name=key.value, values=[json.dumps(item) for item in records]
    )


@pytest.mark.parametrize(
    "attributes, completed",
    [
        (None, False),
        ([], False),
        ([attribute(PatchKeys.AUDIT_DATA_KEY, [audit_record()])], True),
        (
            [
                attribute(
                    PatchKeys.AUDIT_DATA_KEY, [audit_record(audit_status="SKIPPED")]
                )
            ],
            True,
        ),
        (
            [
                attribute(
                    PatchKeys.LEGACY_PAI_DATA_KEY,
                    [{"client_id": "rp-123", "pai": "legacy-user"}],
                )
            ],
            True,
        ),
        (
            [
                attribute(PatchKeys.AUDIT_DATA_KEY, [audit_record("another-rp")]),
                attribute(
                    PatchKeys.LEGACY_PAI_DATA_KEY,
                    [{"client_id": "another-rp", "pai": "legacy-user"}],
                ),
            ],
            False,
        ),
        (
            [
                attribute(
                    PatchKeys.PROCESSING_DATA_KEY,
                    [{"client_id": "rp-123", "retry_count": 2, "timestamp": "now"}],
                )
            ],
            False,
        ),
        (
            [
                attribute(
                    PatchKeys.LEGACY_PAI_DATA_KEY,
                    [{"client_id": "rp-123", "pai": " "}],
                )
            ],
            False,
        ),
    ],
    ids=[
        "no-extension",
        "no-attributes",
        "linked-audit",
        "skipped-audit",
        "pai-without-audit",
        "other-rp-only",
        "processing-only",
        "empty-pai",
    ],
)
def test_completion_is_scoped_to_current_rp(attributes, completed):
    before = [item.model_dump() for item in attributes] if attributes else attributes

    assert status.is_migration_completed(attributes, "rp-123") is completed

    after = [item.model_dump() for item in attributes] if attributes else attributes
    assert after == before


@pytest.mark.parametrize(
    "key,value",
    [
        (PatchKeys.AUDIT_DATA_KEY, "{invalid"),
        (PatchKeys.AUDIT_DATA_KEY, '{"client_id":"rp-123"}'),
        (PatchKeys.LEGACY_PAI_DATA_KEY, "[]"),
        (PatchKeys.LEGACY_PAI_DATA_KEY, '{"client_id":"rp-123","pai":null}'),
    ],
)
def test_malformed_migration_records_do_not_allow_another_action(key, value):
    attributes = [CustomAttribute(name=key.value, values=[value])]

    with pytest.raises(RecoveryError) as raised:
        status.is_migration_completed(attributes, "rp-123")

    assert raised.value.code == "service-unavailable"


@pytest.mark.parametrize("audit_status", ["PENDING", "COMPLETE", ""])
def test_unknown_current_rp_audit_status_does_not_allow_another_action(audit_status):
    attributes = [
        attribute(PatchKeys.AUDIT_DATA_KEY, [audit_record(audit_status=audit_status)])
    ]

    with pytest.raises(RecoveryError) as raised:
        status.is_migration_completed(attributes, "rp-123")

    assert raised.value.code == "service-unavailable"


def test_unknown_audit_status_for_another_rp_does_not_block_current_rp():
    attributes = [
        attribute(PatchKeys.AUDIT_DATA_KEY, [audit_record("another-rp", "UNKNOWN")])
    ]

    assert status.is_migration_completed(attributes, "rp-123") is False


@pytest.mark.asyncio
async def test_profile_token_expiring_after_introspection_requires_session_recovery():
    with patch.object(
        status,
        "get_user_custom_attributes",
        new=AsyncMock(side_effect=HTTPException(401, "Not authenticated")),
    ):
        with pytest.raises(RecoveryError) as raised:
            await status.get_migration_attributes(AsyncMock(), "expired-user-at")

    assert raised.value.code == "session-ended"
    assert raised.value.status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        HTTPException(503, "Upstream failed"),
        httpx.ReadTimeout("Timed out"),
        ValueError(),
    ],
)
async def test_profile_read_failure_does_not_allow_another_action(error):
    with patch.object(
        status, "get_user_custom_attributes", new=AsyncMock(side_effect=error)
    ):
        with pytest.raises(RecoveryError) as raised:
            await status.get_migration_attributes(AsyncMock(), "user-at")

    assert raised.value.code == "service-unavailable"


@pytest.mark.asyncio
async def test_status_validates_rp_before_reading_profile():
    request = MagicMock()
    with (
        patch.object(
            status,
            "get_config",
            new=AsyncMock(side_effect=RecoveryError("missing-rp-context")),
        ),
        patch.object(status, "get_migration_attributes", new=AsyncMock()) as read,
    ):
        with pytest.raises(RecoveryError) as raised:
            await status.get_migration_status(request, "user-at", None)

    assert raised.value.code == "missing-rp-context"
    read.assert_not_awaited()


@pytest.mark.asyncio
async def test_status_reads_attributes_once_and_does_not_change_session():
    request = MagicMock()
    request.session = {"rp_client_id": "rp-123", "legacy_linking_attempt_id": "attempt"}
    attributes = [attribute(PatchKeys.AUDIT_DATA_KEY, [audit_record()])]
    with (
        patch.object(status, "get_config", new=AsyncMock()) as config,
        patch.object(
            status, "get_migration_attributes", new=AsyncMock(return_value=attributes)
        ) as read,
    ):
        result = await status.get_migration_status(request, "user-at", "rp-123")

    assert result.model_dump() == {"rp_client_id": "rp-123", "completed": True}
    config.assert_awaited_once_with("rp-123")
    read.assert_awaited_once_with(request.app.state.request_client, "user-at")
    assert request.session == {
        "rp_client_id": "rp-123",
        "legacy_linking_attempt_id": "attempt",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["login", "skip"])
@pytest.mark.parametrize("evidence", ["LINKED", "SKIPPED", "PAI", "malformed"])
async def test_completed_or_unreadable_migration_prevents_all_new_writes(
    action, evidence
):
    request = MagicMock()
    request.session = {
        "rp_client_id": "rp-123",
        "legacy_linking_attempt_id": "previous",
    }
    before = dict(request.session)
    if evidence == "PAI":
        attributes = [
            attribute(
                PatchKeys.LEGACY_PAI_DATA_KEY,
                [{"client_id": "rp-123", "pai": "legacy-user"}],
            )
        ]
    elif evidence == "malformed":
        attributes = [
            CustomAttribute(name=PatchKeys.AUDIT_DATA_KEY.value, values=["{"])
        ]
    else:
        attributes = [
            attribute(PatchKeys.AUDIT_DATA_KEY, [audit_record(audit_status=evidence)])
        ]
    service = login if action == "login" else skip
    rp = SimpleNamespace(
        rp_client_name="rpname",
        IDP=[
            SimpleNamespace(
                client_name="SIC",
                redirect_uris=["https://legacy.example.test/callback"],
            )
        ],
    )

    with (
        patch.object(service, "get_config", new=AsyncMock(return_value=rp)),
        patch.object(
            service, "get_migration_attributes", new=AsyncMock(return_value=attributes)
        ) as read,
        patch.object(login, "register_client", new=AsyncMock()) as register,
        patch.object(login, "patch_processing_data", new=AsyncMock()) as processing,
        patch.object(skip, "patch_audit_data", new=AsyncMock()) as audit,
    ):
        with pytest.raises(RecoveryError) as raised:
            if action == "login":
                await login.SIC_legacy_login_auth(
                    request, "user-at", "token", "rp-123", "fr"
                )
            else:
                await skip.skip_account_linking(request, "user-at", "token", "rp-123")

    assert raised.value.code == (
        "service-unavailable" if evidence == "malformed" else "migration-completed"
    )
    assert request.session == before
    read.assert_awaited_once()
    register.assert_not_awaited()
    processing.assert_not_awaited()
    audit.assert_not_awaited()
