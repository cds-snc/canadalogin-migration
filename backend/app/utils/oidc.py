import asyncio
import base64
import hashlib
import logging
import secrets

from fastapi import HTTPException, Request
from authlib.integrations.starlette_client import OAuth, OAuthError

from app.rp.schemas import LegacyIdpSchema
from app.rp.services.config import get_legacy_idp_metadata

oauth = OAuth()
logger = logging.getLogger(__name__)
_client_registry_locks: dict[str, asyncio.Lock] = {}


def _get_client_registry_lock(client_name: str) -> asyncio.Lock:
    lock = _client_registry_locks.get(client_name)
    if lock is None:
        lock = asyncio.Lock()
        _client_registry_locks[client_name] = lock
    return lock


# Register Legacy RP to OAuth
async def register_client(
    request: Request,
    client_name: str,
    idp: LegacyIdpSchema,
    ui_locales: str = "en-CA",
    acr_values: str | None = "",
):
    async with _get_client_registry_lock(client_name):
        try:
            # (Clean) Fresh oidc client registration
            # Since this is done on request bases
            oauth._clients.pop(client_name, None)

            # Get idp metadata from Redis Cache or Fetch new one
            metadata = await get_legacy_idp_metadata(request, idp.openid_configuration)
            assert isinstance(metadata, dict)
            assert "authorization_endpoint" in metadata
            assert "token_endpoint" in metadata

            # TODO: get language
            current_locale = ui_locales

            authorize_params = {"ui_locales": current_locale}
            normalized_acr_values = ""
            if acr_values:
                normalized_acr_values = ",".join(
                    value.strip() for value in acr_values.split(",") if value.strip()
                )
            if normalized_acr_values:
                authorize_params["acr_values"] = normalized_acr_values

            registration_kwargs = {
                "name": client_name,
                "client_id": idp.client_id,
                "authorize_url": metadata["authorization_endpoint"],
                "access_token_url": metadata["token_endpoint"],
                "jwks_uri": metadata["jwks_uri"],
                "server_metadata": metadata,
                "http_client": request.app.state.request_client,
                "client_kwargs": {
                    "scope": idp.scope,
                    "token_endpoint_auth_method": idp.token_endpoint_auth_method
                    or "client_secret_post",
                    "max_age": 0,
                },
                "authorize_params": authorize_params,
            }
            if idp.client_secret:
                registration_kwargs["client_secret"] = idp.client_secret
            else:
                logger.warning(
                    "Registering legacy OIDC client '%s' for client_id '%s' without "
                    "client_secret; the provider may require confidential client authentication",
                    client_name,
                    idp.client_id,
                )

            oauth.register(**registration_kwargs)

        except OAuthError:
            logger.error("OAuth error while registering legacy OIDC client")
            raise HTTPException(status_code=500, detail="Failed to create OIDC client")


def has_registered_client(client_name: str) -> bool:
    return client_name in oauth._clients


# Create Legacy RP to OAuth
async def create_client(client_name: str):
    async with _get_client_registry_lock(client_name):
        try:
            client = oauth.create_client(client_name)
            if client is None:
                logger.error("OIDC client '%s' was not registered", client_name)
                raise HTTPException(
                    status_code=500, detail="Failed to create OIDC client"
                )

            return client

        except OAuthError:
            logger.error("OAuth error while creating legacy OIDC client")
            raise HTTPException(status_code=500, detail="Failed to create OIDC client")


# Generate secure random state and nonce
def generate_secure_token(length=32):
    return (
        base64.urlsafe_b64encode(secrets.token_bytes(length))
        .rstrip(b"=")
        .decode("utf-8")
    )


# Generate code_verifier and code_challenge
def generate_code_verifier(length=64):
    return (
        base64.urlsafe_b64encode(secrets.token_bytes(length))
        .rstrip(b"=")
        .decode("utf-8")
    )


def generate_code_challenge(verifier):
    sha256 = hashlib.sha256(verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(sha256).rstrip(b"=").decode("utf-8")
