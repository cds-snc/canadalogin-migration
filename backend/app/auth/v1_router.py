import logging
from typing import Optional

from fastapi import APIRouter
from fastapi import Request, Response, Depends
from app.auth.schemas import CSRFTokenResponse, RPContextRequest
from app.auth.services.csrf import get_or_create_csrf_token
from app.auth.services.auth import (
    redirect_user_to_idp_verify,
    callback_handler,
    reauthenticate_user,
)
from app.utils.custom_parameters import set_customparameters_in_session
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
from app.rp.services.config import get_config
from app.utils.recovery_errors import AuthenticationRequiredError

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    path="/csrf-token",
    response_model=CSRFTokenResponse,
    summary="Get a CSRF token for the current browser session",
)
async def csrf_token(request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return CSRFTokenResponse(csrf_token=await get_or_create_csrf_token(request))


async def get_rp_context_user_session(
    request: Request, context: RPContextRequest
) -> str:
    # A fresh Verify entry posts RP context before reading its profile. It must
    # start OIDC authentication before this endpoint can store that context.
    if (
        context.rp_client_id.strip()
        and not request.session.get(SessionKeys.SESSION_USER_ACCESS_TOKEN_KEY.value)
        and not request.session.get(SessionKeys.SESSION_USER_TOKEN.value)
    ):
        raise AuthenticationRequiredError("Authentication required")
    return await get_users_current_session(request)


@router.post(
    path="/rp-context",
    summary="Set the relying party for the authenticated browser session",
)
async def set_rp_context(
    request: Request,
    context: RPContextRequest,
    user_access_token: str = Depends(get_rp_context_user_session),
):
    await get_config(context.rp_client_id)
    request.session[SessionKeys.RP_CLIENT_ID_KEY.value] = context.rp_client_id
    return {"success": True}


@router.get(
    path="/login",
    summary="Authenticate user via IBM Verify",
    description="",
)
async def redirect_url(
    request: Request,
    clientId: Optional[str] = None,
    lang: Optional[str] = None,
    customparameters: Optional[str] = None,
):
    set_customparameters_in_session(request, customparameters)
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
