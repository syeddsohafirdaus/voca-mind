"""Pydantic schemas for Client-controlled Guardian authorization."""

import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class GrantGuardianAuthorizationRequest(BaseModel):
    """Payload to grant authorization to an existing registered Guardian."""

    guardian_id: uuid.UUID = Field(
        ...,
        description="Unique identifier of the registered Guardian to authorize",
    )


# Alias for backward/alternative schema naming compatibility
GuardianAuthorizationCreate = GrantGuardianAuthorizationRequest


class GuardianSummary(BaseModel):
    """Public details of an authorized Guardian."""

    id: uuid.UUID
    display_name: Optional[str] = None
    role: str = "guardian"

    model_config = ConfigDict(from_attributes=True)


class GuardianAuthorizationResponse(BaseModel):
    """Guardian authorization record returned to Clients."""

    id: uuid.UUID
    client_id: uuid.UUID
    guardian_id: uuid.UUID
    status: Literal["active", "revoked"]
    consented_at: datetime
    revoked_at: Optional[datetime] = None
    created_at: datetime
    guardian_display_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
