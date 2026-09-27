from app.logger import logger
from app.safety.enums import RecommendedAction, SafetyReasonCode, SafetyState
from app.safety.rules import (
    CONCERN_PATTERNS,
    HIGH_RISK_PATTERNS,
    NEGATION_PATTERNS,
    THIRD_PARTY_MEDIA_PATTERNS,
)
from app.safety.schemas import SafetyResult


def evaluate_message(message: str) -> SafetyResult:
    """Evaluates an input message string against deterministic safety rules and returns a structured SafetyResult.

    Privacy & Safety Guarantees:
    - Does NOT log full raw message content (logs operational state and reason codes only).
    - Does NOT determine clinical diagnoses or medical probabilities.
    - Confidence represents rule-engine detection certainty (0.0 to 1.0).
    """
    if not message or not message.strip():
        return SafetyResult(
            state=SafetyState.LOW,
            confidence=0.99,
            reasons=[SafetyReasonCode.NO_SAFETY_CONCERN_DETECTED],
            requires_human_support=False,
            requires_emergency_guidance=False,
            recommended_action=RecommendedAction.NORMAL_CONVERSATION,
        )

    clean_message = message.strip()

    # 1. Check Negations
    is_negated = any(pattern.search(clean_message) for pattern in NEGATION_PATTERNS)

    # 2. Check Third Party / Media / Past Mentions
    is_third_party_media = any(pattern.search(clean_message) for pattern in THIRD_PARTY_MEDIA_PATTERNS)

    # 3. Check High Risk Patterns (Unless overridden by negation or third-party/media context)
    high_risk_reasons: list[SafetyReasonCode] = []
    if not is_negated and not is_third_party_media:
        for pattern, reason in HIGH_RISK_PATTERNS:
            if pattern.search(clean_message):
                high_risk_reasons.append(reason)

    if high_risk_reasons:
        result = SafetyResult(
            state=SafetyState.HIGH_RISK,
            confidence=0.95,
            reasons=list(dict.fromkeys(high_risk_reasons)),
            requires_human_support=True,
            requires_emergency_guidance=True,
            recommended_action=RecommendedAction.IMMEDIATE_HUMAN_EMERGENCY_SUPPORT,
        )
        logger.info(f"Safety Engine evaluated state={result.state} reasons={result.reasons}")
        return result

    # 4. Check Concern Patterns
    concern_reasons: list[SafetyReasonCode] = []
    for pattern, reason in CONCERN_PATTERNS:
        if pattern.search(clean_message):
            concern_reasons.append(reason)

    if concern_reasons:
        requires_human = any(
            r in (SafetyReasonCode.FEAR_OF_SELF_HARM, SafetyReasonCode.HOPELESSNESS_SIGNAL, SafetyReasonCode.UNABLE_TO_COPE)
            for r in concern_reasons
        )
        result = SafetyResult(
            state=SafetyState.CONCERN,
            confidence=0.85,
            reasons=list(dict.fromkeys(concern_reasons)),
            requires_human_support=requires_human,
            requires_emergency_guidance=False,
            recommended_action=RecommendedAction.SUPPORTIVE_CHECK_IN,
        )
        logger.info(f"Safety Engine evaluated state={result.state} reasons={result.reasons}")
        return result

    # 5. Handle Context Overrides (Negation / Third Party / Everyday Emotion)
    low_reasons: list[SafetyReasonCode] = []
    if is_negated:
        low_reasons.append(SafetyReasonCode.NEGATED_SELF_HARM_MENTION)
    if is_third_party_media:
        low_reasons.append(SafetyReasonCode.THIRD_PARTY_OR_MEDIA_MENTION)
    if not low_reasons:
        low_reasons.append(SafetyReasonCode.NO_SAFETY_CONCERN_DETECTED)

    result = SafetyResult(
        state=SafetyState.LOW,
        confidence=0.99 if (is_negated or is_third_party_media) else 0.95,
        reasons=list(dict.fromkeys(low_reasons)),
        requires_human_support=False,
        requires_emergency_guidance=False,
        recommended_action=RecommendedAction.NORMAL_CONVERSATION,
    )
    logger.info(f"Safety Engine evaluated state={result.state} reasons={result.reasons}")
    return result
