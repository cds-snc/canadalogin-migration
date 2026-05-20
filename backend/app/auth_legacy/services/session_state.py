import json
import logging
import hashlib

from fastapi import Request

from app.constants.session_keys import SessionKeys
from app.utils.correlation_id import clear_linking_attempt_id
from app.utils.redis import get_redis_client

logger = logging.getLogger(__name__)

LEGACY_PROVIDER_SESSION_KEY = "legacy_provider"
LEGACY_PROVIDER_KEY_SESSION_KEY = "legacy_provider_key"
LEGACY_CLIENT_NAME_SESSION_KEY = "legacy_client_name"
LEGACY_OIDC_SESSION_SUFFIXES = ("code_verifier", "state", "nonce")
LEGACY_SAML_REQUEST_ID_SESSION_KEY = "legacy_saml_request_id"
LEGACY_SAML_RELAY_STATE_SESSION_KEY = "legacy_saml_relay_state"
LEGACY_SAML_SESSION_INDEX_SESSION_KEY = "legacy_saml_session_index"
LEGACY_SAML_SESSION_KEYS = (
    LEGACY_SAML_REQUEST_ID_SESSION_KEY,
    LEGACY_SAML_RELAY_STATE_SESSION_KEY,
    LEGACY_SAML_SESSION_INDEX_SESSION_KEY,
)
LEGACY_SAML_TRANSACTION_REDIS_PREFIX = "legacy_saml_transaction:"
LEGACY_SAML_TRANSACTION_TTL_SECONDS = 10 * 60


def _legacy_saml_transaction_key(relay_state: str) -> str:
    return f"{LEGACY_SAML_TRANSACTION_REDIS_PREFIX}{relay_state}"


def _trace_hash(value: str | None) -> str | None:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _store_if_present(session: dict, key: str, value: object) -> None:
    if value is not None:
        session[key] = value


async def store_legacy_saml_transaction(
    request: Request,
    *,
    relay_state: str,
    request_id: str,
    rp_client_id: str,
    user_access_token: str,
    session_user_token: object,
    provider_key: str,
    provider_name: str,
    client_name: str,
    lang: str,
    correlation_id: str,
    attempt_id: str,
) -> None:
    payload = {
        "relay_state": relay_state,
        "request_id": request_id,
        "rp_client_id": rp_client_id,
        "user_access_token": user_access_token,
        "session_user_token": session_user_token,
        "provider_key": provider_key,
        "provider_name": provider_name,
        "client_name": client_name,
        "lang": lang,
        "correlation_id": correlation_id,
        "attempt_id": attempt_id,
    }
    redis_client = get_redis_client(request)
    await redis_client.set(
        _legacy_saml_transaction_key(relay_state),
        json.dumps(payload),
        ex=LEGACY_SAML_TRANSACTION_TTL_SECONDS,
    )
    logger.info(
        "Stored legacy SAML transaction: relay_state_sha256=%s; request_id=%s; "
        "rp_client_id_sha256=%s; provider_key=%s; ttl_seconds=%s",
        _trace_hash(relay_state),
        request_id,
        _trace_hash(rp_client_id),
        provider_key,
        LEGACY_SAML_TRANSACTION_TTL_SECONDS,
    )


async def pop_legacy_saml_transaction(
    request: Request, relay_state: str | None
) -> dict | None:
    if not relay_state:
        return None

    redis_client = get_redis_client(request)
    cache_key = _legacy_saml_transaction_key(relay_state)
    raw_payload = await redis_client.get(cache_key)
    if not raw_payload:
        logger.info(
            "Legacy SAML transaction not found: relay_state_sha256=%s",
            _trace_hash(relay_state),
        )
        return None

    await redis_client.delete(cache_key)
    if isinstance(raw_payload, bytes):
        raw_payload = raw_payload.decode("utf-8")

    try:
        payload = json.loads(raw_payload)
    except (TypeError, ValueError):
        logger.warning("Invalid legacy SAML transaction payload in Redis")
        return None

    if not isinstance(payload, dict):
        logger.warning("Legacy SAML transaction payload is not an object")
        return None

    logger.info(
        "Loaded legacy SAML transaction: relay_state_sha256=%s; request_id=%s; "
        "rp_client_id_sha256=%s; provider_key=%s",
        _trace_hash(relay_state),
        payload.get("request_id"),
        _trace_hash(payload.get("rp_client_id")),
        payload.get("provider_key"),
    )
    return payload


def hydrate_legacy_saml_transaction_session(
    request: Request, transaction: dict | None
) -> None:
    if not transaction:
        return

    _store_if_present(
        request.session,
        SessionKeys.RP_CLIENT_ID_KEY.value,
        transaction.get("rp_client_id"),
    )
    _store_if_present(
        request.session,
        SessionKeys.SESSION_USER_ACCESS_TOKEN_KEY.value,
        transaction.get("user_access_token"),
    )
    _store_if_present(
        request.session,
        SessionKeys.SESSION_USER_TOKEN.value,
        transaction.get("session_user_token"),
    )
    _store_if_present(
        request.session,
        SessionKeys.CURRENT_LANGUAGE.value,
        transaction.get("lang"),
    )
    _store_if_present(
        request.session,
        SessionKeys.CORRELATION_ID.value,
        transaction.get("correlation_id"),
    )
    _store_if_present(
        request.session,
        SessionKeys.LEGACY_LINKING_ATTEMPT_ID.value,
        transaction.get("attempt_id"),
    )
    _store_if_present(
        request.session,
        LEGACY_PROVIDER_SESSION_KEY,
        transaction.get("provider_name"),
    )
    _store_if_present(
        request.session,
        LEGACY_PROVIDER_KEY_SESSION_KEY,
        transaction.get("provider_key"),
    )
    _store_if_present(
        request.session,
        LEGACY_CLIENT_NAME_SESSION_KEY,
        transaction.get("client_name"),
    )
    _store_if_present(
        request.session,
        LEGACY_SAML_REQUEST_ID_SESSION_KEY,
        transaction.get("request_id"),
    )
    _store_if_present(
        request.session,
        LEGACY_SAML_RELAY_STATE_SESSION_KEY,
        transaction.get("relay_state"),
    )


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
    request.session.pop(LEGACY_PROVIDER_KEY_SESSION_KEY, None)
    request.session.pop(LEGACY_CLIENT_NAME_SESSION_KEY, None)
    for session_key in LEGACY_SAML_SESSION_KEYS:
        request.session.pop(session_key, None)

    if clear_attempt_id:
        clear_linking_attempt_id(request)
