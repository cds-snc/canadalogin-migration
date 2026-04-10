import logging

from fastapi import HTTPException
from pydantic import ValidationError
from httpx import AsyncClient

from app.users.schemas import (
    IBMVerifyUserProfileSchema,
    ProfileResponse,
    UserToken,
)
from app.utils.access_token import get_auth_request_headers
from app.utils.request_error_handler import RequestErrorHandler
from app.config import get_configuration

logger = logging.getLogger(__name__)


async def dispatch_get_my_profile_from_ibm(
    global_http_client: AsyncClient,
    user_access_token: str,
) -> IBMVerifyUserProfileSchema:
    """
    Fetch user profile data from IBM Verify API and return as Pydantic model.

    Args:
        request: FastAPI request object
        user_access_token: User's authentication token

    Returns:
        IBMVerifyUserProfileSchema: Validated user profile data from IBM Verify

    Raises:
        HTTPException: Via RequestErrorHandler for any request failures
    """
    try:
        settings = get_configuration()
        profile_api_endpoint = settings.profile_api_endpoint
        response = await global_http_client.get(
            profile_api_endpoint,
            headers=get_auth_request_headers(user_access_token),
        )
        response.raise_for_status()

        json_data = response.json()

        return IBMVerifyUserProfileSchema(**json_data)
    except Exception as e:
        logger.error("Error fetching profile from IBM Verify", exc_info=True)
        RequestErrorHandler.handle(e)


async def get_my_profile(
    global_http_client: AsyncClient, user_access_token: str
) -> ProfileResponse:
    """
    Retrieve and return the authenticated user's profile with masked phone numbers.

    Args:
        request: FastAPI request object
        user_access_token: Authenticated User's access token

    Returns:
        ProfileResponse: User profile data with masked phone numbers

    Raises:
        HTTPException: For authentication, validation, or server errors
    """
    profile_response = await dispatch_get_my_profile_from_ibm(
        global_http_client, user_access_token
    )
    profile_data = profile_response.model_dump()

    try:
        response_data = IBMVerifyUserProfileSchema(**profile_data)
    except ValidationError:
        logger.error("Profile validation error")
        raise HTTPException(status_code=422, detail="Request data validation error")
    return ProfileResponse(
        success=True,
        message="User profile retrieved successfully.",
        data=response_data,
    )


# Retrieve user's IBM ID from User Token
def get_ibm_id(
    user_token: str,
):
    try:

        token = UserToken(**user_token)

        # TODO: which value to use
        # ibm_id = token.userinfo.sub
        # ibm_id = token.userinfo.uid
        ibm_id = token.userinfo.uniqueSecurityName
        return ibm_id

    except Exception:
        logger.error("Exception while extracting IBM id from user token")
        raise
