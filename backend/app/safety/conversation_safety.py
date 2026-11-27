"""Context-aware safety routing for recent conversation history."""

from app.safety.engine import evaluate_message
from app.safety.enums import SafetyState
from app.safety.schemas import SafetyResult


def evaluate_conversation(
    message: str,
    conversation_history=None,
) -> SafetyResult:

    current = evaluate_message(message)

    # Current high-risk signals always take priority.
    if current.state == SafetyState.HIGH_RISK:
        return current

    if not conversation_history:
        return current

    recent_users = []

    # Examine only recent user-authored messages.
    for item in conversation_history[-10:]:

        if isinstance(item, dict):
            role = item.get("role")
            content = item.get("content")
        else:
            role = getattr(item, "role", None)
            content = getattr(item, "content", None)

        if (
            role == "user"
            and isinstance(content, str)
            and content.strip()
        ):
            recent_users.append(content)

    recent_results = [
        evaluate_message(content)
        for content in recent_users
    ]

    # Preserve recent high-risk signals.
    for result in reversed(recent_results):
        if result.state == SafetyState.HIGH_RISK:
            return result

    # Preserve current concern signals.
    if current.state == SafetyState.CONCERN:
        return current

    # Continue supportive check-ins after recent distress.
    for result in reversed(recent_results[-2:]):
        if result.state == SafetyState.CONCERN:
            return result

    return current
