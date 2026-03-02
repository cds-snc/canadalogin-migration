from app.main import app


def test_main_registers_auth_me_and_no_users_routes():
    route_paths = {route.path for route in app.routes if hasattr(route, "path")}

    assert "/v1/auth/me" in route_paths
    assert "/v1/users/profile" not in route_paths
    assert "/v1/users/ibmid" not in route_paths
    assert "/v1/users/customAttributes" not in route_paths
