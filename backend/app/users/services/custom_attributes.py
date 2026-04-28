import logging

from fastapi import HTTPException
from httpx import AsyncClient
from pydantic import ValidationError
from typing import List

from app.config import get_configuration

from app.users.schemas import (
    CustomAttribute,
    MeResponse,
)

from app.utils.access_token import get_auth_request_headers
from app.utils.request_error_handler import RequestErrorHandler

logger = logging.getLogger(__name__)


def get_attribute_value(
    key: str,
    attributes: List[CustomAttribute],
) -> List[str] | None:
    for attr in attributes:
        if attr.name == key:
            return attr.values
    return None


def get_custom_attribute(
    custom_attribute_name: str,
    custom_attributes: List[CustomAttribute] | None,
):
    try:

        # None / Empty list
        if not custom_attributes:
            return ""

        custom_attribute_value = get_attribute_value(
            custom_attribute_name, custom_attributes
        )
        return custom_attribute_value

    except ValidationError:
        logger.error("Validation error while reading custom attribute")
        raise HTTPException(status_code=422, detail="Request data validation error")


# Parse ALL Custom Attributes from IBM User Profile
async def get_user_custom_attributes(
    global_http_client: AsyncClient,
    user_access_token: str,
) -> List[CustomAttribute] | None:
    try:

        settings = get_configuration()

        profile_api_endpoint = settings.profile_api_endpoint
        headers = get_auth_request_headers(user_access_token)
        response = await global_http_client.get(profile_api_endpoint, headers=headers)

    except ValidationError:
        logger.error("Validation error while loading user custom attributes")
        raise HTTPException(status_code=422, detail="Request data validation error")

    if response.status_code == 200:
        json_data = response.json()
        response_data = MeResponse(**json_data)
        if not response_data.ibm_extension:
            return None

        custom_attributes = response_data.ibm_extension.custom_attributes
        return custom_attributes

    else:
        safe_detail = RequestErrorHandler.extract_safe_error_detail(response)
        if safe_detail:
            logger.error(
                "Failed to retrieve profile from IBM Verify. status=%s detail=%s",
                response.status_code,
                safe_detail,
            )
        else:
            logger.error(
                "Failed to retrieve profile from IBM Verify. status=%s",
                response.status_code,
            )

        if response.status_code == 401:
            raise HTTPException(status_code=401, detail="Not authenticated")

        else:
            error_details = safe_detail or "Unknown error"
            raise HTTPException(
                status_code=response.status_code, detail=f"HTTP error, {error_details}"
            )
