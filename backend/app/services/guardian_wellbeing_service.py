"""Privacy-preserving guardian wellbeing service."""

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select, delete
from sqlalchemy.orm import aliased

from app.models.user import User
from app.models.guardian_authorization import GuardianAuthorization
from app.models.guardian_wellbeing import GuardianWellbeing


async def lock_owned_authorization(db, client_id, authorization_id, consent_version):
    result = await db.execute(
        select(GuardianAuthorization)
        .where(
            GuardianAuthorization.id == authorization_id,
            GuardianAuthorization.client_id == client_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )

    authorization = result.scalar_one_or_none()

    if authorization is None:
        raise HTTPException(404, "Authorization not found")

    if authorization.consent_version != consent_version:
        raise HTTPException(
            409, "Guardian consent version has changed."
        )

    return authorization


async def share_wellbeing(
    db, client_id, authorization_id, wellbeing, consent_version
):
    authorization = await lock_owned_authorization(
        db, client_id, authorization_id, consent_version
    )

    if authorization.status != "active":
        raise HTTPException(403, "Authorization is not active")

    client = await db.scalar(
        select(User)
        .where(
            User.id == client_id,
            User.role == "client",
            User.account_status == "active",
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )

    if client is None:
        raise HTTPException(403, "Client is not active")

    guardian = await db.scalar(
        select(User)
        .where(
            User.id == authorization.guardian_id,
            User.role == "guardian",
            User.account_status == "active",
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )

    if guardian is None:
        raise HTTPException(403, "Guardian is not active")

    update = await db.get(
        GuardianWellbeing, authorization.id
    )

    now = datetime.now(timezone.utc)

    if update is None:
        update = GuardianWellbeing(
            authorization_id=authorization.id,
            wellbeing=wellbeing,
            shared_at=now,
        )
        db.add(update)
    else:
        update.wellbeing = wellbeing
        update.shared_at = now

    await db.commit()
    await db.refresh(update)

    return update


async def clear_wellbeing(db, client_id, authorization_id, consent_version):
    authorization = await lock_owned_authorization(
        db, client_id, authorization_id, consent_version
    )

    await db.execute(
        delete(GuardianWellbeing).where(
            GuardianWellbeing.authorization_id
            == authorization.id
        )
    )

    await db.commit()


async def list_guardian_dashboard(
    db, guardian_id, limit=50, offset=0
):
    guardian = aliased(User)

    result = await db.execute(
        select(
            GuardianAuthorization.id,
            User.display_name,
            GuardianWellbeing.wellbeing,
            GuardianWellbeing.shared_at,
        )
        .join(
            User,
            User.id == GuardianAuthorization.client_id,
        )
        .join(
            guardian,
            guardian.id == GuardianAuthorization.guardian_id,
        )
        .outerjoin(
            GuardianWellbeing,
            GuardianWellbeing.authorization_id
            == GuardianAuthorization.id,
        )
        .where(
            GuardianAuthorization.guardian_id == guardian_id,
            GuardianAuthorization.status == "active",
            GuardianAuthorization.revoked_at.is_(None),
            User.role == "client",
            User.account_status == "active",
            guardian.role == "guardian",
            guardian.account_status == "active",
        )
        .order_by(
            GuardianAuthorization.created_at.desc(),
            GuardianAuthorization.id.desc(),
        )
        .offset(offset)
        .limit(limit)
    )

    return [
        {
            "authorization_id": row[0],
            "client_display_name": row[1],
            "wellbeing": row[2],
            "shared_at": row[3],
        }
        for row in result.all()
    ]
