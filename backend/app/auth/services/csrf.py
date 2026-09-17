"""Session-bound synchronizer tokens for browser requests that change state."""

import secrets

from fastapi import HTTPException, Request
from starsessions.session import get_session_handler, load_session

from app.config import get_configuration
from app.constants.session_keys import SessionKeys

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})
CSRF_HEADER = "X-CSRF-Token"


def rotate_csrf_token(request: Request) -> str:
    """Replace the token when a fresh authenticated session is established."""
    token = secrets.token_urlsafe(32)
    request.session[SessionKeys.CSRF_TOKEN.value] = token
    return token


async def get_or_create_csrf_token(request: Request) -> str:
    # Loading is idempotent and also initializes sessions without a cookie.
    await load_session(request)
    token = request.session.get(SessionKeys.CSRF_TOKEN.value)
    if not isinstance(token, str) or not token:
        token = rotate_csrf_token(request)
    return token


async def validate_csrf_token(request: Request) -> None:
    """Run before route dependencies so rejected requests cannot change state."""
    if request.method in SAFE_METHODS:
        return

    # This server-to-server OIDC endpoint verifies a signed logout token itself.
    backchannel_path = f"{get_configuration().V1_API_VERSION}/auth/backchannel-logout"
    if request.method == "POST" and request.url.path == backchannel_path:
        return

    await load_session(request)
    expected = request.session.get(SessionKeys.CSRF_TOKEN.value)
    supplied = request.headers.get(CSRF_HEADER)
    if (
        not isinstance(expected, str)
        or not expected
        or not supplied
        or not secrets.compare_digest(expected.encode(), supplied.encode())
    ):
        # Logging must not try to refresh authentication on a rejected request.
        request.state.csrf_rejected = True
        # starsessions 2.2.1 saves every loaded session, even on errors. Suppress
        # that save so a forged request cannot roll the session's expiry.
        get_session_handler(request).is_loaded = False
        raise HTTPException(status_code=403, detail="Missing or invalid CSRF token")
