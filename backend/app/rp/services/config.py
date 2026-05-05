import json
import logging
import os

from fastapi import HTTPException, Request
from httpx import AsyncClient
from pydantic import ValidationError

from app.rp.schemas import LegacyIdpSecretSchema, RPConfigSourceSchema, RPSchema
from app.utils.redis import get_redis_client
from app.utils.custom_parameters import append_customparameters_to_url
from app.utils.request_error_handler import RequestErrorHandler

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

        return matching_rp_idp

    except Exception:
        logger.error("Exception while resolving RP config")
        raise


def _normalize_redirect_language(language: str | None) -> str:
    if not isinstance(language, str):
        return "en"

    normalized = language.strip().lower()
    if "-" in normalized:
        normalized = normalized.split("-")[0]

    return normalized if normalized in ("en", "fr") else "en"


def _is_present(value: object) -> bool:
    return isinstance(value, str) and value.strip() != ""


def resolve_rp_redirect_uri(rp: object, language: str | None = None) -> str:
    normalized_language = _normalize_redirect_language(language)

    if normalized_language == "fr":
        candidates = (
            getattr(rp, "rp_redirect_uri_fr", None),
            getattr(rp, "rp_redirect_uri", None),
            getattr(rp, "rp_redirect_uri_en", None),
        )
    else:
        candidates = (
            getattr(rp, "rp_redirect_uri_en", None),
            getattr(rp, "rp_redirect_uri", None),
            getattr(rp, "rp_redirect_uri_fr", None),
        )

    redirect_uri = next(
        (candidate.strip() for candidate in candidates if _is_present(candidate)),
        None,
    )

    if redirect_uri:
        return redirect_uri

    raise HTTPException(status_code=500, detail="RP redirect URI not configured")


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
    except Exception:
        logger.error("Exception while loading RP config JSON")
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
    missing_secret_client_ids: set[str] = set()

    for rp in config_data:
        rp_copy = dict(rp)
        merged_idps = []
        for idp in rp_copy.get("IDP", []):
            idp_copy = dict(idp)
            client_id = idp_copy.get("client_id")

            if client_id:
                secret_from_env = secrets_by_client_id.get(client_id)
                if secret_from_env:
                    idp_copy["client_secret"] = secret_from_env

            if not idp_copy.get("client_secret"):
                missing_secret_client_ids.add(client_id or "<missing-client-id>")

            merged_idps.append(idp_copy)

        rp_copy["IDP"] = merged_idps
        merged.append(rp_copy)

    if missing_secret_client_ids:
        logger.warning(
            "Missing legacy IDP client_secret for one or more configured client_id values. "
            "Continuing without client_secret. Configure %s entries keyed by client_id "
            "or include inline client_secret in %s if those IdPs require confidential "
            "client auth.",
            CONFIG_SECRETS_ENV_VAR,
            CONFIG_ENV_VAR,
        )

    return merged


# Fetch and cache legacy IdP metadata in Redis.
async def get_legacy_idp_metadata(request: Request, idp_url: str, ttl: int = 86400):
    try:
        redis_client = get_redis_client(request)
        cached = await redis_client.get(idp_url)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "Redis unavailable during legacy IdP metadata lookup", exc_info=True
        )
        raise HTTPException(status_code=503, detail="Redis unavailable") from exc

    if cached:
        return json.loads(cached.decode("utf-8"))

    # Fetch metadata from legacy IdP
    try:
        async with AsyncClient(timeout=20.0) as client:
            resp = await client.get(idp_url)
            resp.raise_for_status()
            metadata = resp.json()
    except Exception as exc:
        RequestErrorHandler.handle(exc, context="legacy IdP metadata fetch")

    try:
        await redis_client.set(idp_url, json.dumps(metadata), ex=ttl)
    except Exception as exc:
        logger.error(
            "Redis unavailable while caching legacy IdP metadata", exc_info=True
        )
        raise HTTPException(status_code=503, detail="Redis unavailable") from exc
    return metadata


async def get_rp_config_details(
    rp_client_id: str,
    custom_parameters: dict[str, str] | None = None,
    language: str | None = None,
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
            "rp_redirect_url": append_customparameters_to_url(
                resolve_rp_redirect_uri(rp, language), custom_parameters
            ),
            "rp_client_id": rp.rp_client_id,
            "rp_client_name": rp.rp_client_name,
            "rp_client_name_en": rp.rp_client_name_en,
            "rp_client_name_fr": rp.rp_client_name_fr,
            "acr_values": rp.acr_values,
            "is_gckey_only": is_gckey_only,
        }

        return rpConfig

    except ValidationError:
        logger.error("Validation error while building RP config details")
        raise HTTPException(status_code=422, detail="Request data validation error")
