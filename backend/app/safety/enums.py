from enum import Enum


class SafetyState(str, Enum):
    """Conceptual safety states evaluated by the Safety Engine.

    Note: These represent risk detection signals for response routing.
    They do NOT represent medical or clinical diagnostic states.
    """
    LOW = "LOW"
    CONCERN = "CONCERN"
    HIGH_RISK = "HIGH_RISK"


class RecommendedAction(str, Enum):
    """Recommended system response routing actions."""
    NORMAL_CONVERSATION = "NORMAL_CONVERSATION"
    SUPPORTIVE_CHECK_IN = "SUPPORTIVE_CHECK_IN"
    IMMEDIATE_HUMAN_EMERGENCY_SUPPORT = "IMMEDIATE_HUMAN_EMERGENCY_SUPPORT"


class SafetyReasonCode(str, Enum):
    """Structured reason codes for safety evaluation signals."""
    # High Risk Reasons
    EXPLICIT_SUICIDAL_INTENT = "EXPLICIT_SUICIDAL_INTENT"
    EXPLICIT_SELF_HARM_INTENT = "EXPLICIT_SELF_HARM_INTENT"
    IMMEDIATE_PLAN_INDICATED = "IMMEDIATE_PLAN_INDICATED"
    INABILITY_TO_STAY_SAFE = "INABILITY_TO_STAY_SAFE"
    SUICIDE_METHOD_REQUEST = "SUICIDE_METHOD_REQUEST"

    # Concern Reasons
    HOPELESSNESS_SIGNAL = "HOPELESSNESS_SIGNAL"
    SEVERE_EMOTIONAL_DISTRESS = "SEVERE_EMOTIONAL_DISTRESS"
    UNABLE_TO_COPE = "UNABLE_TO_COPE"
    FEAR_OF_SELF_HARM = "FEAR_OF_SELF_HARM"

    # Low / Context Reasons
    NEGATED_SELF_HARM_MENTION = "NEGATED_SELF_HARM_MENTION"
    THIRD_PARTY_OR_MEDIA_MENTION = "THIRD_PARTY_OR_MEDIA_MENTION"
    NO_SAFETY_CONCERN_DETECTED = "NO_SAFETY_CONCERN_DETECTED"
