import logging

from contextvars import ContextVar, Token
from fastapi import Request
from uuid import uuid4

from app.constants.session_keys import SessionKeys

_correlation_id_context: ContextVar[str | None] = ContextVar(
    "correlation_id", default=None
)
_attempt_id_context: ContextVar[str | None] = ContextVar("attempt_id", default=None)


def bind_correlation_id(correlation_id: str | None) -> Token:
    return _correlation_id_context.set(correlation_id)


def reset_correlation_id(token: Token) -> None:
    _correlation_id_context.reset(token)


def get_correlation_id() -> str | None:
    return _correlation_id_context.get()


def bind_attempt_id(attempt_id: str | None) -> Token:
    return _attempt_id_context.set(attempt_id)


def reset_attempt_id(token: Token) -> None:
    _attempt_id_context.reset(token)


def get_attempt_id() -> str | None:
    return _attempt_id_context.get()


def get_request_correlation_id(request: Request) -> str | None:
    correlation_id = getattr(getattr(request, "state", None), "correlation_id", None)
    if isinstance(correlation_id, str) and correlation_id:
        return correlation_id

    return None


def get_request_attempt_id(request: Request) -> str | None:
    attempt_id = getattr(getattr(request, "state", None), "attempt_id", None)
    if isinstance(attempt_id, str) and attempt_id:
        return attempt_id

    return None


def _get_session_value(request: Request, key: str) -> str | None:
    try:
        value = request.session.get(key)
    except Exception:
        return None

    if isinstance(value, str) and value:
        return value

    return None


def _store_request_correlation_id(request: Request, correlation_id: str) -> str:
    request.state.correlation_id = correlation_id
    bind_correlation_id(correlation_id)
    return correlation_id


def _store_request_attempt_id(request: Request, attempt_id: str) -> str:
    request.state.attempt_id = attempt_id
    bind_attempt_id(attempt_id)
    return attempt_id


def bind_session_correlation_id(request: Request) -> str | None:
    correlation_id = get_request_correlation_id(request)
    if correlation_id:
        bind_correlation_id(correlation_id)
        return correlation_id

    correlation_id = _get_session_value(request, SessionKeys.CORRELATION_ID.value)
    if not correlation_id:
        return None

    return _store_request_correlation_id(request, correlation_id)


def ensure_session_correlation_id(request: Request) -> str:
    correlation_id = bind_session_correlation_id(request)
    if correlation_id:
        return correlation_id

    correlation_id = str(uuid4())
    request.session[SessionKeys.CORRELATION_ID.value] = correlation_id
    return _store_request_correlation_id(request, correlation_id)


def bind_linking_attempt_id(request: Request) -> str | None:
    attempt_id = get_request_attempt_id(request)
    if attempt_id:
        bind_attempt_id(attempt_id)
        return attempt_id

    attempt_id = _get_session_value(
        request, SessionKeys.LEGACY_LINKING_ATTEMPT_ID.value
    )
    if not attempt_id:
        return None

    return _store_request_attempt_id(request, attempt_id)


def start_linking_attempt_id(request: Request) -> str:
    attempt_id = str(uuid4())
    request.session[SessionKeys.LEGACY_LINKING_ATTEMPT_ID.value] = attempt_id
    return _store_request_attempt_id(request, attempt_id)


def ensure_linking_attempt_id(request: Request) -> str:
    attempt_id = bind_linking_attempt_id(request)
    if attempt_id:
        return attempt_id

    return start_linking_attempt_id(request)


def clear_linking_attempt_id(request: Request) -> None:
    request.session.pop(SessionKeys.LEGACY_LINKING_ATTEMPT_ID.value, None)


class CorrelationIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = get_correlation_id() or "-"
        record.attempt_id = get_attempt_id() or "-"
        return True
