import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from authlib.integrations.starlette_client import OAuthError
from fastapi.responses import JSONResponse

from app.main import oauth_error_handler
from app.constants.session_keys import SessionKeys


def build_request(accept: str = "text/html"):
    request = MagicMock()
    request.headers = {"accept": accept}
    request.session = {}
    request.query_params = {}
    request.url = MagicMock(path="/v1/auth/legacy/callback")
    return request


@pytest.mark.asyncio
async def test_oauth_error_handler_redirects_using_session_values():
    request = build_request()
    request.session[SessionKeys.RP_CLIENT_ID_KEY.value] = "rp-from-session"
    request.session[SessionKeys.CURRENT_LANGUAGE.value] = "fr"

    with patch(
        "app.main.redirect_user_to_idp_verify",
        new=AsyncMock(return_value="redirected"),
    ) as mock_redirect:
        result = await oauth_error_handler(request, OAuthError("bad"))

    assert result == "redirected"
    mock_redirect.assert_awaited_once_with(request, "rp-from-session", "fr")


@pytest.mark.asyncio
async def test_oauth_error_handler_uses_query_params_and_normalizes_lang():
    request = build_request()
    request.query_params = {
        SessionKeys.RP_CLIENT_ID_KEY.value: "rp-from-query",
        "lang": "es",
    }

    with patch(
        "app.main.redirect_user_to_idp_verify",
        new=AsyncMock(return_value="redirected"),
    ) as mock_redirect:
        result = await oauth_error_handler(request, OAuthError("bad"))

    assert result == "redirected"
    mock_redirect.assert_awaited_once_with(request, "rp-from-query", "en")


@pytest.mark.asyncio
async def test_oauth_error_handler_returns_401_when_client_id_missing():
    request = build_request()

    result = await oauth_error_handler(request, OAuthError("bad"))

    assert isinstance(result, JSONResponse)
    assert result.status_code == 401


@pytest.mark.asyncio
async def test_oauth_error_handler_returns_401_for_json_clients():
    request = build_request(accept="application/json")

    result = await oauth_error_handler(request, OAuthError("bad"))

    assert isinstance(result, JSONResponse)
    assert result.status_code == 401
