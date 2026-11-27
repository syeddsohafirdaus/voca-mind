"""Main API router for Voca Mind."""

from fastapi import APIRouter

from app.api.health import router as health_router
from app.api.conversations import router as conversations_router
from app.api.auth import router as auth_router
from app.api.guardians import router as guardians_router
from app.api.doctors import router as doctors_router
from app.api.admin import router as admin_router
from app.api.assignments import router as assignments_router
from app.api.professional_messages import router as professional_messages_router
from app.api.support_requests import router as support_requests_router


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


# Protected professional endpoints
api_router.include_router(
    doctors_router,
    prefix="/doctors",
    tags=["Doctors"],
)


# Restricted administrator endpoints
api_router.include_router(
    admin_router,
    prefix="/admin",
    tags=["Administration"],
)


api_router.include_router(
    assignments_router,
    prefix="/assignments",
    tags=["Professional Assignments"],
)


api_router.include_router(
    professional_messages_router,
    prefix="/professional",
    tags=["Professional Messaging"],
)


api_router.include_router(
    support_requests_router,
    prefix="/support",
    tags=["Professional Support"],
)


__all__ = ["api_router"]
