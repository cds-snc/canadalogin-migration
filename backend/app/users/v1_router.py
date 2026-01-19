import logging

from fastapi import APIRouter, HTTPException
from fastapi import Request, Depends

from app.users.schemas import (
    ProfileResponse,
)

from app.config import get_configuration

from app.auth.services.auth_user_session import get_users_current_session
from app.users.services.custom_attributes import (
    get_custom_attribute,
    get_user_custom_attributes,
)
from app.users.services.get_my_profile import get_ibm_id, get_my_profile
from app.constants.session_keys import SessionKeys


router = APIRouter()
logger = logging.getLogger(__name__)
config = get_configuration()


@router.get(
    path="/profile",
    response_model=ProfileResponse,
    summary="Get a single user's profile",
    description="",
)
async def profile(
    request: Request, user_access_token: str = Depends(get_users_current_session)
):
    return await get_my_profile(
        request.app.state.request_client,
        user_access_token,
    )


# Endpoints below are enabled for Local only - Verify Outputs for Local development
async def verify_local_env():
    if config.ENVIRONMENT != "local":
        raise HTTPException(
            status_code=403, detail="Not available outside local environment"
        )
    return True


@router.get(
    path="/ibmid",
    tags=["Users"],
    summary="LOCAL - Get {attribute}'s value from IBM",
    description="TODO",
    dependencies=[Depends(verify_local_env)],
)
async def handle_get_ibmid(
    request: Request,
    user_access_token: str = Depends(get_users_current_session),
):
    return await get_ibm_id(request.session[SessionKeys.SESSION_USER_TOKEN.value])


@router.get(
    path="/customAttribute/{attribute}",
    tags=["Users"],
    summary="LOCAL - Get {attribute}'s value from IBM",
    description="TODO",
    dependencies=[Depends(verify_local_env)],
)
async def handle_get_custom_attribute(
    request: Request,
    attribute: str,
    user_access_token: str = Depends(get_users_current_session),
):

    custom_attributes = await get_user_custom_attributes(
        request.app.state.request_client,
        user_access_token,
    )

    return await get_custom_attribute(attribute, custom_attributes)


@router.get(
    path="/customAttributes",
    tags=["Users"],
    summary="LOCAL - Get all user's customs attributes ",
    description="TODO",
    dependencies=[Depends(verify_local_env)],
)
async def handle_get_custom_attributes(
    request: Request,
    user_access_token: str = Depends(get_users_current_session),
):
    return await get_user_custom_attributes(
        request.app.state.request_client,
        user_access_token,
    )
