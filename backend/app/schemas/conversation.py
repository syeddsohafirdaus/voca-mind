from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.message import MessageResponse


class ConversationCreate(BaseModel):
    """Schema for initiating a conversation.
    
    Authentication is not implemented in Sprint 1. 
    user_id is optional; if omitted, a temporary user ID strategy is used.
    """

    user_id: Optional[UUID] = Field(
        default=None,
        description="Optional temporary user ID for testing. If omitted, a default dev user is created."
    )


class ConversationResponse(BaseModel):
    """Schema for conversation API responses."""

    id: UUID
    user_id: UUID
    started_at: datetime
    ended_at: Optional[datetime] = None
    messages: List[MessageResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
