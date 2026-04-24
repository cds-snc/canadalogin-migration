import logging
import json

from datetime import datetime
from fastapi import HTTPException
from httpx import AsyncClient, HTTPStatusError, Response
from pydantic import ValidationError
from typing import List, Protocol, TypeVar

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
from app.utils.request_error_handler import RequestErrorHandler

logger = logging.getLogger(__name__)


class _ClientRecord(Protocol):
    client_id: str


TClientRecord = TypeVar("TClientRecord", bound=_ClientRecord)


def _is_legacy_retry_count_record(processing_data: ProcessingDataSchema) -> bool:
    return (
        processing_data.retry_count > 0
        and not processing_data.attempts
        and not processing_data.correlation_id
        and not processing_data.attempt_id
        and not processing_data.first_attempt_timestamp
        and not processing_data.last_attempt_timestamp
    )


def _get_effective_retry_count(processing_data: ProcessingDataSchema) -> int:
    # Legacy records stored the initial attempt as retry_count=1.
    if _is_legacy_retry_count_record(processing_data):
        return processing_data.retry_count - 1

    return processing_data.retry_count


def _flatten_processing_data_records(
    processing_data_records: List[ProcessingDataSchema],
) -> List[ProcessingDataSchema]:
    flattened_records = []

    for processing_data in processing_data_records:
        if not processing_data.attempts:
            retry_count = _get_effective_retry_count(processing_data)
            flattened_records.append(
                processing_data.model_copy(
                    update={
                        "retry_count": retry_count,
                        "attempts": [],
                    }
                )
            )
            continue

        first_retry_count = max(
            0,
            processing_data.retry_count - len(processing_data.attempts) + 1,
        )
        for attempt_index, attempt in enumerate(processing_data.attempts):
            flattened_records.append(
                ProcessingDataSchema(
                    client_id=processing_data.client_id,
                    retry_count=first_retry_count + attempt_index,
                    timestamp=attempt.timestamp,
                    correlation_id=attempt.correlation_id,
                    attempt_id=attempt.attempt_id,
                )
            )

    return flattened_records


def _get_first_attempt_timestamp(processing_data: ProcessingDataSchema) -> str:
    return processing_data.first_attempt_timestamp or processing_data.timestamp


def _get_last_attempt_timestamp(processing_data: ProcessingDataSchema) -> str:
    return processing_data.last_attempt_timestamp or processing_data.timestamp


def _summarize_processing_data_records(
    processing_data_records: List[ProcessingDataSchema],
) -> List[ProcessingDataSchema]:
    summary_by_client_id = {}

    for processing_data in _flatten_processing_data_records(processing_data_records):
        existing_value = summary_by_client_id.get(processing_data.client_id)
        first_attempt_timestamp = _get_first_attempt_timestamp(processing_data)
        last_attempt_timestamp = _get_last_attempt_timestamp(processing_data)

        if existing_value is None:
            summary_by_client_id[processing_data.client_id] = (
                processing_data.model_copy(
                    update={
                        "first_attempt_timestamp": first_attempt_timestamp,
                        "last_attempt_timestamp": last_attempt_timestamp,
                    }
                )
            )
            continue

        first_attempt_timestamp = min(
            _get_first_attempt_timestamp(existing_value),
            first_attempt_timestamp,
        )
        last_attempt_timestamp = max(
            _get_last_attempt_timestamp(existing_value),
            last_attempt_timestamp,
        )
        if processing_data.retry_count >= existing_value.retry_count:
            latest_value = processing_data
        else:
            latest_value = existing_value

        summary_by_client_id[processing_data.client_id] = latest_value.model_copy(
            update={
                "first_attempt_timestamp": first_attempt_timestamp,
                "last_attempt_timestamp": last_attempt_timestamp,
            }
        )

    return list(summary_by_client_id.values())


def _dump_processing_data_record(processing_data: ProcessingDataSchema) -> str:
    return json.dumps(processing_data.model_dump(exclude_none=True))


def _get_next_processing_retry_count(
    processing_data_records: List[ProcessingDataSchema],
    rp_client_id: str,
) -> int:
    retry_counts = [
        processing_data.retry_count
        for processing_data in processing_data_records
        if processing_data.client_id == rp_client_id
    ]

    if not retry_counts:
        return 0

    return max(retry_counts) + 1


def _build_processing_summary_record(
    rp_client_id: str,
    retry_count: int,
    timestamp: str,
    first_attempt_timestamp: str,
    correlation_id: str | None,
    attempt_id: str | None,
) -> ProcessingDataSchema:
    return ProcessingDataSchema(
        client_id=rp_client_id,
        retry_count=retry_count,
        timestamp=timestamp,
        first_attempt_timestamp=first_attempt_timestamp,
        last_attempt_timestamp=timestamp,
        correlation_id=correlation_id,
        attempt_id=attempt_id,
    )


def _upsert_client_record(
    records: List[TClientRecord],
    record_to_upsert: TClientRecord,
) -> List[TClientRecord]:
    for index, record in enumerate(records):
        if record.client_id == record_to_upsert.client_id:
            records[index] = record_to_upsert
            return records

    records.append(record_to_upsert)
    return records


