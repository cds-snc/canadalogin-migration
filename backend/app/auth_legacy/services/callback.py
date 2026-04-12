import logging
import httpx

from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuthError
from pydantic import ValidationError
from urllib.parse import quote

from app.config import get_configuration
from app.auth.services.auth import get_base_profile_management_url
from app.constants.session_keys import SessionKeys
from app.constants.audit_status_keys import AuditStatusKeys
from app.rp.services.config import get_config
from app.users.services.custom_attributes import get_user_custom_attributes
from app.users.services.get_my_profile import get_ibm_id
from app.users.services.patch import patch_legacy_pai, patch_audit_data
from app.utils.auth_flow_logging import log_auth_flow_event
from app.utils.correlation_id import (
    bind_linking_attempt_id,
    bind_session_correlation_id,
    clear_linking_attempt_id,
    ensure_linking_attempt_id,
    ensure_session_correlation_id,
)
from app.utils.oidc import create_client
from app.utils.request_error_handler import RequestErrorHandler

config = get_configuration()
logger = logging.getLogger(__name__)


def _extract_error_detail(response: httpx.Response) -> str:
    """Best-effort extraction of upstream error details for client responses."""
    try:
        payload = response.json()
    except ValueError:
        text = (response.text or "").strip()
        return text or "Unknown error"

    return (
        payload.get("detail")
        or payload.get("message")
        or payload.get("error")
        or payload.get("messageId")
        or "Unknown error"
    )


def _raise_for_failed_patch_response(
    response: httpx.Response | dict, operation_name: str
) -> None:
    """
    Normalize patch helper failures into HTTPException.

    Patch helpers may return an httpx.Response or a dict error payload.
    """
    if isinstance(response, dict):
        error_detail = (
            response.get("detail")
            or response.get("error")
            or f"{operation_name} failed"
        )
        raise HTTPException(status_code=502, detail=error_detail)

    if response.status_code != 204:
        raise HTTPException(
            status_code=response.status_code,
            detail=_extract_error_detail(response),
        )


def get_target_rp_client_ids(
    rp_client_id: str, dependent_client_ids: list[str]
) -> list[str]:
    """Return ordered unique RP client IDs for linking writes."""
    # Keep the primary RP first, then configured direct dependents.
    return list(dict.fromkeys([rp_client_id, *dependent_client_ids]))


def normalize_language(lang: str | None) -> str:
    """Normalize language codes to supported values."""
    if not lang or not isinstance(lang, str):
        return "en"

    language = lang.strip().lower()
    return language if language in ("en", "fr") else "en"


