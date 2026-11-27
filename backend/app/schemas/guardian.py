"""Pydantic schemas for Client-controlled Guardian authorization."""

import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator


class GrantGuardianAuthorizationRequest(BaseModel):
    """Payload to grant authorization to an existing registered Guardian."""

    model_config = ConfigDict(extra="forbid")

    consent: StrictBool

    @field_validator("consent")
    @classmethod
    def require_explicit_consent(cls, value):
        if value is not True:
            raise ValueError("Explicit consent is required")
        return value

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
    consent_version: uuid.UUID

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





class WellbeingShareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    wellbeing: Literal[
        "doing_well",
        "managing",
        "would_like_support",
    ]

    consent: StrictBool


class WellbeingShareResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    authorization_id: uuid.UUID
    wellbeing: Literal[
        "doing_well",
        "managing",
        "would_like_support",
    ]
    shared_at: datetime


class GuardianDashboardItem(BaseModel):
    authorization_id: uuid.UUID
    client_display_name: Optional[str] = None
    wellbeing: Optional[
        Literal[
            "doing_well",
            "managing",
            "would_like_support",
        ]
    ] = None
    shared_at: Optional[datetime] = None
