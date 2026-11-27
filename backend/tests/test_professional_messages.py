"""Professional messaging integration and privacy tests."""

import pytest

from app.config import settings

from tests.test_assignments import (
    setup_assignment,
    register_client,
    register_doctor,
    ADMIN,
    CLIENT,
    DOCTOR,
    OTHER,
    OTHER_DOCTOR,
    BASE,
    ADMIN_BASE,
)


@pytest.fixture(autouse=True)
def configure_admin(monkeypatch):
    monkeypatch.setattr(
        settings,
        "PLATFORM_ADMIN_UIDS",
        "uid-assignment-admin",
    )


async def active_assignment(client):
    assignment_id, _, application_id = await setup_assignment(client)

    response = await client.post(
        f"{BASE}/{assignment_id}/accept",
        headers=CLIENT,
    )

    assert response.status_code == 200

    url = f"/api/v1/professional/{assignment_id}"

    return assignment_id, application_id, url


async def send(client, url, headers, content):
    return await client.post(
        f"{url}/messages",
        headers=headers,
        json={"content": content},
    )


@pytest.mark.asyncio
async def test_two_way_messaging(client):
    _, _, url = await active_assignment(client)

    first = await send(
        client, url, CLIENT,
        "I would like to discuss academic stress."
    )

    assert first.status_code == 201
    assert first.json()["sender_role"] == "client"

    second = await send(
        client, url, DOCTOR,
        "Thank you for sharing your concerns."
    )

    assert second.status_code == 201
    assert second.json()["sender_role"] == "doctor"

    for participant in [CLIENT, DOCTOR]:
        response = await client.get(
            f"{url}/messages",
            headers=participant,
        )

        assert response.status_code == 200
        assert len(response.json()) == 2
        assert response.json()[0]["id"] == second.json()["id"]


@pytest.mark.asyncio
async def test_unread_count_and_read_receipt(client):
    _, _, url = await active_assignment(client)

    response = await send(
        client, url, CLIENT, "Synthetic test message."
    )

    assert response.status_code == 201
    message_id = response.json()["id"]

    response = await client.get(
        f"{url}/unread", headers=DOCTOR
    )
    assert response.json()["unread_count"] == 1

    response = await client.get(
        f"{url}/unread", headers=CLIENT
    )
    assert response.json()["unread_count"] == 0

    response = await client.post(
        f"{url}/messages/{message_id}/read",
        headers=DOCTOR,
    )
    assert response.status_code == 200

    response = await client.get(
        f"{url}/unread", headers=DOCTOR
    )
    assert response.json()["unread_count"] == 0

    response = await client.get(
        f"{url}/messages", headers=CLIENT
    )
    assert response.json()[0]["read_at"] is not None


