import logging
import json

from datetime import datetime
from fastapi import HTTPException
from httpx import AsyncClient, HTTPStatusError, Response
from pydantic import ValidationError
from typing import List

from app.config import get_configuration

from app.constants.patch_keys import PatchKeys

from app.users.schemas import (
    CustomAttribute,
    AuditDataSchema,
    LegacyPaiDataSchema,
    CustomAttributeOperation,
    NotifyTypeOperation,
    PatchRequest,
    ProcessingDataSchema,
)

from app.users.services.custom_attributes import get_custom_attribute

from app.utils.access_token import (
    get_admin_token,
    get_auth_request_headers,
)

# Get the desired log level from configuration
config = get_configuration()
log_level_str = config.LOG_LEVEL.upper()

# Convert string level to the logging module's level constant (e.g., "DEBUG" to logging.DEBUG)
log_level = getattr(logging, log_level_str, logging.INFO)

# Apply the configuration
logging.basicConfig(level=log_level)
logger = logging.getLogger(__name__)


def patching_payload(
    custom_attribute_name: str,
    custom_attribute_value: str,
):

    try:

        patch_request = PatchRequest(
            schemas=["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
            Operations=[
                CustomAttributeOperation(
                    value=[
                        CustomAttribute(
                            name=custom_attribute_name,
                            values=custom_attribute_value,
                        )
                    ],
                ),
                NotifyTypeOperation(
                    value="NONE",
                ),
            ],
        )

        payload = patch_request.model_dump_json()
        return payload

    except ValidationError:
        logger.error("Validation error while building patch payload")
        raise HTTPException(status_code=422, detail="Request data validation error")


async def patch_custom_attribute(
    global_http_client: AsyncClient,
    ibm_id: str,
    patch_payload: str,
):
    try:

        settings = get_configuration()

        access_token = await get_admin_token(global_http_client)

        users_api_endpoint = f"{settings.users_api_endpoint}/{ibm_id}"
        h = get_auth_request_headers(access_token, False)

        response = await global_http_client.patch(
            users_api_endpoint,
            headers=h,
            data=patch_payload,
            follow_redirects=False,
            cookies={},
        )

        if response.status_code == 401:
            return {"error": "Unauthorized: Invalid credentials or token"}
        if response.status_code >= 400:
            return {"error": f"HTTP error: {response.status_code}"}

        return response

    except HTTPStatusError as e:
        # HTTPX error for status codes like 401
        if e.response.status_code == 401:
            return {"error": "Unauthorized: Invalid credentials or token"}
        return {"error": f"HTTP error: {e.response.status_code}"}


async def patch_processing_data(
    global_http_client: AsyncClient,
    ibm_id: str,
    rp_client_id: str,
    custom_attributes: str,
):
    try:

        # Get raw value from IBM
        processing_data_array = get_custom_attribute(
            PatchKeys.PROCESSING_DATA_KEY.value, custom_attributes
        )

        # Parse into Pydantic model
        if not processing_data_array:
            processing_data_array_parsed = []

        else:
            processing_data_array_parsed = [
                ProcessingDataSchema(**json.loads(item))
                for item in processing_data_array
            ]

        exsists = False
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Check if Exsists for current rp_client_id
        for i in processing_data_array_parsed:
            if i.client_id == rp_client_id:
                i.retry_count += 1
                i.timestamp = timestamp
                exsists = True
                break

        if not exsists:
            # Append Data
            data_to_append = ProcessingDataSchema(
                client_id=rp_client_id,
                retry_count=1,
                timestamp=timestamp,
            )
            processing_data_array_parsed.append(data_to_append)

        # Stringify
        processing_data_array_stringified = [
            json.dumps(item.model_dump()) for item in processing_data_array_parsed
        ]

        # Build Payload for patch
        processing_data_payload = patching_payload(
            PatchKeys.PROCESSING_DATA_KEY.value, processing_data_array_stringified
        )

        # Return Status from IBM
        response = await patch_custom_attribute(
            global_http_client, ibm_id=ibm_id, patch_payload=processing_data_payload
        )

        # Return Status from IBM
        if isinstance(response, dict):
            logger.error("patch_processing_data_error")
            return response

        return response

    except Exception:
        logger.error("Unexpected error during patch_processing_data")
        raise


async def patch_legacy_pai(
    global_http_client: AsyncClient,
    ibm_id: str,
    rp_client_id: str,
    custom_attributes: List[CustomAttribute],
    legacy_pai: str,
    target_rp_client_ids: List[str] | None = None,
):
    try:

        # Get raw value from IBM
        legacy_pai_array = get_custom_attribute(
            PatchKeys.LEGACY_PAI_DATA_KEY.value, custom_attributes
        )

        # Parse into Pydantic model
        if not legacy_pai_array:
            legacy_pai_array_parsed = []

        else:
            legacy_pai_array_parsed = [
                LegacyPaiDataSchema(**json.loads(item)) for item in legacy_pai_array
            ]

        if target_rp_client_ids:
            # Preserve order while removing duplicates from config.
            candidate_client_ids = list(dict.fromkeys(target_rp_client_ids))
        else:
            candidate_client_ids = [rp_client_id]

        existing_by_client_id = {
            item.client_id: item for item in legacy_pai_array_parsed
        }
        did_change = False

        for client_id in candidate_client_ids:
            existing_value = existing_by_client_id.get(client_id)
            if existing_value:
                if existing_value.pai != legacy_pai:
                    # Defensive fallback for unexpected data inconsistencies.
                    logger.warning(
                        "Skipping legacy PAI update due to conflicting existing value"
                    )
                continue

            data_to_append = LegacyPaiDataSchema(client_id=client_id, pai=legacy_pai)
            legacy_pai_array_parsed.append(data_to_append)
            existing_by_client_id[client_id] = data_to_append
            did_change = True

        # No-op success when all target client_ids already had values or were skipped due to conflicts.
        if not did_change:
            logger.info("patch_legacy_pai no-op: no new values to append")
            return Response(status_code=204)

        # Stringify
        legacy_pai_array_stringified = [
            json.dumps(item.model_dump()) for item in legacy_pai_array_parsed
        ]

        # Build Payload for patch
        legacy_pai_payload = patching_payload(
            PatchKeys.LEGACY_PAI_DATA_KEY.value, legacy_pai_array_stringified
        )

        response = await patch_custom_attribute(
            global_http_client, ibm_id=ibm_id, patch_payload=legacy_pai_payload
        )

        # Return Status from IBM
        if isinstance(response, dict):
            logger.error("patch_legacy_pai_error")
            return response

        return response

    except Exception:
        logger.error("Unexpected error during patch_legacy_pai")
        raise


async def patch_audit_data(
    global_http_client: AsyncClient,
    ibm_id: str,
    rp_client_id: str,
    custom_attributes: str,
    status: str,
):
    try:

        # Get raw value from IBM
        audit_data_array = get_custom_attribute(
            PatchKeys.AUDIT_DATA_KEY.value, custom_attributes
        )

        # Parse into Pydantic model
        if not audit_data_array:
            audit_data_array_parsed = []

        else:
            audit_data_array_parsed = [
                AuditDataSchema(**json.loads(item)) for item in audit_data_array
            ]

        legacy_idp = ""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        data_to_append = AuditDataSchema(
            client_id=rp_client_id,
            legacy_idp=legacy_idp,
            timestamp=timestamp,
            status=status,
        )

        # Append Data
        audit_data_array_parsed.append(data_to_append)

        # Stringify
        audit_data_array_stringified = [
            json.dumps(item.model_dump()) for item in audit_data_array_parsed
        ]

        # Build Payload for patch
        audit_data_payload = patching_payload(
            PatchKeys.AUDIT_DATA_KEY.value, audit_data_array_stringified
        )

        # Return Status from IBM

        response = await patch_custom_attribute(
            global_http_client, ibm_id=ibm_id, patch_payload=audit_data_payload
        )

        if isinstance(response, dict):
            logger.error("patch_audit_data_error")
            return response

        # Return Status from IBM
        return response

    except Exception:
        logger.error("Unexpected error during patch_audit_data")
        raise
