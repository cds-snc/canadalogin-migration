import logging

from fastapi import APIRouter, Query
from fastapi import Request, Depends

from app.auth_legacy.services.callback import (
    legacy_callback,
    legacy_post_logout_callback,
)
from app.auth_legacy.services.login import legacy_login
from app.auth_legacy.services.skip import skip_account_linking
from app.auth.services.auth_user_session import get_users_current_session
from app.constants.session_keys import SessionKeys

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    path="/login",
    summary="Starts the linking flow",
    description="Initiates the OIDC authentication request to the legacy IDP for linking legacy pai",
)
async def handle_legacy_login(
    request: Request,
    lang: str = Query("en"),
    user_access_token: str = Depends(get_users_current_session),
):
    lang = lang.lower()
    if lang not in ("en", "fr"):
        lang = "en"

    return await legacy_login(
        request,
        user_access_token,
        request.session[SessionKeys.SESSION_USER_TOKEN.value],
        rp_client_id=request.session[SessionKeys.RP_CLIENT_ID_KEY.value],
        lang=lang,
    )


@router.get(
    path="/callback",
    summary="Legacy IDP CallBack Endpoint",
    description="Handles the legacy IDP OIDC authentication callback",
)
async def handle_legacy_callback(
    request: Request,
    user_access_token: str = Depends(get_users_current_session),
):
    return await legacy_callback(
        request,
        user_access_token,
        request.session[SessionKeys.SESSION_USER_TOKEN.value],
        rp_client_id=request.session[SessionKeys.RP_CLIENT_ID_KEY.value],
    )


# post_logout
@router.get(
    path="/post_logout",
    summary="Legacy IDP Logout Callabck Endpoint",
    description="Handles the logout callback for legacy IDP, and redirects user",
)
async def handle_legacy_post_logout_callback(
    request: Request,
    user_access_token: str = Depends(get_users_current_session),
):
    return await legacy_post_logout_callback(request)


@router.get(
    path="/skip",
    summary="Skip Linking",
    description="Handles skip flow, updating IBM Profile and redirecting to RP",
)
async def handle_skip_account_linking(
    request: Request,
    lang: str | None = None,
    user_access_token: str = Depends(get_users_current_session),
):
    if lang is not None:
        lang = lang.lower()
        if lang not in ("en", "fr"):
            lang = "en"
        request.session[SessionKeys.CURRENT_LANGUAGE.value] = lang

    return await skip_account_linking(
        request,
        user_access_token,
        request.session[SessionKeys.SESSION_USER_TOKEN.value],
        rp_client_id=request.session[SessionKeys.RP_CLIENT_ID_KEY.value],
    )
