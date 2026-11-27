"""Protection against delayed takeover actions."""

import pytest

from app.config import settings
from tests.test_takeover_endpoints import (
    BASE,
    CLIENT,
    DOCTOR,
    prepare_assignment,
    request_session,
    accept_session,
)


@pytest.fixture(autouse=True)
def configure_admin(monkeypatch):
    monkeypatch.setattr(
        settings,
        "PLATFORM_ADMIN_UIDS",
        "uid-assignment-admin",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action,auth",
    [
        ("accept", DOCTOR),
        ("cancel", CLIENT),
        ("end", CLIENT),
        ("end", DOCTOR),
    ],
)
async def test_stale_action_cannot_modify_new_session(
    client, action, auth
):
    assignment_id, _ = await prepare_assignment(client)

    first = await request_session(client, assignment_id)

    if action == "end":
        await accept_session(
            client, assignment_id, first["id"]
        )
        close_action = "end"
    else:
        close_action = "cancel"

    response = await client.post(
        f"{BASE}/{assignment_id}/{close_action}",
        headers=CLIENT,
        params={"takeover_id": first["id"]},
    )

    assert response.status_code == 200

    second = await request_session(client, assignment_id)

    expected_status = "requested"

    if action == "end":
        await accept_session(
            client, assignment_id, second["id"]
        )
        expected_status = "active"

    response = await client.post(
        f"{BASE}/{assignment_id}/{action}",
        headers=auth,
        params={"takeover_id": first["id"]},
    )

    assert response.status_code == 409

    response = await client.get(
        f"{BASE}/client",
        headers=CLIENT,
    )

    assert response.status_code == 200

    current = next(
        item for item in response.json()
        if item["id"] == second["id"]
    )

    assert current["status"] == expected_status


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action,auth",
    [
        ("accept", DOCTOR),
        ("cancel", CLIENT),
        ("end", CLIENT),
    ],
)
async def test_missing_session_id_rejected(
    client, action, auth
):
    assignment_id, _ = await prepare_assignment(client)

    await request_session(client, assignment_id)

    response = await client.post(
        f"{BASE}/{assignment_id}/{action}",
        headers=auth,
    )

    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action,auth",
    [
        ("accept", DOCTOR),
        ("cancel", CLIENT),
        ("end", CLIENT),
    ],
)
async def test_invalid_session_id_rejected(
    client, action, auth
):
    assignment_id, _ = await prepare_assignment(client)

    await request_session(client, assignment_id)

    response = await client.post(
        f"{BASE}/{assignment_id}/{action}",
        headers=auth,
        params={"takeover_id": "invalid-id"},
    )

    assert response.status_code == 422
