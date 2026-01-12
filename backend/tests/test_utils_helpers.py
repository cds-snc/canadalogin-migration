import json

from app.utils.helpers import (
    format_error_response,
    generate_error_response,
    string_error_response,
)


def test_generate_error_response_payload():
    response = generate_error_response(status_code=400, message="Bad input")
    assert response.status_code == 400
    body = json.loads(response.body.decode("utf-8"))
    assert body == {"success": False, "message": "Bad input", "data": None}


def test_format_error_response_defaults():
    message = format_error_response({"messageId": "E123"})
    assert message == "E123 - Unknown error"


def test_string_error_response_defaults():
    assert string_error_response() == "Unknown error - "
    assert string_error_response("Oops", "Details") == "Oops - Details"
