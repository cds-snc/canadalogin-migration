import logging
import httpx

from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from urllib.parse import quote

from app.config import get_configuration
from app.constants.audit_status_keys import AuditStatusKeys
from app.rp.services.config import get_config
from app.users.services.custom_attributes import get_user_custom_attributes
from app.users.services.get_my_profile import get_ibm_id
from app.users.services.patch import patch_legacy_pai, patch_audit_data
from app.utils.oidc import create_client


logger = logging.getLogger(__name__)


async def legacy_callback(
    request: Request,
    user_access_token: str,
    session_user_token: str,
    rp_client_id: str,
):
    try:

        # RP with SIC only has 1 IDP
        rp = await get_config(rp_client_id)
        legacy_idp = rp.IDP[0]

        # Unique for RP / IDP combo
        client_name = f"{rp.rp_client_name}_{legacy_idp.client_name}"
        logger.info(f"Callback Client Name: {client_name}")
        client = await create_client(client_name)

        # Exchange authorization code for tokens
        verifier = request.session.get(f"{client_name}_code_verifier")
        token = await client.authorize_access_token(request, code_verifier=verifier)

        # Parse ID token & extract legacy PAI
        nonce = request.session.get(f"{client_name}_nonce")
        state = request.session.get(f"{client_name}_state")
        user = await client.parse_id_token(token, nonce)
        legacy_pai = user["sub"]

        global_http_client = request.app.state.request_client

        # Return IBM Id
        ibm_id = await get_ibm_id(session_user_token)

        # Get Users Custom Attributes
        custom_attributes = await get_user_custom_attributes(
            global_http_client, user_access_token
        )

        # LEGACY_PAI LOGIC + PATCH
        patch_legacy_pai_response = await patch_legacy_pai(
            global_http_client, ibm_id, rp_client_id, custom_attributes, legacy_pai
        )

        if patch_legacy_pai_response.status_code != 204:
            # parse error details safely
            json_data = patch_legacy_pai_response.json()
            error_detail = json_data.get("detail", "Unknown error")
            raise HTTPException(
                status_code=patch_legacy_pai_response.status_code, detail=error_detail
            )

        # AUDIT DATA LOGIC + PATCH
        patch_audit_data_response = await patch_audit_data(
            global_http_client,
            ibm_id,
            rp_client_id,
            custom_attributes,
            AuditStatusKeys.LINKED_KEY.value,
        )

        if patch_audit_data_response.status_code != 204:
            # parse error details safely
            json_data = patch_audit_data_response.json()
            error_detail = json_data.get("detail", "Unknown error")
            raise HTTPException(
                status_code=patch_audit_data_response.status_code, detail=error_detail
            )

        # The discovery metadata is stored here:
        idp_metadata = client.server_metadata
        logger.info(f"IDP Metadata: {idp_metadata}")

        # Grab the logout endpoint
        end_session_endpoint = idp_metadata["server_metadata"].get(
            "end_session_endpoint"
        )

        encoded_post_logout_redirect_uri = quote(
            "http://localhost:8000/v1/auth/legacy/post_logout", safe=""
        )

        # Build the logout url for the Legacy IDP
        logout_url = (
            f"{end_session_endpoint}"
            f"?id_token_hint={token["id_token"]}"
            f"&post_logout_redirect_uri={encoded_post_logout_redirect_uri}"
            f"&state={state}"
            f"&client_id=e1a58c16-a649-45e1-b80c-3cd3daaeea0d"
        )

        logger.info(f"Logout URL: {logout_url}")

        return RedirectResponse(url=logout_url)

    except httpx.HTTPStatusError as e:
        # HTTPX error for status codes like 401
        if e.response.status_code == 401:
            return {"error": "Unauthorized: Invalid credentials or token"}
        return {"error": f"HTTP error: {e.response.status_code}"}

    except ValidationError as e:
        logger.error(f"Validation Error: {e.json()}")
        raise HTTPException(status_code=422, detail="Request data validation error")


async def legacy_post_logout_callback():
    # Logged out of legacy IDP Redierct to Profile Management

    settings = get_configuration()

    # TODO: Retrieve Lang Parameter
    lang = "/en"
    page = "/link/success"

    redirect_url = f"{settings.PROFILE_MANAGEMENT_DOMAIN}{lang}{page}"

    return RedirectResponse(url=redirect_url, status_code=302)
