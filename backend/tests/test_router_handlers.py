import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.auth import v1_router as auth_router
from app.auth_legacy import v1_router as legacy_router
from app.rp import v1_router as rp_router
from app.constants.session_keys import SessionKeys


@pytest.mark.asyncio
async def test_auth_redirect_url_calls_service():
    request = MagicMock()
    with (
        patch("app.auth.v1_router.set_customparameters_in_session") as mock_set_custom,
        patch(
            "app.auth.v1_router.redirect_user_to_idp_verify",
            new=AsyncMock(return_value="ok"),
        ) as mocked,
    ):
        result = await auth_router.redirect_url(
            request,
            clientId="cid",
            lang="en",
            customparameters="encoded-value",
        )
        assert result == "ok"
        mock_set_custom.assert_called_once_with(request, "encoded-value")
        mocked.assert_awaited_once_with(request, "cid", "en")


@pytest.mark.asyncio
async def test_auth_callback_calls_service():
    request = MagicMock()
    with patch(
        "app.auth.v1_router.callback_handler",
        new=AsyncMock(return_value="cb"),
    ) as mocked:
        result = await auth_router.callback(request, lang="en")
        assert result == "cb"
        mocked.assert_awaited_once()


@pytest.mark.asyncio
async def test_auth_reauth_calls_service():
    request = MagicMock()
    with patch(
        "app.auth.v1_router.reauthenticate_user",
        new=AsyncMock(return_value="reauth"),
    ) as mocked:
        result = await auth_router.reauth(request, returnToPage="/", lang="en")
        assert result == "reauth"
        mocked.assert_awaited_once()


@pytest.mark.asyncio
async def test_auth_logout_calls_service():
    request = MagicMock()
    with patch(
        "app.auth.v1_router.logout_user",
        new=AsyncMock(return_value={"ok": True}),
    ) as mocked:
        result = await auth_router.logout(request, id_token="token")
        assert result == {"ok": True}
        mocked.assert_awaited_once()


@pytest.mark.asyncio
async def test_auth_backchannel_calls_service():
    request = MagicMock()
    with patch(
        "app.auth.v1_router.backchannel_logout",
        new=AsyncMock(return_value={"ok": True}),
    ) as mocked:
        result = await auth_router.handle_backchannel_logout(request)
        assert result == {"ok": True}
        mocked.assert_awaited_once()


@pytest.mark.asyncio
async def test_auth_session_status_calls_service():
    request = MagicMock()
    with patch(
        "app.auth.v1_router.session_event_sse_generator",
        new=AsyncMock(return_value="stream"),
    ) as mocked:
        result = await auth_router.session_status(request)
        assert result == "stream"
        mocked.assert_awaited_once()


@pytest.mark.asyncio
async def test_auth_keep_alive_calls_service():
    request = MagicMock()
    with patch(
        "app.auth.v1_router.session_extend",
        new=AsyncMock(return_value={"ok": True}),
    ) as mocked:
        result = await auth_router.keep_alive(request)
        assert result == {"ok": True}
        mocked.assert_awaited_once()


@pytest.mark.asyncio
async def test_auth_me_calls_service():
    request = MagicMock()
    request.app.state.request_client = MagicMock()
    with patch(
        "app.auth.v1_router.get_my_profile",
        new=AsyncMock(return_value={"ok": True}),
    ) as mocked:
        result = await auth_router.get_current_user_profile(
            request, user_access_token="token"
        )
        assert result == {"ok": True}
        mocked.assert_awaited_once_with(request.app.state.request_client, "token")


@pytest.mark.asyncio
async def test_legacy_login_normalizes_lang_and_calls_service():
    request = MagicMock()
    request.session = {
        SessionKeys.SESSION_USER_TOKEN.value: "token",
        SessionKeys.RP_CLIENT_ID_KEY.value: "rp-1",
    }

    with patch(
        "app.auth_legacy.v1_router.legacy_login",
        new=AsyncMock(return_value="legacy"),
    ) as mocked:
        result = await legacy_router.handle_legacy_login(
            request, lang="ES", user_access_token="user-token"
        )
        assert result == "legacy"
        mocked.assert_awaited_once()


@pytest.mark.asyncio
async def test_legacy_callback_calls_service():
    request = MagicMock()
    request.session = {
        SessionKeys.SESSION_USER_TOKEN.value: "token",
        SessionKeys.RP_CLIENT_ID_KEY.value: "rp-1",
    }

    with patch(
        "app.auth_legacy.v1_router.legacy_callback",
        new=AsyncMock(return_value="cb"),
    ) as mocked:
        result = await legacy_router.handle_legacy_callback(
            request, user_access_token="user-token"
        )
        assert result == "cb"
        mocked.assert_awaited_once()


@pytest.mark.asyncio
async def test_legacy_post_logout_calls_service():
    request = MagicMock()
    with patch(
        "app.auth_legacy.v1_router.legacy_post_logout_callback",
        new=AsyncMock(return_value="logout"),
    ) as mocked:
        result = await legacy_router.handle_legacy_post_logout_callback(
            request, user_access_token="user-token"
        )
        assert result == "logout"
        mocked.assert_awaited_once()


@pytest.mark.asyncio
async def test_legacy_skip_calls_service():
    request = MagicMock()
    request.session = {
        SessionKeys.SESSION_USER_TOKEN.value: "token",
        SessionKeys.RP_CLIENT_ID_KEY.value: "rp-1",
        SessionKeys.CURRENT_LANGUAGE.value: "en",
    }
    with patch(
        "app.auth_legacy.v1_router.skip_account_linking",
        new=AsyncMock(return_value="skip"),
    ) as mocked:
        result = await legacy_router.handle_skip_account_linking(
            request, lang="fr", user_access_token="user-token"
        )
        assert result == "skip"
        assert request.session[SessionKeys.CURRENT_LANGUAGE.value] == "fr"
        mocked.assert_awaited_once_with(
            request,
            "user-token",
            "token",
            rp_client_id="rp-1",
        )


@pytest.mark.asyncio
async def test_rp_config_details_calls_service():
    request = MagicMock()
    request.session = {SessionKeys.RP_CLIENT_ID_KEY.value: "rp-1"}
    with (
        patch(
            "app.rp.v1_router.get_rp_return_parameters_from_session",
            return_value={"foo": "bar"},
        ),
        patch(
            "app.rp.v1_router.get_rp_config_details",
            new=AsyncMock(return_value={"ok": True}),
        ) as mocked,
    ):
        result = await rp_router.handle_get_rp_config_details(request)
        assert result == {"ok": True}
        mocked.assert_awaited_once_with(
            rp_client_id="rp-1",
            custom_parameters={"foo": "bar"},
            language=None,
        )
