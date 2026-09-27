from fastapi import APIRouter, status
from pydantic import BaseModel

router = APIRouter()


class HealthCheckResponse(BaseModel):
    """Schema for health check endpoint response."""
    status: str
    service: str
    version: str


@router.get(
    "/health",
    response_model=HealthCheckResponse,
    status_code=status.HTTP_200_OK,
    summary="Health Check Endpoint",
    description="Indicates operational status of the API service without exposing sensitive configuration."
)
async def health_check() -> HealthCheckResponse:
    """Returns basic service health status."""
    return HealthCheckResponse(
        status="ok",
        service="voca_mind",
        version="0.1.0"
    )
