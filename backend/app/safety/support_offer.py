"""Deterministic, consent-based professional support offers."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.safety.enums import SafetyState
from app.safety.schemas import SafetyResult


class SupportOffer(BaseModel):
    model_config = ConfigDict(frozen=True)

    offered: bool = False

    priority: Literal[
        "none", "routine", "urgent"
    ] = "none"

    message: str | None = None

    action: Literal[
        "request_professional_support"
    ] | None = None

    requires_consent: bool = True

    automatic_notification: bool = False

    emergency_service: bool = False


def build_support_offer(
    safety_result: SafetyResult,
    *,
    has_open_support: bool = False,
) -> SupportOffer:

    if has_open_support:
        return SupportOffer()

    if safety_result.state == SafetyState.HIGH_RISK:
        return SupportOffer(
            offered=True,
            priority="urgent",
            message=(
                "You can also request support from a "
                "verified mental health professional. "
                "This request is not an emergency service "
                "and may not receive an immediate response. "
                "If you are in immediate danger, contact "
                "local emergency services without waiting "
                "for this request."
            ),
            action="request_professional_support",
        )

    if (
        safety_result.state == SafetyState.CONCERN
        and safety_result.requires_human_support
    ):
        return SupportOffer(
            offered=True,
            priority="routine",
            message=(
                "If you would like additional support, "
                "you can request to connect with a verified "
                "mental health professional. "
                "The choice is yours, and your private "
                "AI conversations will not be shared "
                "automatically."
            ),
            action="request_professional_support",
        )

    return SupportOffer()
