"""Health-related endpoints."""

import logging
from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from datetime import datetime

from app.utils.redis import get_redis_client

API_VERSION = "1.0.0"

logger = logging.getLogger(__name__)


class HealthResponse(BaseModel):
    status: str = Field(..., description="Service health status")
    timestamp: str = Field(..., description="Todays date")
    service: str = Field(..., description="Service name")


router = APIRouter()


def _health_payload(service_status: str) -> dict[str, str]:
    return {
        "status": service_status,
        "timestamp": datetime.today().strftime("%Y-%m-%d %H:%M:%S"),
        "service": "gc-signin-migration-backend",
    }


async def _dependencies_ready(request: Request) -> bool:
    if not hasattr(request.app.state, "request_client"):
        logger.error("Health check failed: request client is not initialized")
        return False

    try:
        redis_client = get_redis_client(request)
        return bool(await redis_client.ping())
    except Exception:
        logger.exception("Health check failed: Redis dependency unavailable")
        return False


@router.get(
    "/health",
    response_model=HealthResponse,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": HealthResponse,
            "description": "Service dependencies are unavailable",
        }
    },
    summary="Health Check",
    description="Returns the health status of the service",
)
async def health_check(request: Request):
    """
    Health check endpoint to monitor service status.

    This endpoint can be used by monitoring tools to check if the service is running properly.

    Returns:
        HealthResponse: Service health information including status and timestamp
    """
    if not await _dependencies_ready(request):
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=_health_payload("unhealthy"),
        )

    return _health_payload("healthy")
