
from typing import Optional

from fastapi import Depends

from app.ai.openai_generator import OpenAIResponseGenerator
from app.ai.ollama_generator import OllamaResponseGenerator
from app.config import settings
from app.knowledge.retrieval import KnowledgeRetrievalService
from app.services.conversation_orchestrator import (
    ConversationOrchestrator,
    DeterministicFakeResponseGenerator,
    ResponseGeneratorProtocol,
    RetrievalProtocol,
)


_cached_response_generator: Optional[ResponseGeneratorProtocol] = None
_cached_retrieval_service: Optional[RetrievalProtocol] = None


def get_response_generator() -> ResponseGeneratorProtocol:
    """Select the configured AI response generator."""
    global _cached_response_generator

    if _cached_response_generator is not None:
        return _cached_response_generator

    provider = settings.AI_PROVIDER.strip().lower()

    if provider == "ollama":
        _cached_response_generator = OllamaResponseGenerator(
            base_url=settings.OLLAMA_BASE_URL,
            model=settings.OLLAMA_MODEL,
            timeout=settings.OLLAMA_TIMEOUT_SECONDS,
        )
        return _cached_response_generator

    if provider not in ("auto", "openai", "fake"):
        raise ValueError(f"Unsupported AI_PROVIDER: {provider}")

    if provider == "fake":
        if (
            settings.ENVIRONMENT == "production"
            or not settings.ALLOW_DEV_FAKE_GENERATOR
        ):
            raise ValueError(
                "Fake generator is not permitted in this environment."
            )

        _cached_response_generator = DeterministicFakeResponseGenerator()
        return _cached_response_generator

    if settings.OPENAI_API_KEY and settings.OPENAI_API_KEY.strip():
        _cached_response_generator = OpenAIResponseGenerator(
            api_key=settings.OPENAI_API_KEY.strip(),
            model=settings.OPENAI_CHAT_MODEL,
            timeout=settings.OPENAI_TIMEOUT_SECONDS,
        )
        return _cached_response_generator

    if (
        provider == "auto"
        and settings.ENVIRONMENT != "production"
        and settings.ALLOW_DEV_FAKE_GENERATOR
    ):
        _cached_response_generator = DeterministicFakeResponseGenerator()
        return _cached_response_generator

    _cached_response_generator = OpenAIResponseGenerator(api_key=None)
    return _cached_response_generator


def get_retrieval_service() -> RetrievalProtocol:
    """Return the knowledge retrieval service."""
    global _cached_retrieval_service

    if _cached_retrieval_service is None:
        _cached_retrieval_service = KnowledgeRetrievalService()

    return _cached_retrieval_service


def get_orchestrator(
    retrieval_service: RetrievalProtocol = Depends(get_retrieval_service),
    response_generator: ResponseGeneratorProtocol = Depends(get_response_generator),
) -> ConversationOrchestrator:
    """Build the existing safety-aware conversation orchestrator."""
    return ConversationOrchestrator(
        retrieval_service=retrieval_service,
        response_generator=response_generator,
    )


def reset_orchestrator_factory_cache() -> None:
    """Reset cached dependencies."""
    global _cached_response_generator, _cached_retrieval_service
    _cached_response_generator = None
    _cached_retrieval_service = None