def _dedupe_client_records(
    records: List[TClientRecord],
) -> List[TClientRecord]:
    records_by_client_id: dict[str, TClientRecord] = {}

    for record in records:
        records_by_client_id[record.client_id] = record

    return list(records_by_client_id.values())


def _dedupe_matching_legacy_pai_records(
    records: List[LegacyPaiDataSchema],
) -> tuple[List[LegacyPaiDataSchema], bool]:
    records_by_client_id: dict[str, List[LegacyPaiDataSchema]] = {}

    for record in records:
        records_by_client_id.setdefault(record.client_id, []).append(record)

    deduped_records = []
    for client_records in records_by_client_id.values():
        pai_values = {record.pai for record in client_records}
        if len(pai_values) == 1:
            deduped_records.append(client_records[-1])
        else:
            deduped_records.extend(client_records)

    return deduped_records, len(deduped_records) != len(records)


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
    operation_name: str = "patch_custom_attribute",
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
            safe_detail = RequestErrorHandler.extract_safe_error_detail(response)
            if safe_detail:
                logger.error(
                    "%s failed while patching IBM user custom attributes. status=%s detail=%s",
                    operation_name,
                    response.status_code,
                    safe_detail,
                )
            else:
                logger.error(
                    "%s failed while patching IBM user custom attributes. status=%s",
                    operation_name,
                    response.status_code,
                )
            return {"error": "Unauthorized: Invalid credentials or token"}
        if response.status_code >= 400:
            safe_detail = RequestErrorHandler.extract_safe_error_detail(response)
            if safe_detail:
                logger.error(
                    "%s failed while patching IBM user custom attributes. status=%s detail=%s",
                    operation_name,
                    response.status_code,
                    safe_detail,
                )
            else:
                logger.error(
                    "%s failed while patching IBM user custom attributes. status=%s",
                    operation_name,
                    response.status_code,
                )
            return {"error": f"HTTP error: {response.status_code}"}

        return response

    except HTTPStatusError as e:
        # HTTPX error for status codes like 401
        status_code = e.response.status_code if e.response else 502
        safe_detail = RequestErrorHandler.extract_safe_error_detail(e.response)
        if safe_detail:
            logger.error(
                "%s raised HTTPStatusError while patching IBM user custom attributes. status=%s detail=%s",
                operation_name,
                status_code,
                safe_detail,
                exc_info=True,
            )
        else:
            logger.error(
                "%s raised HTTPStatusError while patching IBM user custom attributes. status=%s",
                operation_name,
                status_code,
                exc_info=True,
            )
        if status_code == 401:
            return {"error": "Unauthorized: Invalid credentials or token"}
        return {"error": f"HTTP error: {status_code}"}


