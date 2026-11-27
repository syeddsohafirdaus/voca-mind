import pytest

from app.safety.crisis_resources import get_crisis_resources

from app.services.conversation_orchestrator import (
    DEFAULT_CRISIS_SAFETY_RESPONSE,
    CRISIS_FOLLOWUP_RESPONSE,
    CONCERN_FALLBACK_RESPONSE,
)


@pytest.mark.parametrize(
    "response",
    [
        get_crisis_resources(),
        DEFAULT_CRISIS_SAFETY_RESPONSE,
        CRISIS_FOLLOWUP_RESPONSE,
        CONCERN_FALLBACK_RESPONSE,
    ],
)
def test_regional_crisis_resources(response):
    assert "112" in response
    assert "14416" in response
    assert "1800-891-4416" in response
    assert "findahelpline.com" in response
    assert "befrienders.org" in response
    assert "If you are in India" in response
    assert "If you are outside India" in response
