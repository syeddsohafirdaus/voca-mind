import pytest

from app.safety.check_in import SAFETY_CHECK_IN_QUESTION
from app.schemas.orchestrator import OrchestrationRequest
from app.services.conversation_orchestrator import (
    ConversationOrchestrator,
    DeterministicFakeResponseGenerator,
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "message, expected",
    [
        ("I had a stressful day.", False),
        ("I feel completely hopeless.", True),
        ("I feel like giving up on everything.", True),
        ("I have many college assignments.", False),
        ("I don't want to die.", False),
    ],
)
async def test_safety_check_in(message, expected):

    generator = DeterministicFakeResponseGenerator(
        canned_response="I am here to listen."
    )

    orchestrator = ConversationOrchestrator(
        response_generator=generator
    )

    result = await orchestrator.handle_turn(
        OrchestrationRequest(message=message)
    )

    assert (
        SAFETY_CHECK_IN_QUESTION in result.response_text
    ) == expected

    assert result.fallback_triggered is False
    assert result.is_safety_diverted is False
