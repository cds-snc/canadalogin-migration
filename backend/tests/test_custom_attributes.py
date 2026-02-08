import pytest

from app.users.schemas import CustomAttribute
from app.users.services.custom_attributes import (
    get_attribute_value,
    get_custom_attribute,
)


@pytest.mark.asyncio
async def test_get_attribute_value_finds_match():
    attributes = [
        CustomAttribute(name="alpha", values=["1"]),
        CustomAttribute(name="beta", values=["2", "3"]),
    ]
    result = await get_attribute_value("beta", attributes)
    assert result == ["2", "3"]


@pytest.mark.asyncio
async def test_get_attribute_value_returns_none_when_missing():
    attributes = [CustomAttribute(name="alpha", values=["1"])]
    result = await get_attribute_value("missing", attributes)
    assert result is None


@pytest.mark.asyncio
async def test_get_custom_attribute_returns_empty_string_for_none():
    result = await get_custom_attribute("alpha", None)
    assert result == ""


@pytest.mark.asyncio
async def test_get_custom_attribute_returns_empty_string_for_empty_list():
    result = await get_custom_attribute("alpha", [])
    assert result == ""


@pytest.mark.asyncio
async def test_get_custom_attribute_returns_none_when_missing():
    attributes = [CustomAttribute(name="alpha", values=["1"])]
    result = await get_custom_attribute("missing", attributes)
    assert result is None


@pytest.mark.asyncio
async def test_get_custom_attribute_is_case_sensitive():
    attributes = [CustomAttribute(name="Alpha", values=["1"])]
    result = await get_custom_attribute("alpha", attributes)
    assert result is None


@pytest.mark.asyncio
async def test_get_custom_attribute_returns_value_when_present():
    attributes = [
        CustomAttribute(name="alpha", values=["1"]),
        CustomAttribute(name="beta", values=["2", "3"]),
    ]
    result = await get_custom_attribute("beta", attributes)
    assert result == ["2", "3"]
