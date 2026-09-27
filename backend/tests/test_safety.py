import pytest
from app.safety import (
    RecommendedAction,
    SafetyReasonCode,
    SafetyState,
    evaluate_message,
)


def test_safety_low_examples():
    """Test standard everyday stress and negative emotions evaluate to LOW state."""
    low_inputs = [
        "I'm having a stressful day.",
        "I feel lonely tonight.",
        "I'm worried about my exams.",
        "Today was really difficult at work.",
        "I'm frustrated with my project progress.",
    ]
    for text in low_inputs:
        result = evaluate_message(text)
        assert result.state == SafetyState.LOW
        assert 0.0 <= result.confidence <= 1.0
        assert result.requires_human_support is False
        assert result.requires_emergency_guidance is False
        assert result.recommended_action == RecommendedAction.NORMAL_CONVERSATION
        assert SafetyReasonCode.NO_SAFETY_CONCERN_DETECTED in result.reasons


def test_safety_concern_examples():
    """Test hopeless and severe distress statements evaluate to CONCERN state."""
    concern_inputs = [
        "I feel completely hopeless.",
        "I can't cope anymore.",
        "Everything feels overwhelming.",
        "I feel like I'm drowning in pain.",
    ]
    for text in concern_inputs:
        result = evaluate_message(text)
        assert result.state == SafetyState.CONCERN
        assert 0.0 <= result.confidence <= 1.0
        assert result.requires_emergency_guidance is False
        assert result.recommended_action == RecommendedAction.SUPPORTIVE_CHECK_IN
        assert len(result.reasons) > 0


def test_safety_high_risk_examples():
    """Test explicit suicidal intent, plan, self-harm, or inability to stay safe evaluate to HIGH_RISK state."""
    high_risk_inputs = [
        "I want to kill myself",
        "I want to die right now",
        "I am going to end my life",
        "I am going to cut myself right now",
        "I have a plan to end my life tonight",
        "I can't keep myself safe right now",
        "how to commit suicide",
    ]
    for text in high_risk_inputs:
        result = evaluate_message(text)
        assert result.state == SafetyState.HIGH_RISK
        assert 0.0 <= result.confidence <= 1.0
        assert result.requires_human_support is True
        assert result.requires_emergency_guidance is True
        assert result.recommended_action == RecommendedAction.IMMEDIATE_HUMAN_EMERGENCY_SUPPORT
        assert len(result.reasons) > 0


def test_safety_context_false_positives_and_negations():
    """Test negation, media, third-party, and fear-vs-intent contextual distinctions."""
    # 1. Negated intent should evaluate to LOW
    negated_inputs = [
        "I don't want to die.",
        "I am not going to kill myself.",
        "I would never end my life.",
    ]
    for text in negated_inputs:
        result = evaluate_message(text)
        assert result.state == SafetyState.LOW
        assert result.requires_emergency_guidance is False
        assert SafetyReasonCode.NEGATED_SELF_HARM_MENTION in result.reasons

    # 2. Third-party or media mentions should evaluate to LOW
    third_party_inputs = [
        "My friend died last year.",
        "I watched a movie about suicide.",
        "The game character died.",
        "My grandma passed away recently.",
    ]
    for text in third_party_inputs:
        result = evaluate_message(text)
        assert result.state == SafetyState.LOW
        assert result.requires_emergency_guidance is False
        assert SafetyReasonCode.THIRD_PARTY_OR_MEDIA_MENTION in result.reasons

    # 3. Fear/worry of self-harm (seeking help/expressing fear) should evaluate to CONCERN
    fear_result = evaluate_message("I'm scared I might hurt myself")
    assert fear_result.state == SafetyState.CONCERN
    assert fear_result.requires_human_support is True
    assert fear_result.requires_emergency_guidance is False
    assert fear_result.recommended_action == RecommendedAction.SUPPORTIVE_CHECK_IN
    assert SafetyReasonCode.FEAR_OF_SELF_HARM in fear_result.reasons


def test_safety_edge_cases_and_formatting():
    """Test empty string, whitespace, case insensitivity, and punctuation variations."""
    # Empty and whitespace
    empty_result = evaluate_message("")
    assert empty_result.state == SafetyState.LOW

    space_result = evaluate_message("   \n\t  ")
    assert space_result.state == SafetyState.LOW

    # Uppercase variations
    upper_result = evaluate_message("I WANT TO DIE")
    assert upper_result.state == SafetyState.HIGH_RISK

    # Punctuation variations
    punct_result = evaluate_message("I want to kill myself!!!...")
    assert punct_result.state == SafetyState.HIGH_RISK
