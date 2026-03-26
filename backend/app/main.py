import httpx
import requests
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from authlib.integrations.starlette_client import OAuthError
from starsessions import SessionMiddleware, SessionAutoloadMiddleware
from redis.asyncio import Redis
from starsessions.stores.redis import RedisStore

from app.config import get_configuration
from app.utils.helpers import generate_error_response
from app.auth.services.auth import redirect_user_to_idp_verify
from app.constants.redis_keys import RedisKeys
from app.constants.session_keys import SessionKeys

from .routers import health
from app.auth import v1_router as v1_auth_router
from app.auth.services import oidc_config
from app.auth_legacy import v1_router as v1_auth_legacy_router
from app.rp import v1_router as v1_rp_router
from app.utils.standardized_logging import StandardizedLoggingMiddleware

configuration = get_configuration()


class HealthCheckFilter(logging.Filter):
    """Filter to suppress healthcheck logs from Uvicorn access logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        # Suppress logs for /health/health endpoint
        return record.getMessage().find("/health/health") == -1


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Add filter to suppress healthcheck logs from Uvicorn access logs
logging.getLogger("uvicorn.access").addFilter(HealthCheckFilter())


API_DESCRIPTION = """
This API backend service primarily interacts with [IBM Verify service](https://docs.verify.ibm.com/verify/reference).
API endpoints are consumed by our frontend application to perform user authentication and profile management.
The API endpoints enable our custom frontend application to implement complex workflows and user interfaces without limitations.

### Features

* Password-based authentication
* SMS, Email, Voice callback one-time passcode (OTP)
"""

CONTACT_INFO = {
    "name": "GC Sign In Team",
    "url": configuration.app_info.github_url,
    "email": configuration.app_info.email,
}

redis_url = configuration.session_config.SESSION_REDIS_URL
if configuration.ENVIRONMENT != "local":
    # Construct the Redis URL with TLS and authentication for non-local environments
    redis_url = f"rediss://:{configuration.session_config.REDIS_AUTH_SECRET}@{configuration.session_config.REDIS_DOMAIN}:{configuration.session_config.REDIS_PORT}?ssl_cert_reqs=none"
redis_client = Redis.from_url(redis_url)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.config = configuration
    ibm_verify_config = app.state.config.ibm_verify_config
    logger.info("Starting IBM Verify Integration API")
    logger.info("Tenant URL: %s", ibm_verify_config.IBM_VERIFY_TENANT_URL)
    logger.info("Client ID: %s", ibm_verify_config.IBM_VERIFY_MIGRATION_API_CLIENT_ID)
    logger.info(
        "PROFILE_MANAGEMENT_CLIENT_ID: %s",
        ibm_verify_config.IBM_VERIFY_MIGRATION_CLIENT_ID,
    )
    app.state.request_client = httpx.AsyncClient()

    if redis_client is not None:
        pong = await redis_client.ping()
        if pong:
            app.state.redis_client = redis_client

    oidc_config.register_oidc(app.state.config)
    logger.info("CORS Origins: %s", app.state.config.cors_origins_list)
    logger.info("oidc_well_known_config: %s", app.state.config.oidc_well_known_config)
    logger.info("my_profile_endpoint: %s", app.state.config.profile_api_endpoint)
    yield
    await app.state.request_client.aclose()
    if hasattr(app.state, "redis_client"):
        await app.state.redis_client.close()


app = FastAPI(
    lifespan=lifespan,
    title=configuration.app_info.app_name,
    description=API_DESCRIPTION,
    contact=CONTACT_INFO,
)

# Determine session domain
# ROOT_DOMAIN is .<ROOT_DOMAIN> example: .signin-connexion.cdssandbox.xyz
session_domain = None
if configuration.ENVIRONMENT != "local":
    session_domain = f".{configuration.ROOT_DOMAIN}"

session_store = RedisStore(
    connection=redis_client,
    prefix=RedisKeys.REDIS_SESSION_KEY.value,
    gc_ttl=configuration.session_config.SESSION_LIFETIME,
)

# Determine if cookie should be secure
cookie_secure = False if configuration.ENVIRONMENT == "local" else True

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=configuration.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Logging
app.add_middleware(StandardizedLoggingMiddleware)

# Autoload session if cookie is present
app.add_middleware(SessionAutoloadMiddleware)
# SessionMiddleware
app.add_middleware(
    SessionMiddleware,
    store=session_store,
    rolling=True,
    cookie_https_only=cookie_secure,
    lifetime=configuration.session_config.SESSION_LIFETIME,
    cookie_domain=configuration.ROOT_DOMAIN,
    cookie_name=configuration.session_config.SESSION_COOKIE_NAME,
)


app.include_router(health.router)

app.include_router(
    v1_auth_router.router,
    prefix=f"{configuration.V1_API_VERSION}/auth",
    tags=["Auth"],
)

# app.include_router(
#     v1_auth_legacy_router.router,
#     prefix=f"{configuration.V1_API_VERSION}/auth/legacy",
#     tags=["Legacy Auth"],
# )

app.include_router(
    v1_auth_legacy_router.router,
    prefix=f"{configuration.V1_API_VERSION}/auth/legacy",
    tags=["Legacy Auth"],
)

app.include_router(
    v1_rp_router.router,
    prefix=f"{configuration.V1_API_VERSION}/rp",
    tags=["Relying Party"],
)

# app.include_router(
#     v1_password_router.router,
#     prefix=f"{configuration.V1_API_VERSION}/password",
#     tags=["Password"],
# )

# app.include_router(
#     v1_otp_router.router,
#     prefix=f"{configuration.V1_API_VERSION}/otp",
#     tags=["OTP"],
# )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # The Signup user endpoint uses Pydantic to validate the email
    # This handler is required to send a common format for errors

    error_message = ""
    for error in exc.errors():
        error_message = error["msg"]
        logger.error("Validation error: %s at %s", error_message, request.url.path)
        break
    return generate_error_response(status_code=400, message=error_message)


@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "message": exc.detail},
    )


@app.exception_handler(OAuthError)
async def oauth_error_handler(request: Request, _exc: OAuthError):
    """Catch OAuth errors and redirect user to IdP login."""
    logger.error("OAuth exception handler error")
    if "application/json" in request.headers.get("accept", ""):
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid or expired token"},
        )

    client_id = request.session.get(
        SessionKeys.RP_CLIENT_ID_KEY.value
    ) or request.query_params.get(SessionKeys.RP_CLIENT_ID_KEY.value)
    lang = request.session.get(
        SessionKeys.CURRENT_LANGUAGE.value
    ) or request.query_params.get("lang", "en")
    if not isinstance(lang, str):
        lang = "en"
    lang = lang.lower()
    if lang not in ("en", "fr"):
        lang = "en"

    if not client_id:
        logger.error(
            "OAuth exception handler missing rp_client_id for path %s; returning 401",
            request.url.path,
        )
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid or expired token"},
        )

    return await redirect_user_to_idp_verify(request, client_id, lang)


def log_request_response(
    endpoint: str, request_data: dict, response: requests.Response
):
    """Log request and response details"""
    try:
        request_fields = (
            sorted(request_data.keys()) if isinstance(request_data, dict) else []
        )
        logger.info(
            "[%s] Request fields: %s",
            endpoint,
            request_fields,
        )
        logger.info("[%s] Response status: %s", endpoint, response.status_code)
        logger.info(
            "[%s] Response header keys: %s",
            endpoint,
            sorted(dict(response.headers).keys()),
        )
        try:
            response_body = response.json()
            if isinstance(response_body, dict):
                body_summary = sorted(response_body.keys())
            elif isinstance(response_body, list):
                body_summary = f"list[{len(response_body)}]"
            else:
                body_summary = type(response_body).__name__
        except ValueError:
            body_summary = "non-json"

        logger.info("[%s] Response body summary: %s", endpoint, body_summary)
    except Exception:
        logger.error("[%s] Error logging request/response", endpoint)
