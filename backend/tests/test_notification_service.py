"""Tests for privacy-preserving notification operations."""

import pytest
from datetime import timezone
from uuid import UUID, uuid4


from app.services.notification_service import (
    ALLOWED_EVENTS,
    create_notification,
    list_notifications,
    count_unread_notifications,
    mark_notification_read,
)

from sqlalchemy import select
from app.models.user import User
from tests.conftest import TestAsyncSessionLocal


async def register_client(client, token):
    response = await client.post(
        "/api/v1/auth/register/client",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "display_name": "Synthetic Client",
            "date_of_birth": "2003-01-15",
        },
    )
    assert response.status_code == 201

    async with TestAsyncSessionLocal() as db:
        result = await db.execute(
            select(User.id).where(
                User.firebase_uid == f"uid-{token}"
            )
        )
        return str(result.scalar_one())



@pytest.mark.asyncio
@pytest.mark.parametrize("event_type", sorted(ALLOWED_EVENTS))
async def test_create_notification(client, event_type):
    uid = UUID(await register_client(client, "notify-client"))

    async with TestAsyncSessionLocal() as db:
        notification = await create_notification(
            db,
            recipient_id=uid,
            event_type=event_type,
        )

        assert notification.id is not None
        assert notification.recipient_id == uid
        assert notification.event_type == event_type
        assert notification.read_at is None
        assert notification.created_at is not None

        await db.commit()


@pytest.mark.asyncio
async def test_invalid_notification_event(client):
    uid = UUID(await register_client(client, "notify-client"))

    async with TestAsyncSessionLocal() as db:
        with pytest.raises(ValueError):
            await create_notification(
                db,
                recipient_id=uid,
                event_type="invalid_event",
            )


@pytest.mark.asyncio
async def test_notification_recipient_isolation(client):
    first = UUID(await register_client(client, "notify-first"))
    second = UUID(await register_client(client, "notify-second"))

    async with TestAsyncSessionLocal() as db:
        notification = await create_notification(
            db,
            recipient_id=first,
            event_type="support_requested",
        )

        await db.commit()

        own = await list_notifications(db, first)
        other = await list_notifications(db, second)

        assert len(own) == 1
        assert own[0].id == notification.id
        assert other == []

        assert await count_unread_notifications(db, first) == 1
        assert await count_unread_notifications(db, second) == 0

        result = await mark_notification_read(
            db,
            recipient_id=second,
            notification_id=notification.id,
        )

        assert result is None
        assert notification.read_at is None


@pytest.mark.asyncio
async def test_notification_read_status(client):
    uid = UUID(await register_client(client, "notify-client"))

    async with TestAsyncSessionLocal() as db:
        notification = await create_notification(
            db,
            recipient_id=uid,
            event_type="assignment_proposed",
        )

        await db.commit()

        assert await count_unread_notifications(db, uid) == 1

        result = await mark_notification_read(
            db,
            recipient_id=uid,
            notification_id=notification.id,
        )

        assert result.read_at is not None
        original_read_at = result.read_at

        await db.commit()

        assert await count_unread_notifications(db, uid) == 0
        assert await list_notifications(
            db, uid, unread_only=True
        ) == []

        result = await mark_notification_read(
            db,
            recipient_id=uid,
            notification_id=notification.id,
        )

        assert result.read_at is not None

        actual = result.read_at
        if actual.tzinfo is None:
            actual = actual.replace(tzinfo=timezone.utc)

        assert actual == original_read_at


@pytest.mark.asyncio
async def test_missing_notification(client):
    uid = UUID(await register_client(client, "notify-client"))

    async with TestAsyncSessionLocal() as db:
        result = await mark_notification_read(
            db,
            recipient_id=uid,
            notification_id=uuid4(),
        )

        assert result is None
