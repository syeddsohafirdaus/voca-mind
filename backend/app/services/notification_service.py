"""Privacy-preserving notification operations."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification


ALLOWED_EVENTS = frozenset({
    "support_requested",
    "assignment_proposed",
    "assignment_accepted",
    "assignment_revoked",
    "assignment_completed",
    "professional_message",
    "takeover_requested",
    "takeover_accepted",
    "takeover_cancelled",
    "takeover_ended",
})


async def create_notification(
    db: AsyncSession,
    *,
    recipient_id: UUID,
    event_type: str,
    reference_id: UUID | None = None,
) -> Notification:

    if event_type not in ALLOWED_EVENTS:
        raise ValueError("Invalid notification event type")

    notification = Notification(
        recipient_id=recipient_id,
        event_type=event_type,
        reference_id=reference_id,
    )

    db.add(notification)
    await db.flush()

    return notification


async def list_notifications(
    db: AsyncSession,
    recipient_id: UUID,
    *,
    limit: int = 50,
    offset: int = 0,
    unread_only: bool = False,
) -> list[Notification]:

    query = select(Notification).where(
        Notification.recipient_id == recipient_id
    )

    if unread_only:
        query = query.where(
            Notification.read_at.is_(None)
        )

    query = query.order_by(
        Notification.created_at.desc(),
        Notification.id.desc(),
    ).offset(offset).limit(limit)

    result = await db.execute(query)

    return list(result.scalars().all())


async def count_unread_notifications(
    db: AsyncSession,
    recipient_id: UUID,
) -> int:

    result = await db.execute(
        select(func.count(Notification.id)).where(
            Notification.recipient_id == recipient_id,
            Notification.read_at.is_(None),
        )
    )

    return int(result.scalar_one())


async def mark_notification_read(
    db: AsyncSession,
    *,
    recipient_id: UUID,
    notification_id: UUID,
) -> Notification | None:

    result = await db.execute(
        select(Notification)
        .where(
            Notification.id == notification_id,
            Notification.recipient_id == recipient_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )

    notification = result.scalar_one_or_none()

    if notification is None:
        return None

    if notification.read_at is None:
        notification.read_at = datetime.now(timezone.utc)
        await db.flush()

    return notification
