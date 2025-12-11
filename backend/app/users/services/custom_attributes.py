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


logger = logging.getLogger(__name__)


async def get_attribute_value(
    key: str,
    attributes: List[CustomAttribute],
) -> List[str] | None:
    for attr in attributes:
        if attr.name == key:
            return attr.values
    return None


async def get_custom_attribute(
    custom_attribute_name: str,
    custom_attributes: List[CustomAttribute],
):
    try:

        # None / Empty list
        if not custom_attributes:
            return ""

        custom_attribute_value = await get_attribute_value(
            custom_attribute_name, custom_attributes
        )
        logger.info(
            f"Custom Attribute {custom_attribute_name} value: {custom_attribute_value}"
        )

        return custom_attribute_value

    except ValidationError as e:
        logger.error(f"Validation Error: {e.json()}")
        raise HTTPException(status_code=422, detail="Request data validation error")


# Parse ALL Custom Attributes from IBM User Profile
async def get_user_custom_attributes(
    global_http_client: AsyncClient,
    user_access_token: str,
):
    try:

        settings = get_configuration()

        profile_api_endpoint = settings.profile_api_endpoint
        headers = get_auth_request_headers(user_access_token)
        response = await global_http_client.get(profile_api_endpoint, headers=headers)

    except ValidationError as e:
        logger.error(f"Validation Error: {e.json()}")
        raise HTTPException(status_code=422, detail="Request data validation error")

    if response.status_code == 200:
        json_data = response.json()
        logger.info(f"json repsonse: {json_data}")
        response_data = MeResponse(**json_data)
        custom_attributes = response_data.ibm_extension.custom_attributes
        logger.info(f"Custom Attributes List: {custom_attributes}")
        return custom_attributes

    else:

        logger.error(f"Failed to retrieve profile. Response: {response.text}")

        if response.status_code == 401:
            raise HTTPException(status_code=401, detail="Not authenticated")

        else:
            json_data = response.json()
            error_details = json_data.get("detail")
            raise HTTPException(
                status_code=response.status_code, detail=f"HTTP error, {error_details}"
            )
