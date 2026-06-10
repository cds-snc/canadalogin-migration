import logging

from fastapi import Request

from fastapi.responses import RedirectResponse

from app.auth_legacy.services.session_state import clear_legacy_oidc_session
from app.rp.services.config import get_config
from app.rp.services.config import resolve_rp_redirect_uri
from app.constants.audit_status_keys import AuditStatusKeys
from app.users.services.custom_attributes import get_user_custom_attributes
from app.users.services.get_my_profile import get_ibm_id
from app.users.services.patch import patch_audit_data
from app.utils.auth_flow_logging import log_auth_flow_event
from app.utils.correlation_id import (
    ensure_linking_attempt_id,
    ensure_session_correlation_id,
)
from app.utils.custom_parameters import (
    append_customparameters_to_url,
    get_rp_return_parameters_from_session,
)

logger = logging.getLogger(__name__)


# Update User on IBM (Skipped) and redirect to RP
async def skip_account_linking(
    request: Request,
    user_access_token: str,
    session_user_token: str,
    rp_client_id: str,
):
    correlation_id = ensure_session_correlation_id(request)
    attempt_id = ensure_linking_attempt_id(request)

    ibm_id = get_ibm_id(session_user_token)
    log_auth_flow_event(
        logger,
        flow="migration",
        step="skip_linking",
        outcome="started",
        rp_client_id=rp_client_id,
        user_id=ibm_id,
    )

    global_http_client = request.app.state.request_client
    custom_attributes = await get_user_custom_attributes(
        global_http_client, user_access_token
    )

    # AUDIT DATA LOGIC + PATCH
    await patch_audit_data(
        global_http_client=global_http_client,
        ibm_id=ibm_id,
        rp_client_id=rp_client_id,
        custom_attributes=custom_attributes,
        status=AuditStatusKeys.SKIPPED_KEY.value,
        correlation_id=correlation_id,
        attempt_id=attempt_id,
    )
    log_auth_flow_event(
        logger,
        flow="migration",
        step="audit_patch",
        outcome="succeeded",
        rp_client_id=rp_client_id,
        user_id=ibm_id,
        audit_status=AuditStatusKeys.SKIPPED_KEY.value,
    )

    rp = await get_config(rp_client_id)
    return_parameters = get_rp_return_parameters_from_session(request)

    redirect_url = append_customparameters_to_url(
        resolve_rp_redirect_uri(rp, return_parameters.get("lang")),
        return_parameters,
    )
    log_auth_flow_event(
        logger,
        flow="migration",
        step="skip_linking",
        outcome="succeeded",
        rp_client_id=rp_client_id,
        user_id=ibm_id,
        lang=return_parameters.get("lang"),
    )
    clear_legacy_oidc_session(request, clear_attempt_id=True)

    return RedirectResponse(url=redirect_url, status_code=302)
