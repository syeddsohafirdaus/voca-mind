"""Service handling Client-controlled Guardian authorization."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.logger import logger
from app.models.guardian_authorization import GuardianAuthorization
from app.models.user import User


class GuardianService:
    """Service handling business logic for Client-controlled Guardian authorizations."""

    @staticmethod
    async def grant_authorization(
        db: AsyncSession,
        client: User,
        guardian_id: uuid.UUID,
    ) -> GuardianAuthorization:
        """
        Grant explicit authorization to a registered Guardian.

        Requirements enforced:
        1. Only active clients can authorize (enforced via require_role(["client"])).
        2. Guardians cannot authorize themselves (client_id != guardian_id).
        3. Selected guardian must exist, have role 'guardian', and have status 'active'.
        4. Reauthorizes previously revoked authorizations seamlessly.
        5. Prevents duplicate active authorizations (HTTP 409).
        6. Handles concurrency safely via database integrity check and rollback.
        """
        # 1. Prevent self-authorization
        if client.id == guardian_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Clients cannot authorize themselves as guardians.",
            )

        # 2. Verify selected guardian exists, is active, and has the guardian role
        guardian_stmt = select(User).where(User.id == guardian_id)
        guardian_result = await db.execute(guardian_stmt)
        guardian = guardian_result.scalar_one_or_none()

        if guardian is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Guardian account not found.",
            )

        if guardian.role != "guardian":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The selected user does not have the guardian role.",
            )

        if guardian.account_status != "active":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The guardian account is not active.",
            )

        # 3. Check for existing authorization between this client and guardian
        existing_stmt = select(GuardianAuthorization).where(
            GuardianAuthorization.client_id == client.id,
            GuardianAuthorization.guardian_id == guardian_id,
        )
        existing_result = await db.execute(existing_stmt)
        existing_auth = existing_result.scalar_one_or_none()

        now = datetime.now(timezone.utc)

        if existing_auth is not None:
            if existing_auth.status == "active":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="An active authorization already exists for this guardian.",
                )

            # Reauthorization after revocation: reactivate existing record
            existing_auth.status = "active"
            existing_auth.consented_at = now
            existing_auth.revoked_at = None

            try:
                await db.commit()
                await db.refresh(existing_auth)
            except IntegrityError:
                await db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A conflicting authorization operation is already in progress.",
                )

            logger.info(
                f"Client {client.id} re-authorized guardian {guardian_id}."
            )
            return existing_auth

        # 4. Create new authorization
        new_auth = GuardianAuthorization(
            client_id=client.id,
            guardian_id=guardian_id,
            status="active",
            consented_at=now,
            created_at=now,
        )
        db.add(new_auth)

        try:
            await db.commit()
            await db.refresh(new_auth)
        except IntegrityError:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An authorization for this guardian already exists or is being processed.",
            )

        logger.info(
            f"Client {client.id} granted authorization to guardian {guardian_id}."
        )
        return new_auth

    @staticmethod
    async def list_authorizations(
        db: AsyncSession,
        client_id: uuid.UUID,
        status_filter: Optional[str] = None,
    ) -> list[tuple[GuardianAuthorization, Optional[str]]]:
        """
        List all Guardian authorizations belonging to the authenticated Client.

        Never returns authorizations belonging to other clients.
        Includes the guardian's display_name for client transparency.
        """
        stmt = (
            select(GuardianAuthorization, User.display_name)
            .join(User, GuardianAuthorization.guardian_id == User.id)
            .where(GuardianAuthorization.client_id == client_id)
        )

        if status_filter is not None:
            stmt = stmt.where(GuardianAuthorization.status == status_filter)

        stmt = stmt.order_by(GuardianAuthorization.created_at.desc())
        result = await db.execute(stmt)
        return list(result.all())

    @staticmethod
    async def revoke_authorization_by_id(
        db: AsyncSession,
        client_id: uuid.UUID,
        authorization_id: uuid.UUID,
    ) -> GuardianAuthorization:
        """
        Revoke an authorization by its authorization ID.

        Enforces ownership: clients can only revoke their own authorizations.
        Sets status='revoked' and revoked_at timestamp immediately.
        """
        stmt = select(GuardianAuthorization).where(
            GuardianAuthorization.id == authorization_id,
            GuardianAuthorization.client_id == client_id,
        )
        result = await db.execute(stmt)
        auth = result.scalar_one_or_none()

        if auth is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Guardian authorization not found.",
            )

        if auth.status == "revoked":
            # Idempotent return if already revoked
            return auth

        now = datetime.now(timezone.utc)
        auth.status = "revoked"
        auth.revoked_at = now

        await db.commit()
        await db.refresh(auth)

        logger.info(
            f"Client {client_id} revoked authorization {authorization_id}."
        )
        return auth

    @staticmethod
    async def revoke_authorization_by_guardian_id(
        db: AsyncSession,
        client_id: uuid.UUID,
        guardian_id: uuid.UUID,
    ) -> GuardianAuthorization:
        """
        Revoke an authorization directly by Guardian user ID.

        Enforces ownership: clients can only revoke their own authorizations.
        Sets status='revoked' and revoked_at timestamp immediately.
        """
        stmt = select(GuardianAuthorization).where(
            GuardianAuthorization.guardian_id == guardian_id,
            GuardianAuthorization.client_id == client_id,
        )
        result = await db.execute(stmt)
        auth = result.scalar_one_or_none()

        if auth is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Guardian authorization not found for this guardian.",
            )

        if auth.status == "revoked":
            return auth

        now = datetime.now(timezone.utc)
        auth.status = "revoked"
        auth.revoked_at = now

        await db.commit()
        await db.refresh(auth)

        logger.info(
            f"Client {client_id} revoked authorization for guardian {guardian_id}."
        )
        return auth

    @staticmethod
    async def is_guardian_authorized(
        db: AsyncSession,
        client_id: uuid.UUID,
        guardian_id: uuid.UUID,
    ) -> bool:
        """
        Check if an active authorization exists from client to guardian.
        """
        stmt = select(GuardianAuthorization.id).where(
            GuardianAuthorization.client_id == client_id,
            GuardianAuthorization.guardian_id == guardian_id,
            GuardianAuthorization.status == "active",
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none() is not None
