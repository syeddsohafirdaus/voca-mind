from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator


class MessageCreate(BaseModel):
    """Schema for creating a message in a conversation."""

    role: Literal["user", "assistant"] = Field(
        ...,
        description="Message sender role. Must be 'user' or 'assistant'."
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

    model_config = ConfigDict(from_attributes=True)
