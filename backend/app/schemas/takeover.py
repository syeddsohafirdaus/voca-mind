"""Human takeover request and response schemas."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StrictBool, field_validator


class TakeoverRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    consent: StrictBool

    @field_validator("consent")
    @classmethod
    def require_consent(cls, value):
        if value is not True:
            raise ValueError("Explicit consent is required")
        return value


class TakeoverResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    assignment_id: UUID
    status: Literal[
        "requested", "active", "cancelled", "ended"
    ]
    consented_at: datetime
    accepted_at: datetime | None = None
    ended_at: datetime | None = None
    created_at: datetime
