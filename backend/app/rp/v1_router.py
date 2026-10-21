import logging
from typing import Literal

from fastapi import APIRouter, Request, Response

from app.constants.session_keys import SessionKeys
from app.rp.services.config import get_rp_config_details
from app.utils.custom_parameters import get_rp_return_parameters_from_session

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    path="/rpConfigDetails",
    summary="RP Configuration Details",
    description="Returns the RP Configuration Details for redirection post migration and display purposes.",
)
async def handle_get_rp_config_details(
    request: Request,
    response: Response,
    lang: Literal["en", "fr"] | None = None,
):
    response.headers["Cache-Control"] = "no-store"
    return_parameters = get_rp_return_parameters_from_session(request)
    if lang is not None:
        return_parameters.update({"lang": lang, "ui_locales": f"{lang}-CA"})

    return await get_rp_config_details(
        rp_client_id=request.session.get(SessionKeys.RP_CLIENT_ID_KEY.value),
        custom_parameters=return_parameters,
        language=return_parameters.get("lang"),
    )
