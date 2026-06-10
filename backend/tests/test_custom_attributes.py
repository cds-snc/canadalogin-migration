from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.users.schemas import CustomAttribute
from app.users.services.custom_attributes import (
    get_attribute_value,
    get_custom_attribute,
    get_user_custom_attributes,
)


def test_get_attribute_value_finds_match():
    attributes = [
        CustomAttribute(name="alpha", values=["1"]),
        CustomAttribute(name="beta", values=["2", "3"]),
    ]
    result = get_attribute_value("beta", attributes)
    assert result == ["2", "3"]


def test_get_attribute_value_returns_none_when_missing():
    attributes = [CustomAttribute(name="alpha", values=["1"])]
    result = get_attribute_value("missing", attributes)
    assert result is None


def test_get_custom_attribute_returns_empty_string_for_none():
    result = get_custom_attribute("alpha", None)
    assert result == ""


def test_get_custom_attribute_returns_empty_string_for_empty_list():
    result = get_custom_attribute("alpha", [])
    assert result == ""


def test_get_custom_attribute_returns_none_when_missing():
    attributes = [CustomAttribute(name="alpha", values=["1"])]
    result = get_custom_attribute("missing", attributes)
    assert result is None


def test_get_custom_attribute_is_case_sensitive():
    attributes = [CustomAttribute(name="Alpha", values=["1"])]
    result = get_custom_attribute("alpha", attributes)
    assert result is None


def test_get_custom_attribute_returns_value_when_present():
    attributes = [
        CustomAttribute(name="alpha", values=["1"]),
        CustomAttribute(name="beta", values=["2", "3"]),
    ]
    result = get_custom_attribute("beta", attributes)
    assert result == ["2", "3"]


@pytest.mark.asyncio
async def test_get_user_custom_attributes_returns_none_when_extension_missing():
    http_client = AsyncMock()
    response = MagicMock(status_code=200)
    response.json.return_value = {"success": True, "message": "ok"}
    http_client.get = AsyncMock(return_value=response)

    with patch(
        "app.users.services.custom_attributes.get_configuration",
        return_value=MagicMock(profile_api_endpoint="https://example.test/profile"),
    ):
        result = await get_user_custom_attributes(http_client, "user-token")

    assert result is None