async def legacy_callback(
    request: Request,
    user_access_token: str,
    session_user_token: str,
    rp_client_id: str,
):
    try:
        correlation_id = ensure_session_correlation_id(request)
        attempt_id = ensure_linking_attempt_id(request)
        session_rp_client_id = request.session.get(SessionKeys.RP_CLIENT_ID_KEY.value)
        if session_rp_client_id:
            rp_client_id = session_rp_client_id
        elif not rp_client_id:
            raise HTTPException(status_code=400, detail="Missing RP client id")
        log_auth_flow_event(
            logger,
            flow="migration",
            step="legacy_callback",
            outcome="started",
            rp_client_id=rp_client_id,
        )

        # RP with SIC only has 1 IDP
        rp = await get_config(rp_client_id)
        legacy_idp = rp.IDP[0]

        # Unique for RP / IDP combo
        client_name = f"{rp.rp_client_name}_{legacy_idp.client_name}"
        client = await create_client(client_name)
        # Exchange authorization code for tokens
        verifier = request.session.get(f"{client_name}_code_verifier")
        try:
            token = await client.authorize_access_token(request, code_verifier=verifier)
        except OAuthError as e:
            logger.error("OAuth error during legacy callback token retrieval")
            RequestErrorHandler.handle(e, context="OAuth error during legacy callback")
        log_auth_flow_event(
            logger,
            flow="migration",
            step="legacy_token_exchange",
            outcome="succeeded",
            rp_client_id=rp_client_id,
            legacy_provider=legacy_idp.client_name,
        )

        # Parse ID token & extract legacy PAI
        nonce = request.session.get(f"{client_name}_nonce")
        state = request.session.get(f"{client_name}_state")
        if "id_token" not in token:
            logger.error(
                "Token response missing id_token. Check requested scope includes 'openid'. "
                "Token keys: %s",
                list(token.keys()),
            )
            raise HTTPException(
                status_code=500,
                detail="Token response missing id_token (scope likely missing 'openid')",
            )

        user = await client.parse_id_token(token, nonce)
        legacy_pai = user["sub"]

        global_http_client = request.app.state.request_client

        # Return IBM Id
        ibm_id = get_ibm_id(session_user_token)
        log_auth_flow_event(
            logger,
            flow="migration",
            step="legacy_identity_resolved",
            outcome="succeeded",
            rp_client_id=rp_client_id,
            user_id=ibm_id,
            legacy_provider=legacy_idp.client_name,
        )

        # Get Users Custom Attributes
        custom_attributes = await get_user_custom_attributes(
            global_http_client, user_access_token
        )

        # LEGACY_PAI LOGIC + PATCH
        target_rp_client_ids = get_target_rp_client_ids(
            rp_client_id,
            rp.dependent_client_ids,
        )
        patch_legacy_pai_response = await patch_legacy_pai(
            global_http_client=global_http_client,
            ibm_id=ibm_id,
            rp_client_id=rp_client_id,
            custom_attributes=custom_attributes,
            legacy_pai=legacy_pai,
            target_rp_client_ids=target_rp_client_ids,
            correlation_id=correlation_id,
            attempt_id=attempt_id,
        )
        _raise_for_failed_patch_response(
            patch_legacy_pai_response, operation_name="patch_legacy_pai"
        )
        log_auth_flow_event(
            logger,
            flow="migration",
            step="legacy_pai_patch",
            outcome="succeeded",
            rp_client_id=rp_client_id,
            user_id=ibm_id,
            legacy_provider=legacy_idp.client_name,
            target_rp_client_count=len(target_rp_client_ids),
        )

        # AUDIT DATA LOGIC + PATCH
        patch_audit_data_response = await patch_audit_data(
            global_http_client=global_http_client,
            ibm_id=ibm_id,
            rp_client_id=rp_client_id,
            custom_attributes=custom_attributes,
            status=AuditStatusKeys.LINKED_KEY.value,
            correlation_id=correlation_id,
            attempt_id=attempt_id,
        )
        _raise_for_failed_patch_response(
            patch_audit_data_response, operation_name="patch_audit_data"
        )
        log_auth_flow_event(
            logger,
            flow="migration",
            step="audit_patch",
            outcome="succeeded",
            rp_client_id=rp_client_id,
            user_id=ibm_id,
            audit_status=AuditStatusKeys.LINKED_KEY.value,
            legacy_provider=legacy_idp.client_name,
        )

        # The discovery metadata is stored here:
        idp_metadata = client.server_metadata
        if not config.LEGACY_IDP_LOGOUT_ENABLED:
            logger.info("Legacy IdP logout disabled; skipping end-session redirect.")
            log_auth_flow_event(
                logger,
                flow="migration",
                step="legacy_logout_redirect",
                outcome="skipped",
                rp_client_id=rp_client_id,
                user_id=ibm_id,
                legacy_provider=legacy_idp.client_name,
            )
            return await legacy_post_logout_callback(request)

        # Grab the logout endpoint
        end_session_endpoint = idp_metadata["server_metadata"].get(
            "end_session_endpoint"
        )

        post_logout_redirect_uri = request.url_for("handle_legacy_post_logout_callback")
        if config.ENVIRONMENT != "local":
            post_logout_redirect_uri = str(post_logout_redirect_uri).replace(
                "http://", "https://"
            )

        encoded_post_logout_redirect_uri = quote(str(post_logout_redirect_uri), safe="")

        # Build the logout url for the Legacy IDP
        logout_url = (
            f"{end_session_endpoint}"
            f"?id_token_hint={token['id_token']}"
            f"&post_logout_redirect_uri={encoded_post_logout_redirect_uri}"
            f"&state={state}"
            f"&client_id=e1a58c16-a649-45e1-b80c-3cd3daaeea0d"
        )
        log_auth_flow_event(
            logger,
            flow="migration",
            step="legacy_logout_redirect",
            outcome="succeeded",
            rp_client_id=rp_client_id,
            user_id=ibm_id,
            legacy_provider=legacy_idp.client_name,
        )

        return RedirectResponse(url=logout_url)

    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code if e.response else 502
        error_detail = (
            _extract_error_detail(e.response) if e.response else "Unknown error"
        )
        logger.error(
            "legacy_callback upstream HTTP error status=%s detail=%s",
            status_code,
            error_detail,
            exc_info=True,
        )
        raise HTTPException(status_code=status_code, detail=error_detail) from e

    except ValidationError:
        logger.error("Validation error during legacy callback")
        raise HTTPException(status_code=422, detail="Request data validation error")
    except OAuthError as e:
        raise e
    except Exception as e:
        logger.exception("Unexpected error during legacy callback")
        RequestErrorHandler.handle(e, context="Unexpected error during legacy callback")


async def legacy_post_logout_callback(request: Request):
    # Logged out of legacy IDP Redirect to profile management language sync page.
    bind_session_correlation_id(request)
    bind_linking_attempt_id(request)
    lang = normalize_language(request.session.get(SessionKeys.CURRENT_LANGUAGE.value))
    lang_path = "/" + lang
    page_path = "/link/lang-sync"

    base_profile_url = get_base_profile_management_url()
    redirect_url = f"{base_profile_url}{lang_path}{page_path}"
    log_auth_flow_event(
        logger,
        flow="migration",
        step="post_logout_redirect",
        outcome="succeeded",
        rp_client_id=request.session.get(SessionKeys.RP_CLIENT_ID_KEY.value),
        lang=lang,
    )
    clear_linking_attempt_id(request)

    return RedirectResponse(url=redirect_url, status_code=302)
