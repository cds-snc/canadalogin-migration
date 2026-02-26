import logging
from typing import Optional

from fastapi import APIRouter
from fastapi import Request, Depends
from app.auth.services.auth import (
    redirect_user_to_idp_verify,
    callback_handler,
    reauthenticate_user,
)
from app.auth.services.auth_user_session import (
    session_event_sse_generator,
)
from app.auth.services.auth_logout import (
    logout_user,
    backchannel_logout,
)

from app.auth.services.auth_user_session import (
    get_users_current_session,
    get_user_id_token,
    session_extend,
)

from app.constants.session_keys import SessionKeys
from app.users.schemas import ProfileResponse
from app.users.services.get_my_profile import get_my_profile

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    path="/login",
    summary="Authenticate user via IBM Verify",
    description="",
)
async def redirect_url(
    request: Request,
    clientId: Optional[str] = None,
    lang: Optional[str] = None,
):
    return await redirect_user_to_idp_verify(request, clientId, lang)


@router.get(
    path="/callback",
    summary="Callback from IBM Verify after user authentication",
    name=SessionKeys.CALLBACK_ROUTE_NAME.value,
    description="",
)
async def callback(
    request: Request,
    lang: Optional[str] = None,
):
    return await callback_handler(request, lang)


@router.get(
    path="/reauth",
    summary="Reauthenticate user via IBM Verify",
    name="reauth",
    description="",
)
async def reauth(
    request: Request,
    returnToPage: str = "/",
    user_access_token: None = Depends(get_users_current_session),
    lang: Optional[str] = None,
):
    return await reauthenticate_user(request, returnToPage, lang)


@router.post(
    path="/logout",
    summary="Logout user",
    description="",
)
async def logout(request: Request, id_token: str = Depends(get_user_id_token)):
    return await logout_user(request, id_token)


@router.post(
    path="/backchannel-logout",
    summary="Backchannel logout",
    description="Allow GC Sign-In to call backchannel logout",
)
async def handle_backchannel_logout(request: Request):
    return await backchannel_logout(request)


@router.get(
    path="/session-status",
    summary="Session status",
    description="Get session status via Server-Sent Events (SSE)",
)
async def session_status(request: Request):
    return await session_event_sse_generator(request)


@router.post(
    path="/keep-alive",
    summary="Keep alive",
    description="Keep the user session alive and return the updated session expire info",
)
async def keep_alive(request: Request):
    return await session_extend(request)


@router.get(
    path="/me",
    response_model=ProfileResponse,
    summary="Get authenticated user profile",
    description="Returns the authenticated user's profile from IBM Verify.",
)
async def get_current_user_profile(
    request: Request, user_access_token: str = Depends(get_users_current_session)
):
    return await get_my_profile(
        request.app.state.request_client,
        user_access_token,
    )
