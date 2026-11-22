"""Main API router for Voca Mind."""

from fastapi import APIRouter

from app.api.health import router as health_router
from app.api.conversations import router as conversations_router
from app.api.auth import router as auth_router
from app.api.guardians import router as guardians_router


api_router = APIRouter()

# Health endpoints
api_router.include_router(
    health_router,
    tags=["Health"],
)

# Client AI conversation endpoints
api_router.include_router(
    conversations_router,
    prefix="/conversations",
    tags=["Conversations"],
)

# Client, Doctor, and Guardian registration endpoints
api_router.include_router(
    auth_router,
    prefix="/auth",
    tags=["Authentication"],
)

# Client-controlled Guardian authorization endpoints
api_router.include_router(
    guardians_router,
    prefix="/guardians",
    tags=["Guardians"],
)


__all__ = ["api_router"]
