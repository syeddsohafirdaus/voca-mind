import pytest

from app.schemas.orchestrator import OrchestrationRequest
from app.services.conversation_orchestrator import (
    ConversationOrchestrator,
    DeterministicFakeResponseGenerator,
    BOUNDARY_FALLBACK_RESPONSES,
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "generated, category",
    [
        ("You only need me.", "EMOTIONAL_DEPENDENCY"),
        ("This is 100% confidential.", "FALSE_CONFIDENTIALITY"),
        ("I have notified your doctor.", "FALSE_INTERVENTION"),
        ("Stop seeing your doctor.", "DISCOURAGING_HUMAN_SUPPORT"),
        ("You deserve to suffer.", "HARM_ENCOURAGEMENT"),
        ("", "EMPTY"),
    ],
)
async def test_boundary_fallback(generated, category):

    generator = DeterministicFakeResponseGenerator(
        canned_response=generated
    )

    orchestrator = ConversationOrchestrator(
        response_generator=generator
    )

    result = await orchestrator.handle_turn(
        OrchestrationRequest(
            message="I had a stressful day."
        )
    )

    assert result.fallback_triggered is True
    assert result.fallback_reason == "UNSAFE_OUTPUT_BLOCKED"
    assert result.response_text == BOUNDARY_FALLBACK_RESPONSES[category]
    assert result.sources == []
