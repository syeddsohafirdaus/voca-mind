from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.safety.schemas import SafetyResult


class SourceProvenance(BaseModel):
    """Source provenance tracking for retrieved knowledge chunks."""

    document_id: str = Field(..., description="Parent document identifier.")
    chunk_id: Optional[str] = Field(default=None, description="Specific chunk identifier if available.")
    title: str = Field(..., description="Document or resource title.")
    source_name: str = Field(..., description="Authoritative publisher or organization.")
    source_url: Optional[str] = Field(default=None, description="Reference URL for provenance.")
    topic: Optional[str] = Field(default=None, description="Psychoeducational topic.")
    score: Optional[float] = Field(default=None, description="Retrieval similarity score.")

    model_config = ConfigDict(frozen=True)


class OrchestrationRequest(BaseModel):
    """Request payload for an orchestrated conversation turn."""

    message: str = Field(..., min_length=1, description="Incoming user message.")
    conversation_id: Optional[UUID] = Field(default=None, description="Associated conversation session ID.")
    user_id: Optional[UUID] = Field(default=None, description="Authenticated user ID.")
    top_k: int = Field(default=3, ge=1, le=10, description="Maximum knowledge chunks to retrieve.")
    score_threshold: float = Field(default=0.0, ge=0.0, le=1.0, description="Similarity threshold for retrieval.")

    @field_validator("message")
    @classmethod
    def validate_message_not_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Message content cannot be empty or whitespace.")
        return stripped

    model_config = ConfigDict(frozen=True)


class OrchestrationResponse(BaseModel):
    """Result payload from the conversation orchestrator."""

    response_text: str = Field(..., description="Final dialogue or safety response text.")
    safety_result: SafetyResult = Field(..., description="Evaluated safety engine result on the user message.")
    sources: List[SourceProvenance] = Field(
        default_factory=list,
        description="Preserved source provenance of retrieved knowledge chunks (empty if none or high-risk)."
    )
    is_safety_diverted: bool = Field(
        default=False,
        description="Indicates whether the turn bypassed standard generation to direct immediate crisis/emergency support."
    )
    fallback_triggered: bool = Field(
        default=False,
        description="Indicates whether a safe fallback was returned due to generator failure or unsafe response."
    )
    fallback_reason: Optional[str] = Field(
        default=None,
        description="Reason code for fallback trigger (e.g. GENERATOR_ERROR, UNSAFE_OUTPUT_BLOCKED)."
    )

    model_config = ConfigDict(frozen=True)
