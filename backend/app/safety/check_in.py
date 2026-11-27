"""Backend-controlled safety check-ins."""

from app.safety.enums import SafetyState
from app.safety.schemas import SafetyResult


SAFETY_CHECK_IN_QUESTION = (
    "Are you having thoughts of hurting yourself, "
    "or are you worried that you might not be able to stay safe?"
)


def requires_safety_check_in(result: SafetyResult) -> bool:
    return (
        result.state == SafetyState.CONCERN
        and result.requires_human_support
    )


def enforce_safety_check_in(
    response: str,
    result: SafetyResult,
) -> str:

    if not requires_safety_check_in(result):
        return response

    if SAFETY_CHECK_IN_QUESTION in response:
        return response

    return (
        response.rstrip()
        + "\n\n"
        + SAFETY_CHECK_IN_QUESTION
    )
