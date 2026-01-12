import pytest
import httpx
from fastapi import HTTPException
from pydantic import BaseModel, ValidationError
from authlib.integrations.starlette_client import OAuthError

from app.utils.request_error_handler import RequestErrorHandler


def build_http_status_error(status_code, json_body):
    request = httpx.Request("GET", "https://example.test/resource")
    response = httpx.Response(status_code, json=json_body, request=request)
    return httpx.HTTPStatusError("error", request=request, response=response)


def test_handle_http_400_uses_message_id():
    exc = build_http_status_error(400, {"messageId": "bad_input"})
    with pytest.raises(HTTPException) as raised:
        RequestErrorHandler.handle(exc, context="test")
    assert raised.value.status_code == 400
    assert raised.value.detail == "bad_input"


def test_handle_http_429_returns_too_many_requests():
    exc = build_http_status_error(429, {"messageId": "throttle"})
    with pytest.raises(HTTPException) as raised:
        RequestErrorHandler.handle(exc, context="test")
    assert raised.value.status_code == 429
    assert raised.value.detail == "throttle"


def test_handle_http_401_raises_oauth_error():
    exc = build_http_status_error(401, {"messageId": "invalid"})
    with pytest.raises(OAuthError):
        RequestErrorHandler.handle(exc, context="test")


def test_handle_timeout_exception():
    exc = httpx.TimeoutException("timeout")
    with pytest.raises(HTTPException) as raised:
        RequestErrorHandler.handle(exc, context="test")
    assert raised.value.status_code == 504


def test_handle_validation_error():
    class ExampleModel(BaseModel):
        value: int

    with pytest.raises(ValidationError) as validation_error:
        ExampleModel(value="not-an-int")

    with pytest.raises(HTTPException) as raised:
        RequestErrorHandler.handle(validation_error.value, context="test")
    assert raised.value.status_code == 422


def test_handle_existing_http_exception_passthrough():
    exc = HTTPException(status_code=418, detail="teapot")
    with pytest.raises(HTTPException) as raised:
        RequestErrorHandler.handle(exc, context="test")
    assert raised.value.status_code == 418
