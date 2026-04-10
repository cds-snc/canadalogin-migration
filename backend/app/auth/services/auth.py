import json
import logging

from fastapi import Request
from fastapi.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuthError
from httpx import AsyncClient
from starsessions.session import get_session_handler
from app.auth.services.oidc_config import oauth
from app.config import get_configuration
from app.constants.session_keys import SessionKeys
from app.utils.request_error_handler import RequestErrorHandler
from app.auth.services.auth_user_session import (
    get_users_current_session,
    update_session_tokens,
)
from app.constants.patch_keys import PatchKeys
from app.users.services.custom_attributes import (
    get_custom_attribute,
    get_user_custom_attributes,
)
from app.users.schemas import AuditDataSchema
from app.utils.auth_flow_logging import hash_identifier, log_auth_flow_event
from app.utils.correlation_id import ensure_session_correlation_id

logger = logging.getLogger(__name__)


async def get_http_client(request: Request) -> AsyncClient:
    return request.app.state.request_client


def get_base_profile_management_url():
    config = get_configuration()
    redirectValue = config.MIGRATION_SOLUTION_DOMAIN

    if config.ENVIRONMENT != "local":
        redirectValue = f"https://{config.MIGRATION_SOLUTION_DOMAIN}"
    return redirectValue


def get_callback_redirect_uri(request: Request):
    """
    Get the redirect URI for the OAuth login flow.
    """
    config = get_configuration()
    redirect_uri = request.url_for(SessionKeys.CALLBACK_ROUTE_NAME.value)

    if config.ENVIRONMENT != "local":
        redirect_uri = str(redirect_uri).replace("http://", "https://")

    logger.info("Callback Redirect URI: %s", redirect_uri)
    return redirect_uri


async def redirect_user_to_idp_verify(request: Request, clientId: str, lang: str):
    """
    Get the redirect URL for the OAuth login flow.
    This function is used to initiate the login process with IBM Verify.
    """
    try:
        ensure_session_correlation_id(request)

        # Add Client Id from Ibm
        request.session[SessionKeys.RP_CLIENT_ID_KEY.value] = clientId
        log_auth_flow_event(
            logger,
            flow="verify",
            step="authorize_redirect",
            outcome="started",
            rp_client_id=clientId,
            lang=lang,
        )

        # TODO: Redirect if clientId = NULL

        callback_redirect_uri = get_callback_redirect_uri(request)
        callback_redirect_uri = f"{callback_redirect_uri}?lang={lang}"

        redirect_response = await oauth.verify.authorize_redirect(
            request, callback_redirect_uri, ui_locales=lang
        )
        log_auth_flow_event(
            logger,
            flow="verify",
            step="authorize_redirect",
            outcome="succeeded",
            rp_client_id=clientId,
            lang=lang,
        )
        return redirect_response

    except Exception as e:
        logger.exception("Unexpected error during redirect_to_verify")
        RequestErrorHandler.handle(e, context="Unexpected error during idp redirect")


