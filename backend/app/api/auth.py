
"""Voca Mind account registration and authentication endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_firebase_identity
from app.database import get_db
from app.models.doctor_application import DoctorApplication
from app.models.user import User
from app.schemas.registration import (
    ClientRegistration,
    DoctorRegistration,
    GuardianRegistration,
    RegistrationResponse,
)


router = APIRouter()


# =========================================================
# SHARED REGISTRATION HELPERS
# =========================================================

async def ensure_not_registered(
    firebase_uid: str,
    db: AsyncSession,
) -> None:
    """
    Prevent duplicate registrations and unauthorized role switching.
    """

    result = await db.execute(
        select(User.id).where(User.firebase_uid == firebase_uid)
    )

    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This Firebase account is already registered",
        )


async def save_new_user(
    user: User,
    db: AsyncSession,
) -> RegistrationResponse:
    """
    Save a new Client or Guardian account.
    """

    db.add(user)

    try:
        await db.commit()
        await db.refresh(user)

    except IntegrityError:
        await db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This Firebase account is already registered",
        )

    return RegistrationResponse.model_validate(user)


# =========================================================
# CLIENT REGISTRATION
# =========================================================

@router.post(
    "/register/client",
    response_model=RegistrationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register Client",
)
async def register_client(
    payload: ClientRegistration,
    firebase_uid: str = Depends(get_firebase_identity),
    db: AsyncSession = Depends(get_db),
) -> RegistrationResponse:
    """
    Register a Firebase-authenticated Client aged 18 to 30.

    Age eligibility is validated by ClientRegistration.
    """

    await ensure_not_registered(firebase_uid, db)

    user = User(
        firebase_uid=firebase_uid,
        role="client",
        display_name=payload.display_name.strip(),
        date_of_birth=payload.date_of_birth,
        account_status="active",
        is_verified=False,
    )

    return await save_new_user(user, db)


# =========================================================
# GUARDIAN REGISTRATION
# =========================================================

@router.post(
    "/register/guardian",
    response_model=RegistrationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register Guardian",
)
async def register_guardian(
    payload: GuardianRegistration,
    firebase_uid: str = Depends(get_firebase_identity),
    db: AsyncSession = Depends(get_db),
) -> RegistrationResponse:
    """
    Register a Guardian account.

    Registration does not grant access to Client conversations,
    private messages, or wellbeing information.

    Guardian access requires separate Client authorization.
    """

    await ensure_not_registered(firebase_uid, db)

    user = User(
        firebase_uid=firebase_uid,
        role="guardian",
        display_name=payload.display_name.strip(),
        account_status="active",
        is_verified=False,
    )

    return await save_new_user(user, db)


# =========================================================
# DOCTOR REGISTRATION
# =========================================================

@router.post(
    "/register/doctor",
    response_model=RegistrationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Apply for Doctor Registration",
)
async def register_doctor(
    payload: DoctorRegistration,
    firebase_uid: str = Depends(get_firebase_identity),
    db: AsyncSession = Depends(get_db),
) -> RegistrationResponse:
    """
    Create a pending Doctor account and application.

    Professional privileges require authorized verification.
    """

    await ensure_not_registered(firebase_uid, db)

    user = User(
        firebase_uid=firebase_uid,
        role="doctor",
        display_name=payload.display_name.strip(),
        account_status="pending",
        is_verified=False,
    )

    db.add(user)

    try:
        # Generate the user ID before creating the application.
        await db.flush()

        application = DoctorApplication(
            user_id=user.id,
            registration_number=payload.registration_number.strip(),
            licensing_authority=payload.licensing_authority.strip(),
            specialization=payload.specialization.strip(),
            status="pending",
            created_at=datetime.now(timezone.utc),
        )

        db.add(application)

        # Save both records in one database transaction.
        await db.commit()
        await db.refresh(user)

    except IntegrityError:
        await db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This Firebase account is already registered",
        )

    return RegistrationResponse.model_validate(user)


# =========================================================
# CURRENT ACCOUNT LOOKUP
# =========================================================

@router.get(
    "/me",
    response_model=RegistrationResponse,
    summary="Get Current Account",
)
async def get_my_account(
    firebase_uid: str = Depends(get_firebase_identity),
    db: AsyncSession = Depends(get_db),
) -> RegistrationResponse:
    """
    Return the authenticated user's Voca Mind account.

    HTTP 200:
        Existing active or pending account.

    HTTP 404:
        Valid Firebase user without Voca Mind registration.

    HTTP 403:
        Suspended account, invalid role, or invalid status.

    The endpoint never creates accounts automatically.
    """

    result = await db.execute(
        select(User).where(User.firebase_uid == firebase_uid)
    )

    user = result.scalar_one_or_none()

    # Firebase user exists, but Voca Mind registration
    # has not been completed.
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Voca Mind registration is required",
        )

    # Suspended accounts must not proceed.
    if user.account_status == "suspended":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been suspended",
        )

    # Only supported account statuses are accepted.
    if user.account_status not in {"active", "pending"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account status is invalid",
        )

    # Only supported roles are accepted.
    if user.role not in {"client", "doctor", "guardian"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account role is invalid",
        )

    return RegistrationResponse.model_validate(user)
