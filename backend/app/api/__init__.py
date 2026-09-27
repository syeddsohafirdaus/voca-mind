from fastapi import APIRouter
from app.api.health import router as health_router
from app.api.conversations import router as conversations_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["Health"])
api_router.include_router(conversations_router, prefix="/conversations", tags=["Conversations"])

__all__ = ["api_router"]
