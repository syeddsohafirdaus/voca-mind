from typing import Any, Dict
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.firebase import verify_firebase_id_token
from app.database import get_db
from app.logger import logger
from app.models.user import User

security_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """FastAPI dependency that extracts, verifies Firebase ID token from Authorization header,
    and returns the corresponding database User model instance.
    
    Creates a new database User record if it's the user's first authenticated request.
    Returns 401 Unauthorized for missing, malformed, or invalid tokens.
    
    Security: NEVER logs ID tokens or Authorization headers.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    raw_token = parts[1].strip()

    try:
        decoded_token: Dict[str, Any] = verify_firebase_id_token(raw_token)
    except Exception:
        # Operational logging without logging raw tokens or headers
        logger.warning(f"Failed authentication attempt on {request.method} {request.url.path}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    firebase_uid = decoded_token.get("uid")
    if not firebase_uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Query database for existing user matching firebase_uid
    stmt = select(User).where(User.firebase_uid == firebase_uid)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        # Register new authenticated user in database
        user = User(firebase_uid=firebase_uid)
        db.add(user)
        await db.commit()
        await db.refresh(user)

    return user
