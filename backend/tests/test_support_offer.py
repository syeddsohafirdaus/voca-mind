"""Tests for consent-based AI professional support offers."""

from types import SimpleNamespace

import pytest

from app.safety.enums import SafetyState
from app.safety.support_offer import (
    SupportOffer,
    build_support_offer,
)


def assessment(state, requires_human_support=False):
    return SimpleNamespace(
        state=state,
        requires_human_support=requires_human_support,
    )


def test_default_support_offer():
    offer = SupportOffer()

    assert offer.offered is False
    assert offer.priority == "none"
    assert offer.action is None
    assert offer.message is None


def test_low_risk_does_not_offer_support():
    offer = build_support_offer(
        assessment(SafetyState.LOW)
    )

    assert offer.offered is False
    assert offer.priority == "none"


def test_low_risk_with_inconsistent_flag():
    offer = build_support_offer(
        assessment(SafetyState.LOW, True)
    )

    assert offer.offered is False


def test_concern_without_human_support():
    offer = build_support_offer(
        assessment(SafetyState.CONCERN, False)
    )

    assert offer.offered is False
    assert offer.action is None


def test_concern_with_human_support():
    offer = build_support_offer(
        assessment(SafetyState.CONCERN, True)
    )

    assert offer.offered is True
    assert offer.priority == "routine"
    assert offer.action == "request_professional_support"


def test_high_risk_offers_support():
    offer = build_support_offer(
        assessment(SafetyState.HIGH_RISK, True)
    )

    assert offer.offered is True
    assert offer.priority == "urgent"


def test_high_risk_even_without_support_flag():
    offer = build_support_offer(
        assessment(SafetyState.HIGH_RISK, False)
    )

    assert offer.offered is True
    assert offer.priority == "urgent"


@pytest.mark.parametrize("state", list(SafetyState))
def test_explicit_consent_always_required(state):
    offer = build_support_offer(
        assessment(state, True)
    )

    assert offer.requires_consent is True


@pytest.mark.parametrize("state", list(SafetyState))
def test_no_automatic_notification(state):
    offer = build_support_offer(
        assessment(state, True)
    )

    assert offer.automatic_notification is False


@pytest.mark.parametrize("state", list(SafetyState))
def test_not_an_emergency_service(state):
    offer = build_support_offer(
        assessment(state, True)
    )

    assert offer.emergency_service is False


def test_high_risk_does_not_promise_immediate_response():
    offer = build_support_offer(
        assessment(SafetyState.HIGH_RISK, True)
    )

    message = offer.message.lower()

    assert "not an emergency service" in message
    assert "may not receive an immediate response" in message


def test_high_risk_encourages_immediate_emergency_help():
    offer = build_support_offer(
        assessment(SafetyState.HIGH_RISK, True)
    )

    message = offer.message.lower()

    assert "emergency services" in message
    assert "without waiting" in message


def test_concern_offer_respects_client_choice():
    offer = build_support_offer(
        assessment(SafetyState.CONCERN, True)
    )

    assert "choice is yours" in offer.message.lower()


def test_concern_offer_preserves_conversation_privacy():
    offer = build_support_offer(
        assessment(SafetyState.CONCERN, True)
    )

    assert (
        "will not be shared automatically"
        in offer.message.lower()
    )


def test_support_offer_contains_no_private_data():
    offer = build_support_offer(
        assessment(SafetyState.HIGH_RISK, True)
    )

    allowed_fields = {
        "offered",
        "priority",
        "message",
        "action",
        "requires_consent",
        "automatic_notification",
        "emergency_service",
    }

    assert set(offer.model_dump()) == allowed_fields
