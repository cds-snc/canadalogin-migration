import json
import logging
import os

from fastapi import HTTPException, Request
from httpx import AsyncClient
from pydantic import ValidationError

from app.rp.schemas import LegacyIdpSecretSchema, RPConfigSourceSchema, RPSchema
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
CONFIG_SECRETS_ENV_VAR = "RP_MIGRATION_CONFIG_SECRETS"
LIST_WRAPPER_KEYS = ("rp_configs", "data", "configs")
SECRETS_LIST_WRAPPER_KEYS = ("idp_secrets", "secrets", "data", "configs")

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
        if not env_payload:
            raise ValueError(
                f"Missing required configuration: {CONFIG_ENV_VAR} is not set or empty"
            )

        logger.debug(
            "Loading migration RP config from env var %s (local)",
            CONFIG_ENV_VAR,
        )
        try:
            source_data = _parse_config_json(env_payload)
        except Exception as e:
            raise ValueError(
                f"Invalid JSON in {CONFIG_ENV_VAR}. Expected a JSON array (list) of RP objects "
                "or an object containing a list under one of: rp_configs, data, configs"
            ) from e

        normalized_source = [
            RPConfigSourceSchema.model_validate(item).model_dump(
                by_alias=True, exclude_none=True
            )
            for item in source_data
        ]
        secrets_by_client_id = _load_idp_secrets_by_client_id()
        merged = _merge_config_with_secrets(normalized_source, secrets_by_client_id)

        _CONFIG_JSON_CACHE = merged
        return merged
    except Exception as e:
        logger.error(f"Exception Error: {e}")
        raise


def _parse_config_json(payload: str) -> list:
    """Parse RP config JSON payload into a list of RP objects."""
    data = json.loads(payload)

    # Expected: a JSON array of RP objects
    if isinstance(data, list):
        return data

    # Tolerate wrapper objects (handy if you ever store metadata alongside the list)
    if isinstance(data, dict):
        for key in LIST_WRAPPER_KEYS:
            maybe = data.get(key)
            if isinstance(maybe, list):
                return maybe

    raise ValueError(
        "Unexpected migration RP config format. Expected a JSON array (list) of RP objects "
        f"or an object containing a list under one of: {', '.join(LIST_WRAPPER_KEYS)}"
    )


def _parse_secrets_json(payload: str) -> list:
    """Parse RP config secrets JSON payload into a list of secret objects."""
    data = json.loads(payload)

    # Expected: a JSON array of secret objects
    if isinstance(data, list):
        return data

    # Tolerate wrapper objects for secret payloads
    if isinstance(data, dict):
        for key in SECRETS_LIST_WRAPPER_KEYS:
            maybe = data.get(key)
            if isinstance(maybe, list):
                return maybe

    raise ValueError(
        "Unexpected migration RP secrets format. Expected a JSON array (list) of secret objects "
        "or an object containing a list under one of: "
        f"{', '.join(SECRETS_LIST_WRAPPER_KEYS)}"
    )


def _load_idp_secrets_by_client_id() -> dict[str, str]:
    env_payload = os.getenv(CONFIG_SECRETS_ENV_VAR)
    if not env_payload:
        return {}

    try:
        parsed = _parse_secrets_json(env_payload)
    except Exception as e:
        raise ValueError(
            f"Invalid JSON in {CONFIG_SECRETS_ENV_VAR}. Expected a JSON array of "
            "objects with {client_id, client_secret}, or an object with such a list under "
            f"one of: {', '.join(SECRETS_LIST_WRAPPER_KEYS)}"
        ) from e

    secrets_by_client_id: dict[str, str] = {}
    for item in parsed:
        entry = LegacyIdpSecretSchema.model_validate(item)
        if entry.client_id in secrets_by_client_id:
            raise ValueError(
                f"Duplicate client_id in {CONFIG_SECRETS_ENV_VAR}: {entry.client_id}"
            )
        secrets_by_client_id[entry.client_id] = entry.client_secret

    return secrets_by_client_id


def _merge_config_with_secrets(
    config_data: list, secrets_by_client_id: dict[str, str]
) -> list:
    merged: list = []
    referenced_client_ids: set[str] = set()
    missing_secret_client_ids: set[str] = set()

    for rp in config_data:
        rp_copy = dict(rp)
        merged_idps = []
        for idp in rp_copy.get("IDP", []):
            idp_copy = dict(idp)
            client_id = idp_copy.get("client_id")

            if client_id:
                referenced_client_ids.add(client_id)
                secret_from_env = secrets_by_client_id.get(client_id)
                if secret_from_env:
                    idp_copy["client_secret"] = secret_from_env

            if not idp_copy.get("client_secret"):
                missing_secret_client_ids.add(client_id or "<missing-client-id>")

            merged_idps.append(idp_copy)

        rp_copy["IDP"] = merged_idps
        merged.append(rp_copy)

    if missing_secret_client_ids:
        missing_ids = ", ".join(sorted(missing_secret_client_ids))
        raise ValueError(
            "Missing legacy IDP client_secret for client_id(s): "
            f"{missing_ids}. Provide {CONFIG_SECRETS_ENV_VAR} entries keyed by client_id "
            f"or include inline client_secret in {CONFIG_ENV_VAR}."
        )

    return merged


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
        normalized_acr_values = {
            value.strip().lower()
            for value in (rp.acr_values or "").split(",")
            if value.strip()
        }
        is_gckey_only = "gckey" in normalized_acr_values

        rpConfig = {
            "rp_redirect_url": rp.rp_redirect_uri,
            "rp_client_name": rp.rp_client_name,
            "rp_client_name_en": rp.rp_client_name_en,
            "rp_client_name_fr": rp.rp_client_name_fr,
            "acr_values": rp.acr_values,
            "is_gckey_only": is_gckey_only,
        }

        return rpConfig

    except ValidationError as e:
        logger.error(f"Validation Error: {e.json()}")
        raise HTTPException(status_code=422, detail="Request data validation error")
