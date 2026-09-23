"""Responses that let the frontend offer a safe way to restart migration."""

import logging

from authlib.integrations.starlette_client import OAuthError
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from redis.exceptions import ConnectionError, TimeoutError
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import get_configuration
from app.constants.session_keys import SessionKeys
from app.auth.schemas import SSEventData

logger = logging.getLogger(__name__)

RECOVERY_ERRORS = {
    "missing-rp-context": (400, "Missing RP client id"),
    "session-ended": (401, "Your session has ended. Start again from your service."),
    "service-unavailable": (503, "The service is temporarily unavailable."),
}


class RecoveryError(HTTPException):
    def __init__(self, code: str):
        status_code, message = RECOVERY_ERRORS[code]
        super().__init__(status_code=status_code, detail=message)
        self.code = code


class SessionEndedError(OAuthError):
    """A protected request has no usable authenticated session."""


class AuthenticationRequiredError(OAuthError):
    """A new entry from a service needs its initial Verify authentication."""


def recovery_response(request: Request, code: str):
    status_code, message = RECOVERY_ERRORS[code]
    # Browser redirects and SSE recovery events use 303/200 on the wire. Keep
    # the underlying error visible in logs independently of that response.
    logger.log(
        logging.ERROR if status_code >= 500 else logging.WARNING,
        "Migration recovery: code=%s status=%s method=%s path=%s",
        code,
        status_code,
        request.method,
        request.url.path,
    )
    headers = {"Cache-Control": "no-store"}
    accept = request.headers.get("accept", "")
    config = get_configuration()
    if (
        "text/event-stream" in accept
        and request.url.path == f"{config.V1_API_VERSION}/auth/session-status"
    ):
        # EventSource does not expose bodies of HTTP error responses. Deliver
        # the application error as one readable event before ending the stream.
        event = SSEventData(status="error", error=message, code=code)
        return Response(
            content=f"event: error\ndata: {event.model_dump_json()}\n\n",
            status_code=200,
            media_type="text/event-stream",
            headers={**headers, "X-Accel-Buffering": "no"},
        )
    if "text/html" in accept and "application/json" not in accept:
        # Accept dict subclasses without touching starsessions' unloaded LoadGuard.
        session = request.scope.get("session")
        session_language = (
            session.get(SessionKeys.CURRENT_LANGUAGE.value)
            if issubclass(type(session), dict)
            else None
        )
        language = request.query_params.get("lang") or session_language or "en"
        language = language.lower() if isinstance(language, str) else "en"
        if language not in ("en", "fr"):
            language = "en"
        base_url = config.MIGRATION_SOLUTION_DOMAIN.rstrip("/")
        if config.ENVIRONMENT != "local":
            base_url = f"https://{base_url}"
        return RedirectResponse(
            f"{base_url}/{language}/error/{code}", status_code=303, headers=headers
        )
    return JSONResponse(
        status_code=status_code,
        content={"success": False, "message": message, "code": code},
        headers=headers,
    )


class SessionStoreErrorMiddleware:
    """Catch Redis failures during session loading and response persistence."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        response_started = False

        async def track_response(message: Message):
            # This closure tracks one request; no state is shared across requests.
            nonlocal response_started  # nosemgrep: no-mutable-module-global
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, track_response)
        except (ConnectionError, TimeoutError):
            logger.exception("Redis unavailable while handling session")
            if response_started:
                # Streaming responses must handle errors within their iterator.
                raise
            response = recovery_response(Request(scope), "service-unavailable")
            await response(scope, receive, send)
