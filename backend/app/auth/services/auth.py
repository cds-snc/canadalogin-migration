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

# Get the desired log level from configuration
config = get_configuration()
log_level_str = config.LOG_LEVEL.upper()

# Convert string level to the logging module's level constant (e.g., "DEBUG" to logging.DEBUG)
log_level = getattr(logging, log_level_str, logging.INFO)

# Apply the configuration
logging.basicConfig(level=log_level)

logger = logging.getLogger(__name__)


async def get_http_client(request: Request) -> AsyncClient:
    return request.app.state.request_client


def get_base_profile_management_url():
    config = get_configuration()
    redirectValue = config.MIGRATON_SOLUTION_DOMAIN

    if config.ENVIRONMENT != "local":
        redirectValue = f"https://{config.MIGRATON_SOLUTION_DOMAIN}"
    return redirectValue


def get_callback_redirect_uri(request: Request):
    """
    Get the redirect URI for the OAuth login flow.
    """
    config = get_configuration()
    redirect_uri = request.url_for(SessionKeys.CALLBACK_ROUTE_NAME.value)

    if config.ENVIRONMENT != "local":
        redirect_uri = str(redirect_uri).replace("http://", "https://")

    logger.info(f"Callback Redirect URI: {redirect_uri}")
    return redirect_uri


async def redirect_user_to_idp_verify(request: Request, clientId: str, lang: str):
    """
    Get the redirect URL for the OAuth login flow.
    This function is used to initiate the login process with IBM Verify.
    """
    try:

        # Add Client Id from Ibm
        request.session[SessionKeys.RP_CLIENT_ID_KEY.value] = clientId

        # TODO: Redirect if clientId = NULL

        logger.info(f"Language selected: {lang}")

        callback_redirect_uri = get_callback_redirect_uri(request)
        callback_redirect_uri = f"{callback_redirect_uri}?lang={lang}"

        return await oauth.verify.authorize_redirect(
            request, callback_redirect_uri, ui_locales=lang
        )

    except Exception as e:
        logger.exception("Unexpected error during redirect_to_verify", str(e))
        RequestErrorHandler.handle(e, context="Unexpected error during idp redirect")


async def callback_handler(request: Request, lang: str):
    """
    Get the redirect URL for the OAuth login flow.
    This function is used to initiate the login process with IBM Verify.
    """
    try:
        logger.info(f"lang in callback: {lang}")
        redirectValue = get_base_profile_management_url()
        returnToPageValue = request.session.get(SessionKeys.RETURN_TO_PAGE.value)

        if returnToPageValue:
            clientRedirectValue = f"{returnToPageValue}?{SessionKeys.RETURN_TO_PAGE.value}={returnToPageValue}"
            redirectValue += clientRedirectValue
            logger.info(f"Return to page set in session: {redirectValue}")

        try:
            oidc_response = await oauth.verify.authorize_access_token(request)
            logger.info("OIDC Responsed")
        except OAuthError as error:
            logger.error(f"OAuth error during token retrieval: {error}")
            logger.error(
                f"Redirect user back to IBM Verify to be re-authenticated: {redirectValue}"
            )
            # redirect back to IBM Verify to retry authentication
            raise OAuthError("Invalid or expired token") from error

        # Get the handler and set your sid as session id. sid is uuid passed in id_token
        handler = get_session_handler(request)
        new_session_id = oidc_response.get("userinfo").get("sid")
        handler.session_id = new_session_id

        update_session_tokens(request, oidc_response)

        if lang:
            redirectValue = f"{redirectValue}/{lang}"

        logger.info("OIDC Callback Handler")
        logger.info(f"Redirect to MIGRATON_SOLUTION_DOMAIN: {redirectValue}")
        return RedirectResponse(url=redirectValue)
    except OAuthError as error:
        logger.error(f"OAuth error: {error}")
        raise OAuthError("Invalid or expired token") from error
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        RequestErrorHandler.handle(e, context="Unexpected error during idp redirect")


async def reauthenticate_user(
    request: Request, returnToPage: str = "/", lang: str = None
):
    """
    Get the redirect URL for the OAuth login flow.
    This function is used to initiate a reauthentication flow with IBM Verify.
    """
    try:

        callback_redirect_uri = get_callback_redirect_uri(request)

        if returnToPage:
            request.session[SessionKeys.RETURN_TO_PAGE.value] = returnToPage
            logger.info(f"Return to page set in session: {returnToPage}")

        # if the user recently logged in, we can set the max age to 15 minutes
        # will reautenticate after max age value
        max_age_in_seconds = 900
        return await oauth.verify.authorize_redirect(
            request, callback_redirect_uri, max_age=max_age_in_seconds
        )
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

        audit_data_array = await get_custom_attribute(
            PatchKeys.AUDIT_DATA_KEY.value, custom_attributes
        )

        # Parse into Pydantic model
        if not audit_data_array:
            audit_data_array_parsed = []

        else:
            audit_data_array_parsed = [
                AuditDataSchema(**json.loads(item)) for item in audit_data_array
            ]

        logger.debug(f"Audit Object from Custom Attributes: {audit_data_array_parsed}")

    except Exception as e:
        logger.error(f"Error verifying audit status: {e}")
        return False
