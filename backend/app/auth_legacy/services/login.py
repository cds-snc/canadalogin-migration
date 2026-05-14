import logging

from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse
from httpx import Response

from app.auth_legacy.services.saml import build_saml_login_redirect_url
from app.auth_legacy.services.session_state import (
    LEGACY_CLIENT_NAME_SESSION_KEY,
    LEGACY_PROVIDER_KEY_SESSION_KEY,
    LEGACY_PROVIDER_SESSION_KEY,
    LEGACY_SAML_RELAY_STATE_SESSION_KEY,
    LEGACY_SAML_REQUEST_ID_SESSION_KEY,
)
from app.rp.services.config import get_config
from app.constants.session_keys import SessionKeys
from app.users.services.custom_attributes import get_user_custom_attributes
from app.users.services.get_my_profile import get_ibm_id
from app.users.services.patch import patch_processing_data
from app.utils.auth_flow_logging import log_auth_flow_event
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

PROVIDER_ACR_HINTS = {
    "gckey": ("gckey", "gckey-sim"),
    "interac": ("interac", "interac-sim", "cbs", "cbs-sim"),
    "cbs": ("interac", "interac-sim", "cbs", "cbs-sim"),
    "gccf": ("gccf",),
    "sic": ("sic",),
}


def _normalize_provider_value(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip().lower()


def _legacy_idp_keys(legacy_idp: object) -> set[str]:
    return {
        key
        for key in (
            _normalize_provider_value(getattr(legacy_idp, "provider_key", None)),
            _normalize_provider_value(getattr(legacy_idp, "client_name", None)),
            _normalize_provider_value(getattr(legacy_idp, "client_id", None)),
            _normalize_provider_value(getattr(legacy_idp, "entity_id", None)),
        )
        if key
    }


def _acr_tokens(acr_values: str | None) -> set[str]:
    if not acr_values:
        return set()
    return {
        token.strip().lower()
        for chunk in acr_values.split(",")
        for token in chunk.split()
        if token.strip()
    }


def _legacy_provider_key(legacy_idp: object) -> str:
    return getattr(legacy_idp, "provider_key", None) or _normalize_provider_value(
        getattr(legacy_idp, "client_name", "")
    )


def select_legacy_idp(rp: object, provider: str | None = None):
    legacy_idps = list(getattr(rp, "IDP", []) or [])
    if not legacy_idps:
        raise HTTPException(status_code=400, detail="Legacy IDP configuration not found")

    normalized_provider = _normalize_provider_value(provider)
    if normalized_provider:
        for legacy_idp in legacy_idps:
            if normalized_provider in _legacy_idp_keys(legacy_idp):
                return legacy_idp
        raise HTTPException(
            status_code=400,
            detail=f"Legacy IDP provider '{provider}' is not configured for this RP",
        )

    if len(legacy_idps) == 1:
        return legacy_idps[0]

    rp_acr_tokens = _acr_tokens(getattr(rp, "acr_values", ""))
    for acr_token, provider_keys in PROVIDER_ACR_HINTS.items():
        if acr_token not in rp_acr_tokens:
            continue
        for legacy_idp in legacy_idps:
            if set(provider_keys) & _legacy_idp_keys(legacy_idp):
                return legacy_idp

    raise HTTPException(
        status_code=400,
        detail="Legacy IDP selection is required when multiple legacy IDPs are configured",
    )


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


def _store_selected_legacy_idp_session(
    request: Request,
    *,
    rp: object,
    legacy_idp: object,
    lang: str,
) -> str:
    client_name = f"{rp.rp_client_name}_{legacy_idp.client_name}"
    request.session[SessionKeys.CURRENT_LANGUAGE.value] = lang
    request.session[LEGACY_PROVIDER_SESSION_KEY] = legacy_idp.client_name
    request.session[LEGACY_PROVIDER_KEY_SESSION_KEY] = _legacy_provider_key(legacy_idp)
    request.session[LEGACY_CLIENT_NAME_SESSION_KEY] = client_name
    return client_name


async def _start_legacy_linking(
    request: Request,
    *,
    user_access_token: str,
    session_user_token: str,
    rp_client_id: str,
    lang: str,
    legacy_provider: str,
) -> tuple[str, str, str]:
    correlation_id = ensure_session_correlation_id(request)
    attempt_id = start_linking_attempt_id(request)
    ibm_id = get_ibm_id(session_user_token)
    log_auth_flow_event(
        logger,
        flow="migration",
        step="legacy_linking",
        outcome="started",
        rp_client_id=rp_client_id,
        user_id=ibm_id,
        legacy_provider=legacy_provider,
        lang=lang,
    )

    global_http_client = request.app.state.request_client
    custom_attributes = await get_user_custom_attributes(
        global_http_client, user_access_token
    )
    patch_processing_data_response = await patch_processing_data(
        global_http_client=global_http_client,
        ibm_id=ibm_id,
        rp_client_id=rp_client_id,
        custom_attributes=custom_attributes,
        correlation_id=correlation_id,
        attempt_id=attempt_id,
    )

    _raise_for_failed_processing_patch_response(patch_processing_data_response)
    log_auth_flow_event(
        logger,
        flow="migration",
        step="processing_data_patch",
        outcome="succeeded",
        rp_client_id=rp_client_id,
        user_id=ibm_id,
        legacy_provider=legacy_provider,
    )
    return ibm_id, correlation_id, attempt_id


async def legacy_login(
    request: Request,
    user_access_token: str,
    session_user_token: str,
    rp_client_id: str,
    lang: str = "en",
    provider: str | None = None,
):
    try:
        rp = await get_config(rp_client_id)
        legacy_idp = select_legacy_idp(rp, provider)
        protocol = _normalize_provider_value(getattr(legacy_idp, "protocol", "oidc"))

        if protocol == "oidc":
            return await SIC_legacy_login_auth(
                request,
                user_access_token,
                session_user_token,
                rp_client_id,
                lang,
                rp=rp,
                legacy_idp=legacy_idp,
            )

        if protocol == "saml":
            return await SAML_legacy_login_auth(
                request,
                user_access_token,
                session_user_token,
                rp_client_id,
                lang,
                rp=rp,
                legacy_idp=legacy_idp,
            )

        raise HTTPException(
            status_code=400,
            detail=f"Unsupported legacy IDP protocol '{protocol}'",
        )

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
    *,
    rp=None,
    legacy_idp=None,
):
    try:
        if not rp_client_id:
            raise HTTPException(status_code=400, detail="Missing RP client id")

        if rp is None:
            rp = await get_config(rp_client_id)
        if not getattr(rp, "IDP", None):
            raise HTTPException(
                status_code=400, detail="Legacy IDP configuration not found"
            )

        if legacy_idp is None:
            legacy_idp = select_legacy_idp(rp)

        ui_locales = f"{lang}-CA"
        client_name = _store_selected_legacy_idp_session(
            request,
            rp=rp,
            legacy_idp=legacy_idp,
            lang=lang,
        )
        acr_values = getattr(rp, "acr_values", "")
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
        # Store values needed for callback in the session.
        request.session[f"{client_name}_code_verifier"] = code_verifier
        request.session[f"{client_name}_state"] = state
        request.session[f"{client_name}_nonce"] = nonce

        ibm_id, _, _ = await _start_legacy_linking(
            request,
            user_access_token=user_access_token,
            session_user_token=session_user_token,
            rp_client_id=rp_client_id,
            lang=lang,
            legacy_provider=legacy_idp.client_name,
        )

        redirect_response = await client.authorize_redirect(
            request,
            redirect_uri,
            nonce=nonce,
            state=state,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            ui_locales=ui_locales,
        )
        log_auth_flow_event(
            logger,
            flow="migration",
            step="legacy_authorize_redirect",
            outcome="succeeded",
            rp_client_id=rp_client_id,
            user_id=ibm_id,
            legacy_provider=legacy_idp.client_name,
            lang=lang,
        )
        return redirect_response

    except Exception:
        logger.exception(
            "Unexpected error during SIC legacy login for rp_client_id=%s",
            rp_client_id,
        )
        raise


