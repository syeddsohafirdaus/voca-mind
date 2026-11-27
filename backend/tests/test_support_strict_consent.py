import pytest
from pydantic import ValidationError

from app.api.support_requests import SupportRequestCreate


@pytest.mark.parametrize(
    "value",
    [False, 1, 0, "true", "yes", None, [], {}],
)
def test_invalid_consent_rejected(value):
    with pytest.raises(ValidationError):
        SupportRequestCreate(consent=value)


@pytest.mark.parametrize("source", ["client", "ai_suggestion"])
def test_explicit_consent_accepted(source):
    request = SupportRequestCreate(
        consent=True,
        source=source,
    )
    assert request.consent is True
    assert request.source == source


def test_missing_consent_rejected():
    with pytest.raises(ValidationError):
        SupportRequestCreate()
