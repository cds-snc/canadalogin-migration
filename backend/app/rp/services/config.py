import json
import logging

from fastapi import HTTPException, Request
from httpx import AsyncClient
from pydantic import ValidationError

from app.rp.schemas import RPSchema, LegacyIdpSchema
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


async def get_config(
    rp_client_id: str,
) -> RPSchema:
    """
    Get RP configuration from environment variables.
    This replaces the previous JSON file-based configuration.
    Supports multiple Legacy IDPs via JSON array in LEGACY_IDP_CONFIGS.
    """
    try:
        config = get_configuration()

        # Validate that the requested RP client ID matches the configured one
        if config.rp_config.RP_CLIENT_ID != rp_client_id:
            raise HTTPException(
                status_code=404,
                detail=f"RP configuration not found for client_id: {rp_client_id}",
            )

        # Build the list of Legacy IDP configurations from the JSON array
        idp_configs = config.legacy_idp_config.idp_configs_list
        legacy_idps = [
            LegacyIdpSchema(
                client_id=idp["client_id"],
                client_name=idp["client_name"],
                client_secret=idp["client_secret"],
                openid_configuration=idp["openid_configuration"],
                redirect_uris=idp["redirect_uris"],
                scope=idp.get("scope", "openid profile email"),
                max_age=idp.get("max_age", 3600),
                code_challenge_method=idp.get("code_challenge_method", "S256"),
            )
            for idp in idp_configs
        ]

        # Validate that at least one IDP is configured
        if not legacy_idps:
            raise HTTPException(
                status_code=500,
                detail="No Legacy IDP configurations found. Please set LEGACY_IDP_0_CLIENT_ID and related environment variables.",
            )

        # Build the RP configuration
        rp_config = RPSchema(
            rp_client_id=config.rp_config.RP_CLIENT_ID,
            rp_client_name=config.rp_config.RP_CLIENT_NAME,
            rp_client_name_en=config.rp_config.RP_CLIENT_NAME_EN,
            rp_client_name_fr=config.rp_config.RP_CLIENT_NAME_FR,
            rp_redirect_uri=config.rp_config.RP_REDIRECT_URI,
            IDP=legacy_idps,
        )

        logger.debug(f"RP Config {rp_config}")

        return rp_config

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Exception Error: {e}")
        raise HTTPException(status_code=500, detail="Failed to load RP configuration")


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
    """
    Get RP configuration details.
    Returns a dictionary with RP redirect URL and client names.
    """
    try:
        rp = await get_config(rp_client_id)

        rp_config = {
            "rp_redirect_url": rp.rp_redirect_uri,
            "rp_client_name": rp.rp_client_name,
            "rp_client_name_en": rp.rp_client_name_en,
            "rp_client_name_fr": rp.rp_client_name_fr,
        }

        return rp_config

    except HTTPException:
        raise
    except ValidationError as e:
        logger.error(f"Validation Error: {e.json()}")
        raise HTTPException(status_code=422, detail="Request data validation error")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
