from fastapi import Request

from app.utils.correlation_id import clear_linking_attempt_id

LEGACY_PROVIDER_SESSION_KEY = "legacy_provider"
LEGACY_CLIENT_NAME_SESSION_KEY = "legacy_client_name"
LEGACY_OIDC_SESSION_SUFFIXES = ("code_verifier", "state", "nonce")


def get_legacy_client_name(request: Request) -> str | None:
    client_name = request.session.get(LEGACY_CLIENT_NAME_SESSION_KEY)
    if isinstance(client_name, str) and client_name:
        return client_name
    return None


def clear_legacy_oidc_session(
    request: Request,
    *,
    clear_attempt_id: bool = False,
    client_name: str | None = None,
) -> None:
    client_name = client_name or get_legacy_client_name(request)
    state_value = None

    if client_name:
        for suffix in LEGACY_OIDC_SESSION_SUFFIXES:
            session_key = f"{client_name}_{suffix}"
            value = request.session.pop(session_key, None)
            if suffix == "state" and isinstance(value, str) and value:
                state_value = value

        if state_value:
            request.session.pop(f"_state_{client_name}_{state_value}", None)

    request.session.pop(LEGACY_PROVIDER_SESSION_KEY, None)
    request.session.pop(LEGACY_CLIENT_NAME_SESSION_KEY, None)

    if clear_attempt_id:
        clear_linking_attempt_id(request)
