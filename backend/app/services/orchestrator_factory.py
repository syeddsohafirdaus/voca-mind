from typing import Optional
from fastapi import Depends
from app.ai.openai_generator import OpenAIResponseGenerator
from app.config import settings
from app.knowledge.retrieval import KnowledgeRetrievalService
from app.services.conversation_orchestrator import (
    ConversationOrchestrator,
    DeterministicFakeResponseGenerator,
    ResponseGeneratorProtocol,
    RetrievalProtocol,
)

# Cached generator instance across requests
_cached_response_generator: Optional[ResponseGeneratorProtocol] = None
_cached_retrieval_service: Optional[RetrievalProtocol] = None


def get_response_generator() -> ResponseGeneratorProtocol:
    """Dependency provider returning the active response generator.

    Safeguards:
    - If OPENAI_API_KEY is configured, returns OpenAIResponseGenerator.
    - If OPENAI_API_KEY is missing in production (or when ALLOW_DEV_FAKE_GENERATOR is False),
      returns OpenAIResponseGenerator(api_key=None), which raises ValueError on invocation
      and causes ConversationOrchestrator to return safe fallback rather than silently
      returning a fake response.
    - DeterministicFakeResponseGenerator is ONLY used in test or explicitly configured development
      environments where ALLOW_DEV_FAKE_GENERATOR is True.
    """
    global _cached_response_generator
    if _cached_response_generator is not None:
        return _cached_response_generator

    if settings.OPENAI_API_KEY and settings.OPENAI_API_KEY.strip():
        _cached_response_generator = OpenAIResponseGenerator(
            api_key=settings.OPENAI_API_KEY.strip(),
            model=settings.OPENAI_CHAT_MODEL,
            timeout=settings.OPENAI_TIMEOUT_SECONDS,
        )
        return _cached_response_generator

    if settings.ENVIRONMENT == "production" or not settings.ALLOW_DEV_FAKE_GENERATOR:
        # In production or when fake generator not explicitly allowed, fail safely
        _cached_response_generator = OpenAIResponseGenerator(api_key=None)
        return _cached_response_generator

    _cached_response_generator = DeterministicFakeResponseGenerator()
    return _cached_response_generator


def get_retrieval_service() -> RetrievalProtocol:
    """Dependency provider returning the active knowledge retrieval service."""
    global _cached_retrieval_service
    if _cached_retrieval_service is None:
        _cached_retrieval_service = KnowledgeRetrievalService()
    return _cached_retrieval_service


def get_orchestrator(
    retrieval_service: RetrievalProtocol = Depends(get_retrieval_service),
    response_generator: ResponseGeneratorProtocol = Depends(get_response_generator),
) -> ConversationOrchestrator:
    """Dependency provider returning ConversationOrchestrator with injected services."""
    return ConversationOrchestrator(
        retrieval_service=retrieval_service,
        response_generator=response_generator,
    )


def reset_orchestrator_factory_cache() -> None:
    """Resets cached generator and retrieval service instances."""
    global _cached_response_generator, _cached_retrieval_service
    _cached_response_generator = None
    _cached_retrieval_service = None
