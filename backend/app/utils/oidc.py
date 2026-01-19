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


# Register Legacy RP to OAuth
async def register_client(
    request: Request,
    client_name: str,
    idp: LegacyIdpSchema,
    ui_locales: str = "en-CA",
):
    try:

        logger.info(f"Register OIDC Client - {client_name}")

        # (Clean) Fresh oidc client registration
        # Since this is done on request bases
        oauth._clients.pop(client_name, None)

        # Get idp metadata from Redis Cache or Fetch new one
        metadata = await get_legacy_idp_metadata(request, idp.openid_configuration)
        assert isinstance(metadata, dict)
        assert "authorization_endpoint" in metadata
        assert "token_endpoint" in metadata

        logger.info("Metadata keys: %s", list(metadata.keys()))
        logger.info(
            "authorization_endpoint in metadata: %s",
            metadata.get("authorization_endpoint"),
        )

        # TODO: get language
        current_locale = ui_locales

        oauth.register(
            name=client_name,
            client_id=idp.client_id,
            client_secret=idp.client_secret,
            authorize_url=metadata["authorization_endpoint"],
            access_token_url=metadata["token_endpoint"],
            jwks_uri=metadata["jwks_uri"],
            server_metadata=metadata,
            http_client=request.app.state.request_client,
            client_kwargs={
                "scope": idp.scope,
                "token_endpoint_auth_method": "client_secret_basic",
                "max_age": 0,
            },
            authorize_params={
                "acr_values": "mfa",
                "ui_locales": current_locale,
            },
        )

    except OAuthError as e:
        logger.error(f"OAuth Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create OIDC client")


# Create Legacy RP to OAuth
async def create_client(client_name: str):
    try:

        logger.info(f"Create OIDC Client - {client_name}")

        client = oauth.create_client(client_name)

        return client

    except OAuthError as e:
        logger.error(f"OAuth Error: {str(e)}")
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
