"""Voca Mind Guardian authorization endpoints.

Allows active Clients to securely grant, list, and revoke authorizations for Guardians.
Guardians never receive access to Clients' private AI conversations or message contents.
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.database import get_db
from app.models.user import User
from app.schemas.guardian import (
    GrantGuardianAuthorizationRequest,
    GuardianAuthorizationResponse,
)
from app.services.guardian_service import GuardianService

router = APIRouter()

# All endpoints in this router require an active client account.
# Guardians and doctors cannot grant or manipulate authorizations.
get_current_client = require_role(["client"])


@router.post(
    "/authorizations",
    response_model=GuardianAuthorizationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Grant Guardian Authorization",
    description=(
        "Explicitly grants authorization to a registered, active Guardian. "
        "Identity is extracted from the verified Firebase Bearer token. "
        "Guardians cannot authorize themselves, and duplicate active authorizations "
        "are safely prevented."
    ),
)
@router.post(
    "",
    response_model=GuardianAuthorizationResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
async def grant_guardian_authorization(
    payload: GrantGuardianAuthorizationRequest,
    current_user: User = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> GuardianAuthorizationResponse:
    """Grant authorization to a registered Guardian."""
    auth = await GuardianService.grant_authorization(
        db=db,
        client=current_user,
        guardian_id=payload.guardian_id,
    )

    # Retrieve guardian display name for UI response
    guardian_name = await db.scalar(
        select(User.display_name).where(User.id == payload.guardian_id)
    )

    resp = GuardianAuthorizationResponse.model_validate(auth)
    resp.guardian_display_name = guardian_name
    return resp


@router.get(
    "/authorizations",
    response_model=list[GuardianAuthorizationResponse],
    status_code=status.HTTP_200_OK,
    summary="List Guardian Authorizations",
    description=(
        "Retrieves all Guardian authorizations granted by the authenticated Client. "
        "Never returns authorizations belonging to other Clients."
    ),
)
@router.get(
    "",
    response_model=list[GuardianAuthorizationResponse],
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def list_guardian_authorizations(
    status_filter: Optional[str] = Query(
        None,
        alias="status",
        description="Filter by authorization status ('active' or 'revoked')",
    ),
    current_user: User = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> list[GuardianAuthorizationResponse]:
    """List the authenticated Client's Guardian authorizations."""
    rows = await GuardianService.list_authorizations(
        db=db,
        client_id=current_user.id,
        status_filter=status_filter,
    )

    authorizations: list[GuardianAuthorizationResponse] = []
    for auth, guardian_name in rows:
        resp = GuardianAuthorizationResponse.model_validate(auth)
        resp.guardian_display_name = guardian_name
        authorizations.append(resp)

    return authorizations


@router.post(
    "/authorizations/{authorization_id}/revoke",
    response_model=GuardianAuthorizationResponse,
    status_code=status.HTTP_200_OK,
    summary="Revoke Guardian Authorization by ID",
    description=(
        "Immediately revokes an active authorization by authorization ID. "
        "Enforces ownership: Clients can only revoke their own authorizations."
    ),
)
@router.delete(
    "/authorizations/{authorization_id}",
    response_model=GuardianAuthorizationResponse,
    status_code=status.HTTP_200_OK,
    summary="Revoke Guardian Authorization via DELETE",
    description="Revoke an authorization using standard REST DELETE semantics.",
)
async def revoke_authorization_by_id(
    authorization_id: uuid.UUID,
    current_user: User = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> GuardianAuthorizationResponse:
    """Revoke Guardian authorization by authorization ID."""
    auth = await GuardianService.revoke_authorization_by_id(
        db=db,
        client_id=current_user.id,
        authorization_id=authorization_id,
    )

    guardian_name = await db.scalar(
        select(User.display_name).where(User.id == auth.guardian_id)
    )

    resp = GuardianAuthorizationResponse.model_validate(auth)
    resp.guardian_display_name = guardian_name
    return resp


@router.post(
    "/{guardian_id}/revoke",
    response_model=GuardianAuthorizationResponse,
    status_code=status.HTTP_200_OK,
    summary="Revoke Guardian Authorization by Guardian ID",
    description="Convenience endpoint to revoke authorization directly using the Guardian's user ID.",
)
async def revoke_authorization_by_guardian_id(
    guardian_id: uuid.UUID,
    current_user: User = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> GuardianAuthorizationResponse:
    """Revoke Guardian authorization directly by Guardian ID."""
    auth = await GuardianService.revoke_authorization_by_guardian_id(
        db=db,
        client_id=current_user.id,
        guardian_id=guardian_id,
    )

    guardian_name = await db.scalar(
        select(User.display_name).where(User.id == auth.guardian_id)
    )

    resp = GuardianAuthorizationResponse.model_validate(auth)
    resp.guardian_display_name = guardian_name
    return resp
