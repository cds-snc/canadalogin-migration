import hashlib
import json
import logging
from typing import Any

from app.utils.correlation_id import get_attempt_id, get_correlation_id

AUTH_FLOW_CODE = "GCAuth.Migration.INFO.AUTH_FLOW"


def hash_identifier(value: str | None) -> str | None:
    if not value:
        return None
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def _filter_none_values(values: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}


def log_auth_flow_event(
    logger: logging.Logger,
    *,
    flow: str,
    step: str,
    outcome: str,
    rp_client_id: str | None = None,
    user_id: str | None = None,
    **extra_context: Any,
) -> None:
    context = _filter_none_values(
        {
            "correlation_id": get_correlation_id(),
            "attempt_id": get_attempt_id(),
            "rp_client_id_hash": hash_identifier(rp_client_id),
            "user_id_hash": hash_identifier(user_id),
            **extra_context,
        }
    )

    logger.info(
        json.dumps(
            {
                "code": AUTH_FLOW_CODE,
                "event": "auth_flow",
                "flow": flow,
                "step": step,
                "outcome": outcome,
                "context": context,
            }
        )
    )
