import logging

from fastapi import HTTPException, Request
from httpx import Response

from app.rp.services.config import get_config
from app.constants.session_keys import SessionKeys
from app.users.services.custom_attributes import get_user_custom_attributes
from app.users.services.get_my_profile import get_ibm_id
from app.users.services.patch import patch_processing_data
from app.utils.correlation_id import (
    ensure_session_correlation_id,
    start_linking_attempt_id,
)
from app.utils.oidc import (
    create_client,
    generate_code_challenge,
    generate_code_verifier,
    generate_secure_token,
    register_client,
)
logger = logging.getLogger(__name__)


def _raise_for_failed_processing_patch_response(
    response: Response | dict,
) -> None:
    if isinstance(response, dict):
        error_detail = response.get("detail") or response.get("error")
        raise HTTPException(
            status_code=502,
            detail=error_detail or "patch_processing_data failed",
        )

    if response.status_code != 204:
        error_detail = "Unknown error"
        try:
            json_data = response.json()
            error_detail = json_data.get("detail", error_detail)
        except Exception:
            try:
                error_detail = response.text or error_detail
            except Exception:
                pass

        raise HTTPException(
            status_code=response.status_code,
            detail=error_detail,
        )


async def legacy_login(
    request: Request,
    user_access_token: str,
    session_user_token: str,
    rp_client_id: str,
    lang: str = "en",
):
    try:
        # RP with SIC only has 1 IDP
        rp = await get_config(rp_client_id)

        # the [0] is the only value returned, just looks odd
        legacy_idp = rp.IDP[0]

        # handle SIC legacy login
        if legacy_idp.client_name == "SIC":
            return await SIC_legacy_login_auth(
                request,
                user_access_token,
                session_user_token,
                rp_client_id,
                lang,
            )

        # handle GCCF legacy login

        # handle GCKey legacy login

        # handle Interac legacy login

    except Exception:
        logger.exception(
            "Unexpected error during legacy login for rp_client_id=%s",
            rp_client_id,
        )
        raise


async def SIC_legacy_login_auth(
    request: Request,
    user_access_token: str,
    session_user_token: str,
    rp_client_id: str,
    lang: str,
):
    try:
        if not rp_client_id:
            raise HTTPException(status_code=400, detail="Missing RP client id")

        global_http_client = request.app.state.request_client

        # RP with SIC only has 1 IDP
        rp = await get_config(rp_client_id)
        if not getattr(rp, "IDP", None):
            raise HTTPException(
                status_code=400, detail="Legacy IDP configuration not found"
            )

        legacy_idp = rp.IDP[0]

        # Unique for RP / IDP combo
        client_name = f"{rp.rp_client_name}_{legacy_idp.client_name}"

        ui_locales = f"{lang}-CA"
        request.session[SessionKeys.CURRENT_LANGUAGE.value] = lang
        request.session["legacy_provider"] = legacy_idp.client_name
        request.session["legacy_client_name"] = client_name
        acr_values = getattr(rp, "acr_values", "")
        correlation_id = ensure_session_correlation_id(request)
        # Register
        await register_client(request, client_name, legacy_idp, ui_locales, acr_values)
        client = await create_client(client_name)
        redirect_uris = getattr(legacy_idp, "redirect_uris", None) or []

        if not redirect_uris:
            raise HTTPException(
                status_code=500,
                detail=f"Legacy IDP '{legacy_idp.client_name}' has no redirect_uris configured",
            )

        redirect_uri = redirect_uris[0]
        # redirect_uri = f"{redirect_uri}?lang={lang}"
        state = generate_secure_token()
        nonce = generate_secure_token()
        code_verifier = generate_code_verifier()
        code_challenge = generate_code_challenge(code_verifier)
        code_challenge_method = legacy_idp.code_challenge_method
        attempt_id = start_linking_attempt_id(request)
        # Store values needed for callback in the session.
        request.session[f"{client_name}_code_verifier"] = code_verifier
        request.session[f"{client_name}_state"] = state
        request.session[f"{client_name}_nonce"] = nonce

        # Add/Update Processing Data in IBM
        # Return IBM Id
        ibm_id = get_ibm_id(session_user_token)
        # Get Users Custom Attributes
        custom_attributes = await get_user_custom_attributes(
            global_http_client, user_access_token
        )
        # AUDIT DATA LOGIC + PATCH
        patch_processing_data_response = await patch_processing_data(
            global_http_client=global_http_client,
            ibm_id=ibm_id,
            rp_client_id=rp_client_id,
            custom_attributes=custom_attributes,
            correlation_id=correlation_id,
            attempt_id=attempt_id,
        )

        _raise_for_failed_processing_patch_response(patch_processing_data_response)

        return await client.authorize_redirect(
            request,
            redirect_uri,
            nonce=nonce,
            state=state,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            ui_locales=ui_locales,
        )

    except Exception:
        logger.exception(
            "Unexpected error during SIC legacy login for rp_client_id=%s",
            rp_client_id,
        )
        raise
