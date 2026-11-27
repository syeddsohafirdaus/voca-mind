
"""Firebase authentication and role-based authorization dependencies."""

from typing import Any, Dict, Iterable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.firebase import verify_firebase_id_token
from app.database import get_db
from app.logger import logger
from app.models.user import User
from app.models.doctor_application import DoctorApplication


security_scheme = HTTPBearer(auto_error=False)

VALID_ROLES = frozenset({"client", "doctor", "guardian"})


async def get_firebase_identity(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(
        security_scheme
    ),
) -> str:
    """
    Verify Firebase authentication without creating a database account.

    Returns the verified Firebase UID.
    """

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        decoded_token: Dict[str, Any] = verify_firebase_id_token(
            credentials.credentials
        )
    except Exception:
        logger.warning(
            f"Failed authentication attempt on "
            f"{request.method} {request.url.path}"
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    firebase_uid = decoded_token.get("uid")

    if not isinstance(firebase_uid, str) or not firebase_uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return firebase_uid


async def get_current_user(
    firebase_uid: str = Depends(get_firebase_identity),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Return an existing registered user.

    Never create accounts automatically.
    """

    result = await db.execute(
        select(User).where(User.firebase_uid == firebase_uid)
    )

    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Registration is required before accessing this feature",
        )

    if user.account_status == "suspended":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been suspended",
        )

    if user.account_status not in {"active", "pending"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account status is invalid",
        )

    if user.role not in VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account role is invalid",
        )

    return user


def require_role(allowed_roles: Iterable[str]):
    """Require an active account with an allowed role."""

    roles = frozenset(allowed_roles)

    if not roles or not roles.issubset(VALID_ROLES):
        raise ValueError("Invalid allowed roles")

    async def role_dependency(
        current_user: User = Depends(get_current_user),
    ) -> User:

        if current_user.account_status != "active":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is not active",
            )

        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource",
            )

        return current_user

    return role_dependency


def require_verified_doctor():
    """Require an active, verified Doctor account."""

    async def verified_doctor_dependency(
        current_user: User = Depends(require_role(["doctor"])),
        db: AsyncSession = Depends(get_db),
    ) -> User:

        if not current_user.is_verified:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Professional verification is required",
            )

        result = await db.execute(
            select(DoctorApplication).where(
                DoctorApplication.user_id == current_user.id,
                DoctorApplication.status == "approved",
                DoctorApplication.reviewed_at.is_not(None),
            )
        )

        application = result.scalar_one_or_none()

        if application is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Approved professional application is required",
            )

        return current_user

    return verified_doctor_dependency
