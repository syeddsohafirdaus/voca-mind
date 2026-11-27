
"""Registration request and response schemas for Voca Mind."""

import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def calculate_age(date_of_birth: date) -> int:
    """Calculate age in completed years."""
    today = date.today()

    return (
        today.year
        - date_of_birth.year
        - (
            (today.month, today.day)
            < (date_of_birth.month, date_of_birth.day)
        )
    )


class ClientRegistration(BaseModel):
    """Client registration for adults aged 18 to 30."""

    display_name: str = Field(
        min_length=2,
        max_length=150,
    )
    date_of_birth: date

    @field_validator("date_of_birth")
    @classmethod
    def validate_age(cls, value: date) -> date:
        age = calculate_age(value)

        if not 18 <= age <= 30:
            raise ValueError(
                "Client registration is available only "
                "for adults aged 18 to 30."
            )

        return value


class DoctorRegistration(BaseModel):
    """Professional application; approval is required."""

    display_name: str = Field(
        min_length=2,
        max_length=150,
    )
    registration_number: str = Field(
        min_length=3,
        max_length=100,
    )
    licensing_authority: str = Field(
        min_length=3,
        max_length=150,
    )
    specialization: str = Field(
        min_length=3,
        max_length=150,
    )


class GuardianRegistration(BaseModel):
    """Guardian registration without automatic client access."""

    display_name: str = Field(
        min_length=2,
        max_length=150,
    )


class RegistrationResponse(BaseModel):
    id: uuid.UUID

    """Safe account information returned after registration."""

    model_config = ConfigDict(from_attributes=True)

    role: Literal["client", "doctor", "guardian"]
    display_name: str | None
    account_status: Literal["pending", "active", "suspended"]
    is_verified: bool
