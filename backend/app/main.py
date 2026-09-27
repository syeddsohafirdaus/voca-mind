import time
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.api import api_router
from app.config import settings
from app.logger import logger

app = FastAPI(
    title="Voca Mind API",
    description="Voice-based AI Emotional-Support Companion Backend API",
    version="0.1.0",
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
)

# Include master API router under /api/v1
app.include_router(api_router, prefix="/api/v1")


@app.middleware("http")
async def log_requests_middleware(request: Request, call_next):
    """Middleware for structured operational logging (path, method, duration, status).
    
    NEVER logs request payload body, message content, auth tokens, or credentials.
    """
    start_time = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start_time) * 1000

    # Operational log entry
    logger.info(
        f"HTTP {request.method} {request.url.path} - "
        f"Status: {response.status_code} - Duration: {duration_ms:.2f}ms"
    )
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Custom validation error handler returning clean JSON responses."""
    logger.warning(f"Validation error on {request.method} {request.url.path}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid request payload or parameters.",
                "details": exc.errors(),
            }
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global unhandled exception handler that prevents stack trace leaks."""
    logger.error(f"Unhandled exception on {request.method} {request.url.path}: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred. Please try again later.",
            }
        },
    )
