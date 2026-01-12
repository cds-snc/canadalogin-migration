from app.utils.access_token import get_auth_request_headers


def test_get_auth_request_headers_scim_defaults():
    headers = get_auth_request_headers("token123")
    assert headers["Authorization"] == "Bearer token123"
    assert headers["Content-Type"] == "application/scim+json"
    assert headers["Accept"] == "application/scim+json"


def test_get_auth_request_headers_json():
    headers = get_auth_request_headers("token123", json_content_type=True)
    assert headers["Authorization"] == "Bearer token123"
    assert headers["Content-Type"] == "application/json"
    assert headers["Accept"] == "application/json"
