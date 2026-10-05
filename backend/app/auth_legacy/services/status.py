from fastapi import HTTPException, Request
from httpx import AsyncClient

from app.auth_legacy.schemas import MigrationStatusResponse
from app.constants.audit_status_keys import AuditStatusKeys
from app.constants.patch_keys import PatchKeys
from app.rp.services.config import get_config
from app.users.schemas import AuditDataSchema, CustomAttribute, LegacyPaiDataSchema
from app.users.services.custom_attributes import (
    get_custom_attribute,
    get_user_custom_attributes,
)
from app.utils.recovery_errors import RecoveryError


def is_migration_completed(
    custom_attributes: list[CustomAttribute] | None, rp_client_id: str
) -> bool:
    """Classify existing IBM records for one RP without changing them."""
    try:
        audits = [
            AuditDataSchema.model_validate_json(value)
            for value in (
                get_custom_attribute(PatchKeys.AUDIT_DATA_KEY.value, custom_attributes)
                or []
            )
        ]
        identities = [
            LegacyPaiDataSchema.model_validate_json(value)
            for value in (
                get_custom_attribute(
                    PatchKeys.LEGACY_PAI_DATA_KEY.value, custom_attributes
                )
                or []
            )
        ]
    except (ValueError, TypeError, AttributeError):
        # Unreadable migration data cannot establish that another action is safe.
        raise RecoveryError("service-unavailable") from None

    completed_statuses = {
        AuditStatusKeys.LINKED_KEY.value,
        AuditStatusKeys.SKIPPED_KEY.value,
    }
    current_rp_audits = [
        record for record in audits if record.client_id == rp_client_id
    ]
    if any(record.status not in completed_statuses for record in current_rp_audits):
        # An unfamiliar audit value is not evidence that migration is incomplete.
        raise RecoveryError("service-unavailable")

    return bool(current_rp_audits) or any(
        record.client_id == rp_client_id and bool(record.pai.strip())
        for record in identities
    )


async def get_migration_attributes(
    global_http_client: AsyncClient, user_access_token: str
) -> list[CustomAttribute] | None:
    try:
        return await get_user_custom_attributes(global_http_client, user_access_token)
    except Exception as exc:
        if isinstance(exc, HTTPException) and exc.status_code == 401:
            raise RecoveryError("session-ended") from exc
        raise RecoveryError("service-unavailable") from exc


async def get_migration_status(
    request: Request, user_access_token: str, rp_client_id: str | None
) -> MigrationStatusResponse:
    await get_config(rp_client_id)
    custom_attributes = await get_migration_attributes(
        request.app.state.request_client, user_access_token
    )
    return MigrationStatusResponse(
        rp_client_id=rp_client_id,
        completed=is_migration_completed(custom_attributes, rp_client_id),
    )