async def callback_handler(request: Request, lang: str):
    """
    Get the redirect URL for the OAuth login flow.
    This function is used to initiate the login process with IBM Verify.
    """
    try:
        ensure_session_correlation_id(request)
        redirectValue = get_base_profile_management_url()
        returnToPageValue = request.session.get(SessionKeys.RETURN_TO_PAGE.value)
        rp_client_id = request.session.get(SessionKeys.RP_CLIENT_ID_KEY.value)
        log_auth_flow_event(
            logger,
            flow="verify",
            step="callback",
            outcome="started",
            rp_client_id=rp_client_id,
            lang=lang,
        )

        if returnToPageValue:
            clientRedirectValue = f"{returnToPageValue}?{SessionKeys.RETURN_TO_PAGE.value}={returnToPageValue}"
            redirectValue += clientRedirectValue
            logger.info("Return to page set in session: %s", redirectValue)

        try:
            oidc_response = await oauth.verify.authorize_access_token(request)
        except OAuthError as error:
            logger.error("OAuth error during token retrieval")
            logger.error("Redirecting user back to IBM Verify for re-authentication")
            # redirect back to IBM Verify to retry authentication
            raise OAuthError("Invalid or expired token") from error
        user_info = oidc_response.get("userinfo", {})
        log_auth_flow_event(
            logger,
            flow="verify",
            step="token_exchange",
            outcome="succeeded",
            rp_client_id=rp_client_id,
            user_id=user_info.get("sub"),
            auth_methods=user_info.get("amr"),
        )

        # Get the handler and set your sid as session id. sid is uuid passed in id_token
        handler = get_session_handler(request)
        new_session_id = user_info.get("sid")
        handler.session_id = new_session_id

        update_session_tokens(request, oidc_response)
        log_auth_flow_event(
            logger,
            flow="verify",
            step="session_established",
            outcome="succeeded",
            rp_client_id=rp_client_id,
            user_id=user_info.get("sub"),
            session_id_hash=hash_identifier(user_info.get("sid")),
        )

        if lang:
            redirectValue = f"{redirectValue}/{lang}"

        logger.info("Redirect to MIGRATION_SOLUTION_DOMAIN: %s", redirectValue)
        log_auth_flow_event(
            logger,
            flow="verify",
            step="callback",
            outcome="succeeded",
            rp_client_id=rp_client_id,
            user_id=user_info.get("sub"),
            lang=lang,
        )
        return RedirectResponse(url=redirectValue)
    except OAuthError as error:
        logger.error("OAuth error during callback handling")
        raise OAuthError("Invalid or expired token") from error
    except Exception as e:
        logger.exception("Unexpected error during callback handling")
        RequestErrorHandler.handle(e, context="Unexpected error during idp redirect")


async def reauthenticate_user(
    request: Request, returnToPage: str = "/", lang: str = None
):
    """
    Get the redirect URL for the OAuth login flow.
    This function is used to initiate a reauthentication flow with IBM Verify.
    """
    try:
        ensure_session_correlation_id(request)
        rp_client_id = request.session.get(SessionKeys.RP_CLIENT_ID_KEY.value)
        log_auth_flow_event(
            logger,
            flow="verify",
            step="reauthenticate",
            outcome="started",
            rp_client_id=rp_client_id,
            lang=lang,
        )

        callback_redirect_uri = get_callback_redirect_uri(request)

        if returnToPage:
            request.session[SessionKeys.RETURN_TO_PAGE.value] = returnToPage
            logger.info("Return to page set in session: %s", returnToPage)

        # if the user recently logged in, we can set the max age to 15 minutes
        # will reautenticate after max age value
        max_age_in_seconds = 900
        redirect_response = await oauth.verify.authorize_redirect(
            request, callback_redirect_uri, max_age=max_age_in_seconds
        )
        log_auth_flow_event(
            logger,
            flow="verify",
            step="reauthenticate",
            outcome="succeeded",
            rp_client_id=rp_client_id,
            lang=lang,
            return_to_page=bool(returnToPage),
        )
        return redirect_response
    except OAuthError as error:
        logger.exception("Unexpected error during redirect_to_verify")
        raise OAuthError("Invalid or expired token") from error
    except Exception as e:
        logger.exception("Unexpected error during redirect_to_verify")
        RequestErrorHandler.handle(e, context="Unexpected error")


async def verify_audit_status(
    request: Request,
):
    """
    Verify if the user's audit status allows access.
    """
    try:
        http_client = await get_http_client(request)
        user_access_token = await get_users_current_session(request)

        custom_attributes = await get_user_custom_attributes(
            http_client,
            user_access_token,
        )

        if not custom_attributes:
            logger.error("Missing custom attributes for user.")
            return False

        audit_data_array = get_custom_attribute(
            PatchKeys.AUDIT_DATA_KEY.value, custom_attributes
        )

        # Parse into Pydantic model
        if not audit_data_array:
            return []

        audit_data_array_parsed = [
            AuditDataSchema(**json.loads(item)) for item in audit_data_array
        ]
        log_auth_flow_event(
            logger,
            flow="verify",
            step="audit_status_lookup",
            outcome="succeeded",
            rp_client_id=request.session.get(SessionKeys.RP_CLIENT_ID_KEY.value),
            audit_record_count=len(audit_data_array_parsed),
        )

        return audit_data_array_parsed

    except Exception:
        logger.exception("Error verifying audit status")
        return False
