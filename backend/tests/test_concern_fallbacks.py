import pytest

from app.safety.enums import SafetyState
from app.schemas.orchestrator import OrchestrationRequest
from app.services.conversation_orchestrator import (
    ConversationOrchestrator,
    DeterministicFakeResponseGenerator,
    CONCERN_FALLBACK_RESPONSE,
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "should_fail, expected_reason",
    [
        (True, "GENERATOR_ERROR"),
        (False, "UNSAFE_OUTPUT_BLOCKED"),
    ],
)
async def test_concern_fallback(should_fail, expected_reason):

    generator = DeterministicFakeResponseGenerator(
        should_fail=should_fail,
        canned_response="You only need me.",
    )

    orchestrator = ConversationOrchestrator(
        response_generator=generator
    )

    result = await orchestrator.handle_turn(
        OrchestrationRequest(
            message="I feel completely hopeless."
        )
    )

    assert result.safety_result.state == SafetyState.CONCERN
    assert result.fallback_triggered is True
    assert result.fallback_reason == expected_reason
    assert result.response_text == CONCERN_FALLBACK_RESPONSE
    assert result.sources == []
