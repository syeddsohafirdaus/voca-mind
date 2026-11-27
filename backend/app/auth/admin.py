"""Restricted platform administrator authorization."""

from fastapi import Depends, HTTPException, status

from app.auth.dependencies import get_firebase_identity
from app.config import settings


def get_admin_uids() -> frozenset[str]:
    """Return explicitly configured administrator identities."""

    return frozenset(
        uid.strip()
        for uid in settings.PLATFORM_ADMIN_UIDS.split(",")
        if uid.strip()
    )


async def require_platform_admin(
    firebase_uid: str = Depends(get_firebase_identity),
) -> str:
    """Require a trusted Firebase administrator identity."""

    if firebase_uid not in get_admin_uids():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform administrator access is required",
        )

    return firebase_uid