@pytest.mark.asyncio
async def test_sender_cannot_mark_own_message_read(client):
    _, _, url = await active_assignment(client)

    response = await send(
        client, url, CLIENT, "Synthetic message."
    )

    assert response.status_code == 201
    message_id = response.json()["id"]

    response = await client.post(
        f"{url}/messages/{message_id}/read",
        headers=CLIENT,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_pagination(client):
    _, _, url = await active_assignment(client)

    for i in range(5):
        response = await send(
            client, url, CLIENT, f"Test message {i}"
        )
        assert response.status_code == 201

    first = await client.get(
        f"{url}/messages?limit=2&offset=0",
        headers=CLIENT,
    )

    second = await client.get(
        f"{url}/messages?limit=2&offset=2",
        headers=CLIENT,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert len(first.json()) == 2
    assert len(second.json()) == 2

    first_ids = {item["id"] for item in first.json()}
    second_ids = {item["id"] for item in second.json()}

    assert first_ids.isdisjoint(second_ids)


@pytest.mark.asyncio
@pytest.mark.parametrize("content", ["", "   ", "x" * 5001])
async def test_invalid_message_content(client, content):
    _, _, url = await active_assignment(client)

    response = await send(
        client, url, CLIENT, content
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_sender_identity_cannot_be_spoofed(client):
    _, _, url = await active_assignment(client)

    response = await client.post(
        f"{url}/messages",
        headers=CLIENT,
        json={
            "content": "Synthetic message.",
            "sender_role": "doctor",
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_unauthenticated_access(client):
    _, _, url = await active_assignment(client)

    response = await client.get(f"{url}/messages")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_pending_assignment_blocks_messaging(client):
    assignment_id, _, _ = await setup_assignment(client)

    url = f"/api/v1/professional/{assignment_id}"

    for participant in [CLIENT, DOCTOR]:
        response = await send(
            client, url, participant, "Test message."
        )
        assert response.status_code == 403

        response = await client.get(
            f"{url}/messages", headers=participant
        )
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_other_client_cannot_access_messages(client):
    _, _, url = await active_assignment(client)

    await register_client(client, "other-client")

    response = await client.get(
        f"{url}/messages", headers=OTHER
    )
    assert response.status_code == 404

    response = await send(
        client, url, OTHER, "Unauthorized message."
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_other_doctor_cannot_access_messages(client):
    _, _, url = await active_assignment(client)

    await register_doctor(client, "other-doctor")

    response = await client.get(
        f"{url}/messages", headers=OTHER_DOCTOR
    )
    assert response.status_code == 404

    response = await send(
        client, url, OTHER_DOCTOR,
        "Unauthorized message."
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_admin_cannot_read_private_messages(client):
    _, _, url = await active_assignment(client)

    response = await client.get(
        f"{url}/messages", headers=ADMIN
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_guardian_cannot_read_professional_messages(client):
    _, _, url = await active_assignment(client)

    guardian = {
        "Authorization": "Bearer messaging-guardian"
    }

    response = await client.post(
        "/api/v1/auth/register/guardian",
        headers=guardian,
        json={"display_name": "Synthetic Guardian"},
    )

    assert response.status_code == 201

    response = await client.get(
        f"{url}/messages", headers=guardian
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_revocation_blocks_all_message_operations(client):
    assignment_id, _, url = await active_assignment(client)

    response = await send(
        client, url, CLIENT, "Synthetic private message."
    )

    assert response.status_code == 201
    message_id = response.json()["id"]

    response = await client.post(
        f"{BASE}/{assignment_id}/revoke",
        headers=CLIENT,
    )
    assert response.status_code == 200

    for participant in [CLIENT, DOCTOR]:
        response = await client.get(
            f"{url}/messages", headers=participant
        )
        assert response.status_code == 403

        response = await send(
            client, url, participant, "Blocked message."
        )
        assert response.status_code == 403

        response = await client.get(
            f"{url}/unread", headers=participant
        )
        assert response.status_code == 403

    response = await client.post(
        f"{url}/messages/{message_id}/read",
        headers=DOCTOR,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_suspension_blocks_messaging(client):
    _, application_id, url = await active_assignment(client)

    response = await client.post(
        f"{ADMIN_BASE}/{application_id}/suspend",
        headers=ADMIN,
        json={"reason": "Synthetic suspension test."},
    )

    assert response.status_code == 200

    for participant in [CLIENT, DOCTOR]:
        response = await client.get(
            f"{url}/messages", headers=participant
        )
        assert response.status_code == 403

        response = await send(
            client, url, participant, "Blocked message."
        )
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_completed_assignment_blocks_messaging(client):
    assignment_id, _, url = await active_assignment(client)

    response = await client.post(
        f"{BASE}/{assignment_id}/complete",
        headers=DOCTOR,
    )

    assert response.status_code == 200

    for participant in [CLIENT, DOCTOR]:
        response = await send(
            client, url, participant, "Blocked message."
        )
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_professional_messages_do_not_unlock_ai_history(client):
    _, _, url = await active_assignment(client)

    response = await send(
        client, url, CLIENT, "Synthetic professional message."
    )

    assert response.status_code == 201

    response = await client.get(
        "/api/v1/conversations",
        headers=DOCTOR,
    )

    assert response.status_code == 403
