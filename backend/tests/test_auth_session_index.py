from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from redis.exceptions import ConnectionError, TimeoutError

from app.auth.services.auth_session_index import (
    OIDC_SESSION_INDEX_TTL_SECONDS,
    associate_oidc_session,
    get_oidc_session_index_key,
)
from app.utils.recovery_errors import RecoveryError


def build_request(redis_client):
    return SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(redis_client=redis_client))
    )


@pytest.mark.asyncio
async def test_associate_oidc_session_preserves_siblings_and_refreshes_expiration():
    redis_client = MagicMock(sadd=AsyncMock(), expire=AsyncMock())
    request = build_request(redis_client)

    await associate_oidc_session(request, "private-provider-sid", "app-session-1")
    await associate_oidc_session(request, "private-provider-sid", "app-session-2")

    index_key = get_oidc_session_index_key("private-provider-sid")
    assert "private-provider-sid" not in index_key
    assert redis_client.sadd.await_args_list[0].args == (index_key, "app-session-1")
    assert redis_client.sadd.await_args_list[1].args == (index_key, "app-session-2")
    assert redis_client.expire.await_count == 2
    assert all(
        args.args == (index_key, OIDC_SESSION_INDEX_TTL_SECONDS)
        for args in redis_client.expire.await_args_list
    )
    assert OIDC_SESSION_INDEX_TTL_SECONDS == 12 * 60 * 60


@pytest.mark.asyncio
async def test_association_without_redis_returns_service_unavailable():
    request = build_request(None)

    with pytest.raises(RecoveryError) as raised:
        await associate_oidc_session(request, "sid", "app-session")

    assert raised.value.code == "service-unavailable"
    assert raised.value.status_code == 503


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["sadd", "expire"])
@pytest.mark.parametrize("error_type", [ConnectionError, TimeoutError])
async def test_association_redis_failures_return_service_unavailable(
    operation, error_type
):
    redis_client = MagicMock(sadd=AsyncMock(), expire=AsyncMock())
    getattr(redis_client, operation).side_effect = error_type("Redis unavailable")
    request = build_request(redis_client)

    with pytest.raises(RecoveryError) as raised:
        await associate_oidc_session(request, "sid", "app-session")

    assert raised.value.code == "service-unavailable"
    assert raised.value.status_code == 503
