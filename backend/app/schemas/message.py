from datetime import datetime
from typing import List, Literal, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.schemas.orchestrator import SourceProvenance


class MessageCreate(BaseModel):
    """Schema for submitting a message to a conversation.

    Clients may only submit 'user' messages. Assistant messages are generated
    server-side through the orchestrator pipeline.
    """

    role: Literal["user"] = Field(
        default="user",
        description="Message sender role. Clients may only submit 'user' messages."
    )
    content: str = Field(
        ...,
        min_length=1,
        description="Text content of the message."
    )

    @field_validator("content")
    @classmethod
    def validate_content_not_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Message content cannot be empty or blank.")
        return stripped


class MessageResponse(BaseModel):
    """Schema for message API responses."""

    id: UUID
    conversation_id: UUID
    role: str
    content: str
    created_at: datetime
    assistant_reply: Optional["MessageResponse"] = Field(
        default=None,
        description="Server-generated assistant response for user dialogue turns."
    )
    sources: List[SourceProvenance] = Field(
        default_factory=list,
        description="Source provenance of retrieved knowledge chunks if applicable."
    )
    is_safety_diverted: bool = Field(
        default=False,
        description="Whether the turn bypassed ordinary generation to provide immediate crisis resources."
    )

    model_config = ConfigDict(from_attributes=True)
