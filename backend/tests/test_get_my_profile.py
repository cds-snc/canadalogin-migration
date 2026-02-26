import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch
from authlib.integrations.starlette_client import OAuthError
from fastapi import HTTPException

from app.users.services.get_my_profile import (
    dispatch_get_my_profile_from_ibm,
    get_my_profile,
)
from app.users.schemas import ProfileResponse, IBMVerifyUserProfileSchema


def _valid_profile_json():
    return {
        "emails": [],
        "meta": {
            "created": "2024-01-01T00:00:00Z",
            "location": "https://example.test/users/1",
            "lastModified": "2024-01-01T00:00:00Z",
            "resourceType": "User",
        },
        "active": True,
        "id": "user-1",
        "userName": "user@example.com",
    }


@pytest.mark.asyncio
async def test_dispatch_get_my_profile_returns_schema():
    http_client = AsyncMock()
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json = MagicMock(return_value=_valid_profile_json())
    http_client.get = AsyncMock(return_value=response)

    result = await dispatch_get_my_profile_from_ibm(http_client, "user-token")

    assert isinstance(result, IBMVerifyUserProfileSchema)
    assert result.userName == "user@example.com"


@pytest.mark.asyncio
async def test_dispatch_get_my_profile_raises_oauth_error_on_401():
    http_client = AsyncMock()
    request = httpx.Request("GET", "https://example.test/profile")
    response = httpx.Response(401, request=request)
    error = httpx.HTTPStatusError("unauthorized", request=request, response=response)

    http_client.get = AsyncMock(
        return_value=MagicMock(raise_for_status=MagicMock(side_effect=error))
    )

    with pytest.raises(OAuthError):
        await dispatch_get_my_profile_from_ibm(http_client, "user-token")


@pytest.mark.asyncio
async def test_dispatch_get_my_profile_raises_http_exception_on_500():
    http_client = AsyncMock()
    request = httpx.Request("GET", "https://example.test/profile")
    response = httpx.Response(500, request=request)
    error = httpx.HTTPStatusError("server error", request=request, response=response)

    http_client.get = AsyncMock(
        return_value=MagicMock(raise_for_status=MagicMock(side_effect=error))
    )

    with pytest.raises(HTTPException) as raised:
        await dispatch_get_my_profile_from_ibm(http_client, "user-token")

    assert raised.value.status_code == 500


@pytest.mark.asyncio
async def test_get_my_profile_returns_profile_response():
    http_client = AsyncMock()
    profile = IBMVerifyUserProfileSchema(**_valid_profile_json())

    with patch(
        "app.users.services.get_my_profile.dispatch_get_my_profile_from_ibm",
        new=AsyncMock(return_value=profile),
    ):
        result = await get_my_profile(http_client, "user-token")

    assert isinstance(result, ProfileResponse)
    assert result.success is True
    assert result.data.userName == "user@example.com"


@pytest.mark.asyncio
async def test_get_my_profile_raises_on_invalid_profile_data():
    http_client = AsyncMock()
    bad_profile = MagicMock()
    bad_profile.model_dump = MagicMock(return_value={"id": "only-id"})

    with patch(
        "app.users.services.get_my_profile.dispatch_get_my_profile_from_ibm",
        new=AsyncMock(return_value=bad_profile),
    ):
        with pytest.raises(HTTPException) as raised:
            await get_my_profile(http_client, "user-token")

    assert raised.value.status_code == 422
