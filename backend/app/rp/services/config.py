import json
import logging

from fastapi import HTTPException, Request
from httpx import AsyncClient
from pydantic import ValidationError

from app.rp.schemas import RPSchema
from app.utils.redis import get_redis_client


logger = logging.getLogger(__name__)


async def get_config(
    rp_client_id: str,
):
    try:

        with open("/app/migration_rp.json") as f:
            data = json.load(f)

        rp_configs = [RPSchema(**item) for item in data]

        matching_rp_idp = next(
            (rp for rp in rp_configs if rp.rp_client_id == rp_client_id),
            None,
        )

        if not matching_rp_idp:
            raise HTTPException(
                status_code=404, detail="Legacy IdP configuration not found"
            )

        logger.info(f"RP Config {matching_rp_idp}")

        return matching_rp_idp

    except Exception as e:
        logger.error(f"Exception Error: {e}")
        raise


# Fetch and cache legacy IdP metadata in Redis.
async def get_legacy_idp_metadata(request: Request, idp_url: str, ttl: int = 86400):

    redis_client = get_redis_client(request)

    logger.info(f"IDP url: {idp_url}")

    # Return cached metadata if available
    cached = await redis_client.get(idp_url)
    if cached:
        logger.info("Cached value: %s", cached[:200])  # first 200 chars
        return json.loads(cached.decode("utf-8"))

    # Fetch metadata from legacy IdP
    async with AsyncClient(timeout=20.0) as client:
        resp = await client.get(idp_url)
        resp.raise_for_status()
        metadata = resp.json()

    # Store in Redis with TTL
    await redis_client.set(idp_url, json.dumps(metadata), ex=ttl)
    return metadata


async def get_callback_url(
    rp_client_id: str,
):
    try:

        rp = await get_config(rp_client_id)

        return rp.rp_redirect_uri

    except ValidationError as e:
        logger.error(f"Validation Error: {e.json()}")
        raise HTTPException(status_code=422, detail="Request data validation error")
