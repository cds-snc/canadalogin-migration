import asyncio
import json
import logging
import os

from fastapi import HTTPException, Request
from httpx import AsyncClient
from pydantic import ValidationError

from app.rp.schemas import RPSchema
from app.utils.redis import get_redis_client
from app.config import get_configuration


# Get the desired log level from configuration
config = get_configuration()
log_level_str = config.LOG_LEVEL.upper()

# Convert string level to the logging module's level constant (e.g., "DEBUG" to logging.DEBUG)
log_level = getattr(logging, log_level_str, logging.INFO)

# Apply the configuration
logging.basicConfig(level=log_level)
logger = logging.getLogger(__name__)

CONFIG_ENV_VAR = "RP_MIGRATION_CONFIG"

# Simple in-process cache to avoid hitting disk / Secrets Manager repeatedly (per worker process)
_CONFIG_JSON_CACHE: list | None = None


async def get_config(
    rp_client_id: str,
):
    try:
        data = await get_config_json()

        rp_configs = [RPSchema(**item) for item in data]

        matching_rp_idp = next(
            (rp for rp in rp_configs if rp.rp_client_id == rp_client_id),
            None,
        )

        if not matching_rp_idp:
            raise HTTPException(
                status_code=404, detail="Legacy IdP configuration not found"
            )

        logger.debug(f"RP Config {matching_rp_idp}")

        return matching_rp_idp

    except Exception as e:
        logger.error(f"Exception Error: {e}")
        raise


# load the legacy idp config, from wherever it is stored
async def get_config_json() -> list:
    global _CONFIG_JSON_CACHE

    try:
        # In-process cache (per worker process)
        if _CONFIG_JSON_CACHE is not None:
            return _CONFIG_JSON_CACHE

        env_payload = os.getenv(CONFIG_ENV_VAR)
        if env_payload:
            logger.debug(
                "Loading migration RP config from env var %s (local)",
                CONFIG_ENV_VAR,
            )
            try:
                data = _parse_config_json(env_payload)
            except Exception as e:
                raise ValueError(
                    f"Invalid JSON in {CONFIG_ENV_VAR}. Expected a JSON array (list) of RP objects "
                    "or an object containing a list under one of: rp_configs, data, configs"
                ) from e

            _CONFIG_JSON_CACHE = data
            return data
    except Exception as e:
        logger.error(f"Exception Error: {e}")
        raise


def _parse_config_json(payload: str) -> list:
    """Parse secret/file JSON payload into the list expected by `[RPSchema(**item) for item in data]`."""
    data = json.loads(payload)

    # Expected: a JSON array of RP objects
    if isinstance(data, list):
        return data

    # Tolerate wrapper objects (handy if you ever store metadata alongside the list)
    if isinstance(data, dict):
        for key in ("rp_configs", "data", "configs"):
            maybe = data.get(key)
            if isinstance(maybe, list):
                return maybe

    raise ValueError(
        "Unexpected migration RP config format. Expected a JSON array (list) of RP objects "
        "or an object containing a list under one of: rp_configs, data, configs"
    )


# Fetch and cache legacy IdP metadata in Redis.
async def get_legacy_idp_metadata(request: Request, idp_url: str, ttl: int = 86400):

    redis_client = get_redis_client(request)

    logger.info(f"IDP url: {idp_url}")

    # Return cached metadata if available
    cached = await redis_client.get(idp_url)
    if cached:
        logger.debug("Cached value: %s", cached[:200])  # first 200 chars
        return json.loads(cached.decode("utf-8"))

    # Fetch metadata from legacy IdP
    async with AsyncClient(timeout=20.0) as client:
        resp = await client.get(idp_url)
        resp.raise_for_status()
        metadata = resp.json()

    # Store in Redis with TTL
    await redis_client.set(idp_url, json.dumps(metadata), ex=ttl)
    return metadata


async def get_rp_config_details(
    rp_client_id: str,
):
    try:

        rp = await get_config(rp_client_id)

        rpConfig = {
            "rp_redirect_url": rp.rp_redirect_uri,
            "rp_client_name": rp.rp_client_name,
            "rp_client_name_en": rp.rp_client_name_en,
            "rp_client_name_fr": rp.rp_client_name_fr,
        }

        return rpConfig

    except ValidationError as e:
        logger.error(f"Validation Error: {e.json()}")
        raise HTTPException(status_code=422, detail="Request data validation error")
