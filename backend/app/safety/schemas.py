from pydantic import BaseModel, ConfigDict, Field
from app.safety.enums import RecommendedAction, SafetyReasonCode, SafetyState


class SafetyResult(BaseModel):
    """Structured evaluation output produced by the Safety Engine.

    Privacy & Non-Clinical Boundary:
    - This result contains detection routing signals, NOT clinical diagnoses or medical probabilities.
    - Confidence represents rule-engine match certainty (0.0 to 1.0), NOT diagnostic probability.
    - Reasons contain structured codes, preserving user message privacy by avoiding raw message logging.
    """

    state: SafetyState = Field(
        ...,
        description="Detected conceptual safety state (LOW, CONCERN, HIGH_RISK)"
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description=(
            "Detection certainty score (0.0 to 1.0). "
            "Represents pattern match confidence, NOT medical probability."
        )
    )
    reasons: list[SafetyReasonCode] = Field(
        default_factory=list,
        description="Concise structured safety signal codes."
    )
    requires_human_support: bool = Field(
        ...,
        description="Indicates if connecting with a human support resource is recommended."
    )
    requires_emergency_guidance: bool = Field(
        ...,
        description="Indicates if immediate emergency crisis guidance is required."
    )
    recommended_action: RecommendedAction = Field(
        ...,
        description="Recommended system response routing action."
    )

    model_config = ConfigDict(frozen=True)
