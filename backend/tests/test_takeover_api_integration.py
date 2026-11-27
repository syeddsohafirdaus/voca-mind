"""Integration tests for server-controlled takeover routing."""

from uuid import UUID

import pytest

from app.config import settings
from app.services.human_takeover_service import (
    request_takeover,
    accept_takeover,
    cancel_takeover,
    end_takeover,
)
from app.services.conversation_orchestrator import (
    HUMAN_TAKEOVER_RESPONSE,
)
from app.safety.check_in import SAFETY_CHECK_IN_QUESTION

from tests.conftest import TestAsyncSessionLocal
from tests.test_notification_lifecycle import (
    setup_case,
    propose,
    accept,
    CLIENT,
)

CONVERSATIONS = "/api/v1/conversations"


@pytest.fixture(autouse=True)
def configure_admin(monkeypatch):
    monkeypatch.setattr(
        settings,
        "PLATFORM_ADMIN_UIDS",
        "uid-assignment-admin",
    )


async def prepare_case(client, takeover_status=None):
    client_id, doctor_id = await setup_case(client)

    assignment_id = await propose(
        client, client_id, doctor_id
    )

    await accept(client, assignment_id)

    if takeover_status is not None:
        async with TestAsyncSessionLocal() as db:
            takeover = await request_takeover(
                db, UUID(assignment_id)
            )

            if takeover_status in ("active", "ended"):
                await accept_takeover(db, takeover)

            if takeover_status == "cancelled":
                await cancel_takeover(db, takeover)

            if takeover_status == "ended":
                await end_takeover(db, takeover)

            await db.commit()

    response = await client.post(
        CONVERSATIONS,
        headers=CLIENT,
        json={},
    )

    assert response.status_code == 201

    return response.json()["id"], assignment_id


async def send_message(client, conversation_id, content, **extra):
    response = await client.post(
        f"{CONVERSATIONS}/{conversation_id}/messages",
        headers=CLIENT,
        json={
            "role": "user",
            "content": content,
            **extra,
        },
    )

    assert response.status_code == 201
    return response.json()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "takeover_status",
    [None, "requested", "cancelled", "ended", "active"],
)
async def test_api_takeover_routing(client, takeover_status):
    conversation_id, _ = await prepare_case(
        client, takeover_status
    )

    result = await send_message(
        client, conversation_id, "I had a busy day."
    )

    expected = takeover_status == "active"

    assert result["is_human_takeover"] is expected
    assert result["is_safety_diverted"] is False

    if expected:
        assert (
            result["assistant_reply"]["content"]
            == HUMAN_TAKEOVER_RESPONSE
        )
        assert result["sources"] == []


@pytest.mark.asyncio
async def test_api_crisis_priority(client):
    conversation_id, _ = await prepare_case(
        client, "active"
    )

    result = await send_message(
        client,
        conversation_id,
        "I want to die.",
    )

    assert result["is_safety_diverted"] is True
    assert result["is_human_takeover"] is False
    assert "112" in result["assistant_reply"]["content"]


@pytest.mark.asyncio
async def test_api_concern_check_in(client):
    conversation_id, _ = await prepare_case(
        client, "active"
    )

    result = await send_message(
        client,
        conversation_id,
        "I feel hopeless.",
    )

    assert result["is_human_takeover"] is True

    assert (
        SAFETY_CHECK_IN_QUESTION
        in result["assistant_reply"]["content"]
    )


@pytest.mark.asyncio
async def test_client_cannot_force_takeover(client):
    conversation_id, _ = await prepare_case(client)

    result = await send_message(
        client,
        conversation_id,
        "I had a busy day.",
        human_takeover_active=True,
        is_human_takeover=True,
    )

    assert result["is_human_takeover"] is False


@pytest.mark.asyncio
async def test_client_cannot_disable_takeover(client):
    conversation_id, _ = await prepare_case(
        client, "active"
    )

    result = await send_message(
        client,
        conversation_id,
        "I had a busy day.",
        human_takeover_active=False,
        is_human_takeover=False,
    )

    assert result["is_human_takeover"] is True


@pytest.mark.asyncio
async def test_lookup_failure_preserves_crisis_routing(
    client, monkeypatch
):
    conversation_id, _ = await prepare_case(
        client, "active"
    )

    async def failed_lookup(*args, **kwargs):
        raise RuntimeError("Synthetic lookup failure")

    monkeypatch.setattr(
        "app.api.conversations.get_eligible_active_takeover",
        failed_lookup,
    )

    result = await send_message(
        client,
        conversation_id,
        "I want to die.",
    )

    assert result["is_safety_diverted"] is True
    assert result["is_human_takeover"] is False
