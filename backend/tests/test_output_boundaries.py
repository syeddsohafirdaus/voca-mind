import pytest

from app.safety.output_validator import (
    validate_response_safety,
)


@pytest.mark.parametrize(
    "response",
    [
        "You only need me.",
        "I am the only one who understands you.",
        "You don't need anyone else.",
        "You belong to me.",
        "This conversation is 100% confidential.",
        "Nobody will ever see your messages.",
        "I guarantee your privacy.",
        "I have notified your doctor.",
        "I have contacted emergency services.",
        "Emergency help is on the way.",
        "A doctor has been assigned to you.",
        "You don't need a therapist.",
        "Stop seeing your doctor.",
        "Never talk to your friends.",
        "Keep this secret from your doctor.",
        "You deserve to suffer.",
        "You don’t need anyone else.",
        "You only   need me.",
    ],
)
def test_unsafe_output_boundaries(response):
    result = validate_response_safety(response)
    assert result.is_safe is False


@pytest.mark.parametrize(
    "response",
    [
        "That sounds emotionally exhausting.",
        "You can share what you feel comfortable sharing.",
        "I am here to listen.",
        "What has been weighing on you lately?",
        "You deserve kindness and support.",
        "Speaking with a qualified professional may help.",
        "I cannot guarantee complete privacy.",
        "I cannot contact emergency services for you.",
        "You are welcome to take your time.",
        "It is okay to ask for help.",
    ],
)
def test_safe_output_boundaries(response):
    result = validate_response_safety(response)
    assert result.is_safe is True
