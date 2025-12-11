import logging

from fastapi import APIRouter, Request

from app.constants.session_keys import SessionKeys
from app.rp.services.config import get_callback_url


router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    path="/callback_url",
    summary="RP Callback URL",
    description="Returns the RP Callback URL for redirection post migration",
)
async def handle_get_callback_url(
    request: Request,
):
    return await get_callback_url(
        rp_client_id=request.session[SessionKeys.RP_CLIENT_ID_KEY.value],
    )