async def SAML_legacy_login_auth(
    request: Request,
    user_access_token: str,
    session_user_token: str,
    rp_client_id: str,
    lang: str,
    *,
    rp,
    legacy_idp,
):
    try:
        if not rp_client_id:
            raise HTTPException(status_code=400, detail="Missing RP client id")

        _store_selected_legacy_idp_session(
            request,
            rp=rp,
            legacy_idp=legacy_idp,
            lang=lang,
        )
        request_id = f"_{generate_secure_token(18)}"
        relay_state = generate_secure_token()
        request.session[LEGACY_SAML_REQUEST_ID_SESSION_KEY] = request_id
        request.session[LEGACY_SAML_RELAY_STATE_SESSION_KEY] = relay_state

        ibm_id, _, _ = await _start_legacy_linking(
            request,
            user_access_token=user_access_token,
            session_user_token=session_user_token,
            rp_client_id=rp_client_id,
            lang=lang,
            legacy_provider=legacy_idp.client_name,
        )

        redirect_url = await build_saml_login_redirect_url(
            legacy_idp,
            request_id=request_id,
            relay_state=relay_state,
        )
        log_auth_flow_event(
            logger,
            flow="migration",
            step="legacy_saml_authorize_redirect",
            outcome="succeeded",
            rp_client_id=rp_client_id,
            user_id=ibm_id,
            legacy_provider=legacy_idp.client_name,
            lang=lang,
        )
        return RedirectResponse(url=redirect_url, status_code=302)

    except Exception:
        logger.exception(
            "Unexpected error during SAML legacy login for rp_client_id=%s",
            rp_client_id,
        )
        raise
