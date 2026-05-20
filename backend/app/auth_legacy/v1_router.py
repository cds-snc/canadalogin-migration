import logging
from typing import Annotated

from fastapi import APIRouter, Form, Query
from fastapi import Request, Depends
from fastapi.responses import Response

from app.auth_legacy.services.callback import (
    legacy_callback,
    legacy_post_logout_callback,
    legacy_saml_acs,
)
from app.auth_legacy.services.login import legacy_login
from app.auth_legacy.services.saml import build_sp_metadata_xml
from app.config import get_configuration
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
    provider: Annotated[
        str | None,
        Query(
            description="Optional legacy IDP provider key, such as sic, gccf, gckey-sim, or interac-sim."
        ),
    ] = None,
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
        provider=provider,
    )


@router.get(
    path="/saml/login/{provider_key}",
    summary="Starts SAML linking flow",
    description="Initiates a SAML authentication request to a configured legacy IDP.",
)
async def handle_legacy_saml_login(
    provider_key: str,
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
        provider=provider_key,
    )


@router.get(
    path="/saml/metadata",
    summary="SAML SP Metadata",
    description="Returns local SAML service provider metadata for legacy IDP simulators.",
)
async def handle_legacy_saml_metadata():
    config = get_configuration()
    metadata_xml = build_sp_metadata_xml(
        entity_id=config.SAML_SP_ENTITY_ID,
        acs_url=config.SAML_SP_ACS_URL,
    )
    return Response(content=metadata_xml, media_type="application/samlmetadata+xml")


@router.post(
    path="/saml/acs",
    summary="SAML Assertion Consumer Service",
    description="Handles SAML HTTP-POST responses from configured legacy IDPs.",
)
async def handle_legacy_saml_acs(
    request: Request,
    saml_response: Annotated[str, Form(..., alias="SAMLResponse")],
    relay_state: Annotated[str | None, Form(alias="RelayState")] = None,
):
    return await legacy_saml_acs(
        request,
        request.session.get(SessionKeys.SESSION_USER_ACCESS_TOKEN_KEY.value),
        request.session.get(SessionKeys.SESSION_USER_TOKEN.value),
        rp_client_id=request.session.get(SessionKeys.RP_CLIENT_ID_KEY.value),
        saml_response=saml_response,
        relay_state=relay_state,
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
    user_access_token: str = Depends(get_users_current_session),
):
    return await skip_account_linking(
        request,
        user_access_token,
        request.session[SessionKeys.SESSION_USER_TOKEN.value],
        rp_client_id=request.session[SessionKeys.RP_CLIENT_ID_KEY.value],
    )
