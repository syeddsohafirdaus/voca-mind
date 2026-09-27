from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.message import MessageResponse


class ConversationCreate(BaseModel):
    """Schema for initiating a conversation.
    
    Authenticated user identity is verified via Firebase Bearer token.
    Client payloads cannot override user identity.
    """
    pass


class ConversationResponse(BaseModel):
    """Schema for conversation API responses."""

    id: UUID
    user_id: UUID
    started_at: datetime
    ended_at: Optional[datetime] = None
    messages: List[MessageResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
