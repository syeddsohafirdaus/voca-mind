"""Verify takeover-aware orchestration and crisis priority."""

import pytest

from app.schemas.orchestrator import OrchestrationRequest
from app.safety.enums import SafetyState

from app.services.conversation_orchestrator import (
    ConversationOrchestrator,
    DeterministicFakeResponseGenerator,
    HUMAN_TAKEOVER_RESPONSE,
    DEFAULT_CRISIS_SAFETY_RESPONSE,
    CRISIS_FOLLOWUP_RESPONSE,
)


class SpyRetrieval:
    def __init__(self):
        self.calls = []

    async def retrieve_relevant_chunks(
        self,
        query,
        top_k=5,
        score_threshold=0.0,
    ):
        self.calls.append(query)
        return []


def build_orchestrator():
    retrieval = SpyRetrieval()

    generator = DeterministicFakeResponseGenerator(
        canned_response=(
            "I am here to listen. "
            "Would you like to tell me more?"
        )
    )

    orchestrator = ConversationOrchestrator(
        retrieval_service=retrieval,
        response_generator=generator,
    )

    return orchestrator, retrieval, generator


@pytest.mark.asyncio
async def test_normal_ai_without_takeover():
    orchestrator, retrieval, generator = (
        build_orchestrator()
    )

    result = await orchestrator.handle_turn(
        OrchestrationRequest(
            message="I had a busy day."
        )
    )

    assert result.is_human_takeover is False
    assert result.is_safety_diverted is False
    assert len(retrieval.calls) == 1
    assert len(generator.calls) == 1


@pytest.mark.asyncio
async def test_active_takeover_bypasses_generation():
    orchestrator, retrieval, generator = (
        build_orchestrator()
    )

    result = await orchestrator.handle_turn(
        OrchestrationRequest(
            message="I had a busy day.",
            human_takeover_active=True,
        )
    )

    assert result.is_human_takeover is True
    assert result.is_safety_diverted is False
    assert result.response_text == HUMAN_TAKEOVER_RESPONSE
    assert result.sources == []
    assert result.fallback_triggered is False
    assert retrieval.calls == []
    assert generator.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("active", [False, True])
async def test_crisis_always_has_priority(active):
    orchestrator, retrieval, generator = (
        build_orchestrator()
    )

    result = await orchestrator.handle_turn(
        OrchestrationRequest(
            message="I want to kill myself.",
            human_takeover_active=active,
        )
    )

    assert result.safety_result.state == SafetyState.HIGH_RISK
    assert result.is_safety_diverted is True
    assert result.is_human_takeover is False
    assert result.response_text == DEFAULT_CRISIS_SAFETY_RESPONSE
    assert result.sources == []
    assert "112" in result.response_text
    assert "14416" in result.response_text
    assert retrieval.calls == []
    assert generator.calls == []


@pytest.mark.asyncio
async def test_crisis_history_overrides_takeover():
    orchestrator, retrieval, generator = (
        build_orchestrator()
    )

    result = await orchestrator.handle_turn(
        OrchestrationRequest(
            message="I am still here.",
            human_takeover_active=True,
            conversation_history=[
                {
                    "role": "user",
                    "content": "I want to kill myself.",
                },
                {
                    "role": "assistant",
                    "content": "Are you safe right now?",
                },
            ],
        )
    )

    assert result.safety_result.state == SafetyState.HIGH_RISK
    assert result.is_safety_diverted is True
    assert result.is_human_takeover is False
    assert result.response_text == CRISIS_FOLLOWUP_RESPONSE
    assert retrieval.calls == []
    assert generator.calls == []


@pytest.mark.asyncio
async def test_takeover_preserves_concern_check_in():
    orchestrator, retrieval, generator = (
        build_orchestrator()
    )

    result = await orchestrator.handle_turn(
        OrchestrationRequest(
            message="I feel hopeless.",
            human_takeover_active=True,
        )
    )

    assert result.safety_result.state == SafetyState.CONCERN
    assert result.safety_result.requires_human_support
    assert result.is_human_takeover is True
    assert result.is_safety_diverted is False
    assert HUMAN_TAKEOVER_RESPONSE in result.response_text
    assert "?" in result.response_text
    assert retrieval.calls == []
    assert generator.calls == []


@pytest.mark.asyncio
async def test_takeover_response_privacy_boundaries():
    orchestrator, _, _ = build_orchestrator()

    result = await orchestrator.handle_turn(
        OrchestrationRequest(
            message="Can my professional see this?",
            human_takeover_active=True,
        )
    )

    assert result.is_human_takeover is True

    text = result.response_text.lower()

    assert "not automatically forwarded" in text
    assert "does not mean" in text
    assert "currently online" in text
    assert "end the takeover" in text


@pytest.mark.asyncio
async def test_normal_ai_resumes_after_takeover():
    orchestrator, retrieval, generator = (
        build_orchestrator()
    )

    first = await orchestrator.handle_turn(
        OrchestrationRequest(
            message="I had a busy day.",
            human_takeover_active=True,
        )
    )

    assert first.is_human_takeover is True
    assert generator.calls == []

    second = await orchestrator.handle_turn(
        OrchestrationRequest(
            message="Can we talk about my day?",
            human_takeover_active=False,
        )
    )

    assert second.is_human_takeover is False
    assert second.is_safety_diverted is False
    assert len(retrieval.calls) == 1
    assert len(generator.calls) == 1
