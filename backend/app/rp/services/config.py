import asyncio
import json
import logging
import os

from fastapi import HTTPException, Request
from httpx import AsyncClient
from pydantic import ValidationError

from app.rp.schemas import RPSchema
from app.utils.redis import get_redis_client


logger = logging.getLogger(__name__)

# Configuration source selection
# Local dev: file (mounted/bundled)
# Deployed: AWS Secrets Manager
APP_ENV = os.getenv("APP_ENV", "local").lower()
CONFIG_FILE_PATH = os.getenv("MIGRATION_RP_CONFIG_PATH", "/app/migration_rp.json")
AWS_SECRET_NAME = os.getenv("MIGRATION_RP_SECRET_NAME")
AWS_REGION = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")

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

        logger.info(f"RP Config {matching_rp_idp}")

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

        if APP_ENV == "local":
            logger.info("Loading migration RP config from local file: %s", CONFIG_FILE_PATH)
            with open(CONFIG_FILE_PATH) as f:
                data = json.load(f)

            if not isinstance(data, list):
                raise ValueError("Local migration RP config file must contain a JSON array (list) of RP objects")

            _CONFIG_JSON_CACHE = data
            return data

        # Non-local environments must use Secrets Manager
        if not AWS_SECRET_NAME:
            raise RuntimeError(
                "Non-local environment requires MIGRATION_RP_SECRET_NAME to be set (AWS Secrets Manager)."
            )

        logger.info("Loading migration RP config from AWS Secrets Manager: %s", AWS_SECRET_NAME)
        secret_payload = await _get_secret_string(AWS_SECRET_NAME)
        data = _parse_config_json(secret_payload)

        _CONFIG_JSON_CACHE = data
        return data

    except Exception as e:
        logger.error(f"Exception Error: {e}")
        raise

async def _get_secret_string(secret_name: str) -> str:
    """Fetch SecretString (or SecretBinary) from AWS Secrets Manager.

    Uses boto3 under the hood and runs the blocking call in a thread.
    """

    def _sync_fetch() -> str:
        try:
            import boto3
            from botocore.exceptions import BotoCoreError, ClientError
        except Exception as e:
            raise RuntimeError(
                "boto3/botocore not available. Add boto3 to requirements.txt or ensure it exists in the runtime image."
            ) from e

        if not AWS_REGION:
            raise RuntimeError(
                "AWS region is not set. Set AWS_REGION or AWS_DEFAULT_REGION in the environment."
            )

        client = boto3.client("secretsmanager", region_name=AWS_REGION)

        try:
            resp = client.get_secret_value(SecretId=secret_name)
        except (BotoCoreError, ClientError) as e:
            raise RuntimeError(f"Failed to read secret '{secret_name}' from Secrets Manager") from e

        secret_string = resp.get("SecretString")
        if secret_string:
            return secret_string

        secret_binary = resp.get("SecretBinary")
        if secret_binary:
            if isinstance(secret_binary, (bytes, bytearray)):
                return secret_binary.decode("utf-8")
            return bytes(secret_binary).decode("utf-8")

        raise RuntimeError(f"Secret '{secret_name}' had no SecretString or SecretBinary")

    return await asyncio.to_thread(_sync_fetch)


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

        rpConfig = {
            "rp_redirect_url": rp.rp_redirect_uri,
            "rp_client_name": rp.rp_client_name,
            "rp_client_name_en": rp.rp_client_name_en,
            "rp_client_name_fr": rp.rp_client_name_fr
        }

        return rpConfig

    except ValidationError as e:
        logger.error(f"Validation Error: {e.json()}")
        raise HTTPException(status_code=422, detail="Request data validation error")
