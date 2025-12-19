import logging

from fastapi import APIRouter, Request

from app.constants.session_keys import SessionKeys
from app.rp.services.config import get_rp_config_details


router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    path="/rpConfigDetails",
    summary="RP Configuration Details",
    description="Returns the RP Configuration Details for redirection post migration and display purposes.",
)
async def handle_get_rp_config_details(
    request: Request,
):
    return await get_rp_config_details(
        rp_client_id=request.session[SessionKeys.RP_CLIENT_ID_KEY.value],
    )