async def patch_processing_data(
    global_http_client: AsyncClient,
    ibm_id: str,
    rp_client_id: str,
    custom_attributes: List[CustomAttribute],
    correlation_id: str | None = None,
    attempt_id: str | None = None,
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
            processing_data_array_parsed = _summarize_processing_data_records(
                processing_data_array_parsed
            )

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        retry_count = _get_next_processing_retry_count(
            processing_data_array_parsed, rp_client_id
        )
        existing_processing_data = next(
            (
                item
                for item in processing_data_array_parsed
                if item.client_id == rp_client_id
            ),
            None,
        )
        first_attempt_timestamp = (
            _get_first_attempt_timestamp(existing_processing_data)
            if existing_processing_data
            else timestamp
        )
        existing_correlation_id = (
            existing_processing_data.correlation_id
            if existing_processing_data
            else None
        )
        effective_correlation_id = (
            correlation_id if correlation_id is not None else existing_correlation_id
        )
        existing_attempt_id = (
            existing_processing_data.attempt_id if existing_processing_data else None
        )
        effective_attempt_id = (
            attempt_id if attempt_id is not None else existing_attempt_id
        )

        processing_data_array_parsed = _upsert_client_record(
            processing_data_array_parsed,
            _build_processing_summary_record(
                rp_client_id=rp_client_id,
                retry_count=retry_count,
                timestamp=timestamp,
                first_attempt_timestamp=first_attempt_timestamp,
                correlation_id=effective_correlation_id,
                attempt_id=effective_attempt_id,
            ),
        )

        # Stringify
        processing_data_array_stringified = [
            _dump_processing_data_record(item) for item in processing_data_array_parsed
        ]

        # Build Payload for patch
        processing_data_payload = patching_payload(
            PatchKeys.PROCESSING_DATA_KEY.value, processing_data_array_stringified
        )

        # Return Status from IBM
        response = await patch_custom_attribute(
            global_http_client,
            ibm_id=ibm_id,
            patch_payload=processing_data_payload,
            operation_name="patch_processing_data",
        )

        # Return Status from IBM
        if isinstance(response, dict):
            logger.error(
                "patch_processing_data returned handled IBM patch failure: %s",
                response.get("error", "Unknown error"),
            )
            return response

        return response

    except Exception:
        logger.exception("Unexpected error during patch_processing_data")
        raise


async def patch_legacy_pai(
    global_http_client: AsyncClient,
    ibm_id: str,
    rp_client_id: str,
    custom_attributes: List[CustomAttribute],
    legacy_pai: str,
    target_rp_client_ids: List[str] | None = None,
    correlation_id: str | None = None,
    attempt_id: str | None = None,
):
    try:

        # Get raw value from IBM
        legacy_pai_array = get_custom_attribute(
            PatchKeys.LEGACY_PAI_DATA_KEY.value, custom_attributes
        )

        # Parse into Pydantic model
        did_change = False
        if not legacy_pai_array:
            legacy_pai_array_parsed = []

        else:
            legacy_pai_array_parsed = [
                LegacyPaiDataSchema(**json.loads(item)) for item in legacy_pai_array
            ]
            (
                legacy_pai_array_parsed,
                did_change,
            ) = _dedupe_matching_legacy_pai_records(legacy_pai_array_parsed)

        if target_rp_client_ids:
            # Preserve order while removing duplicates from config.
            candidate_client_ids = list(dict.fromkeys(target_rp_client_ids))
        else:
            candidate_client_ids = [rp_client_id]

        existing_by_client_id = {}
        for item in legacy_pai_array_parsed:
            existing_by_client_id.setdefault(item.client_id, []).append(item)

        for client_id in candidate_client_ids:
            existing_values = existing_by_client_id.get(client_id)
            if existing_values:
                if any(
                    existing_value.pai != legacy_pai
                    for existing_value in existing_values
                ):
                    # Defensive fallback for unexpected data inconsistencies.
                    logger.warning(
                        "Skipping legacy PAI update due to conflicting existing value"
                    )
                continue

            data_to_append = LegacyPaiDataSchema(
                client_id=client_id,
                pai=legacy_pai,
                correlation_id=correlation_id,
                attempt_id=attempt_id,
            )
            legacy_pai_array_parsed.append(data_to_append)
            existing_by_client_id[client_id] = [data_to_append]
            did_change = True

        # No-op success when all target client_ids already had values or were skipped due to conflicts.
        if not did_change:
            logger.info("patch_legacy_pai no-op: no new values to append")
            return Response(status_code=204)

        # Stringify
        legacy_pai_array_stringified = [
            json.dumps(item.model_dump(exclude_none=True))
            for item in legacy_pai_array_parsed
        ]

        # Build Payload for patch
        legacy_pai_payload = patching_payload(
            PatchKeys.LEGACY_PAI_DATA_KEY.value, legacy_pai_array_stringified
        )

        response = await patch_custom_attribute(
            global_http_client,
            ibm_id=ibm_id,
            patch_payload=legacy_pai_payload,
            operation_name="patch_legacy_pai",
        )

        # Return Status from IBM
        if isinstance(response, dict):
            logger.error(
                "patch_legacy_pai returned handled IBM patch failure: %s",
                response.get("error", "Unknown error"),
            )
            return response

        return response

    except Exception:
        logger.exception("Unexpected error during patch_legacy_pai")
        raise


async def patch_audit_data(
    global_http_client: AsyncClient,
    ibm_id: str,
    rp_client_id: str,
    custom_attributes: List[CustomAttribute],
    status: str,
    correlation_id: str | None = None,
    attempt_id: str | None = None,
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
            audit_data_array_parsed = _dedupe_client_records(audit_data_array_parsed)

        legacy_idp = ""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        existing_audit_data = next(
            (
                item
                for item in audit_data_array_parsed
                if item.client_id == rp_client_id
            ),
            None,
        )
        existing_correlation_id = (
            existing_audit_data.correlation_id if existing_audit_data else None
        )
        effective_correlation_id = (
            correlation_id if correlation_id is not None else existing_correlation_id
        )
        existing_attempt_id = (
            existing_audit_data.attempt_id if existing_audit_data else None
        )
        effective_attempt_id = (
            attempt_id if attempt_id is not None else existing_attempt_id
        )

        data_to_append = AuditDataSchema(
            client_id=rp_client_id,
            legacy_idp=legacy_idp,
            timestamp=timestamp,
            status=status,
            correlation_id=effective_correlation_id,
            attempt_id=effective_attempt_id,
        )

        audit_data_array_parsed = _upsert_client_record(
            audit_data_array_parsed, data_to_append
        )

        # Stringify
        audit_data_array_stringified = [
            json.dumps(item.model_dump(exclude_none=True))
            for item in audit_data_array_parsed
        ]

        # Build Payload for patch
        audit_data_payload = patching_payload(
            PatchKeys.AUDIT_DATA_KEY.value, audit_data_array_stringified
        )

        # Return Status from IBM

        response = await patch_custom_attribute(
            global_http_client,
            ibm_id=ibm_id,
            patch_payload=audit_data_payload,
            operation_name="patch_audit_data",
        )

        if isinstance(response, dict):
            logger.error(
                "patch_audit_data returned handled IBM patch failure: %s",
                response.get("error", "Unknown error"),
            )
            return response

        # Return Status from IBM
        return response

    except Exception:
        logger.exception("Unexpected error during patch_audit_data")
        raise
