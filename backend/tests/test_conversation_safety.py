import pytest

from app.safety.conversation_safety import evaluate_conversation
from app.safety.enums import SafetyState


@pytest.mark.parametrize(
    "history, message, expected",
    [
        (
            [],
            "I had a stressful day.",
            SafetyState.LOW,
        ),
        (
            [
                {"role": "user",
                 "content": "I feel completely hopeless."}
            ],
            "Nothing has changed.",
            SafetyState.CONCERN,
        ),
        (
            [
                {"role": "user",
                 "content": "I want to die."}
            ],
            "I don't know what to do.",
            SafetyState.HIGH_RISK,
        ),
        (
            [
                {"role": "user",
                 "content": "I want to die."}
            ],
            "I feel better now.",
            SafetyState.HIGH_RISK,
        ),
        (
            [
                {"role": "assistant",
                 "content": "Are you feeling unsafe right now?"}
            ],
            "I had a stressful exam.",
            SafetyState.LOW,
        ),
        (
            [
                {"role": "user",
                 "content": "I am studying for exams."}
            ],
            "I can't keep myself safe.",
            SafetyState.HIGH_RISK,
        ),
        (
            [
                {"role": "user",
                 "content": "I have many assignments."}
            ],
            "I feel tired.",
            SafetyState.LOW,
        ),
        (
            [
                {"role": "user",
                 "content": "I want to die."}
            ],
            "I don't want to die.",
            SafetyState.HIGH_RISK,
        ),
    ],
)
def test_conversation_safety(history, message, expected):

    result = evaluate_conversation(message, history)

    assert result.state == expected

    if expected == SafetyState.HIGH_RISK:
        assert result.requires_human_support is True
        assert result.requires_emergency_guidance is True
