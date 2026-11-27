"""Guardian wellbeing privacy and consent tests."""

import pytest

from tests.test_guardians import (
    make_auth_client,
    register_test_user,
    get_user_id_by_token,
)

BASE = "/api/v1/guardians"
CLIENT = "wellbeing-client"
GUARDIAN = "wellbeing-guardian"
OTHER = "wellbeing-other"


async def prepare():
    await register_test_user(CLIENT, "client", "Test Client")
    await register_test_user(GUARDIAN, "guardian", "Test Guardian")
    await register_test_user(OTHER, "guardian", "Other Guardian")

    guardian_id = await get_user_id_by_token(GUARDIAN)

    async with make_auth_client(CLIENT) as ac:
        response = await ac.post(
            f"{BASE}/authorizations",
            json={"guardian_id": str(guardian_id), "consent": True},
        )

    assert response.status_code == 201
    return response.json()["id"], str(guardian_id), response.json()["consent_version"]


async def publish(auth_id, version, wellbeing="doing_well"):
    async with make_auth_client(CLIENT) as ac:
        return await ac.post(
            f"{BASE}/authorizations/{auth_id}/wellbeing?consent_version={version}",
            json={"wellbeing": wellbeing, "consent": True},
        )


async def dashboard(token=GUARDIAN):
    async with make_auth_client(token) as ac:
        response = await ac.get(f"{BASE}/dashboard")

    assert response.status_code == 200
    return response.json()


@pytest.mark.asyncio
async def test_no_automatic_wellbeing_sharing():
    await prepare()

    items = await dashboard()

    assert len(items) == 1
    assert items[0]["wellbeing"] is None
    assert items[0]["shared_at"] is None


@pytest.mark.asyncio
async def test_explicit_wellbeing_sharing():
    auth_id, _, version = await prepare()

    response = await publish(auth_id, version)

    assert response.status_code == 200

    items = await dashboard()

    assert items[0]["wellbeing"] == "doing_well"
    assert items[0]["shared_at"] is not None


@pytest.mark.asyncio
async def test_update_replaces_previous_status():
    auth_id, _, version = await prepare()

    assert (await publish(auth_id, version)).status_code == 200
    assert (await publish(auth_id, version, "managing")).status_code == 200

    items = await dashboard()

    assert len(items) == 1
    assert items[0]["wellbeing"] == "managing"


@pytest.mark.asyncio
async def test_unrelated_guardian_cannot_see_update():
    auth_id, _, version = await prepare()

    assert (await publish(auth_id, version)).status_code == 200

    assert await dashboard(OTHER) == []


@pytest.mark.asyncio
async def test_dashboard_contains_only_allowed_fields():
    auth_id, _, version = await prepare()

    assert (await publish(auth_id, version)).status_code == 200

    item = (await dashboard())[0]

    assert set(item) == {
        "authorization_id",
        "client_display_name",
        "wellbeing",
        "shared_at",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"wellbeing": "doing_well"},
        {"wellbeing": "doing_well", "consent": False},
        {"wellbeing": "doing_well", "consent": "true"},
        {"wellbeing": "doing_well", "consent": 1},
        {"wellbeing": "invalid", "consent": True},
        {
            "wellbeing": "doing_well",
            "consent": True,
            "private_message": "not permitted",
        },
    ],
)
async def test_invalid_sharing_rejected(payload):
    auth_id, _, version = await prepare()

    async with make_auth_client(CLIENT) as ac:
        response = await ac.post(
            f"{BASE}/authorizations/{auth_id}/wellbeing?consent_version={version}",
            json=payload,
        )

    assert response.status_code == 422
    assert (await dashboard())[0]["wellbeing"] is None


@pytest.mark.asyncio
async def test_client_can_withdraw_update():
    auth_id, _, version = await prepare()

    assert (await publish(auth_id, version)).status_code == 200

    async with make_auth_client(CLIENT) as ac:
        response = await ac.delete(
            f"{BASE}/authorizations/{auth_id}/wellbeing?consent_version={version}"
        )

    assert response.status_code == 204
    assert (await dashboard())[0]["wellbeing"] is None


@pytest.mark.asyncio
async def test_revocation_and_reauthorization():
    auth_id, guardian_id, version = await prepare()

    assert (await publish(auth_id, version)).status_code == 200

    async with make_auth_client(CLIENT) as ac:
        response = await ac.post(
            f"{BASE}/authorizations/{auth_id}/revoke?consent_version={version}"
        )

        assert response.status_code == 200
        assert await dashboard() == []

        assert (await publish(auth_id, version)).status_code == 403

        response = await ac.post(
            f"{BASE}/authorizations",
            json={"guardian_id": guardian_id, "consent": True},
        )

        assert response.status_code == 201

    items = await dashboard()

    assert len(items) == 1
    assert items[0]["wellbeing"] is None


@pytest.mark.asyncio
async def test_guardian_cannot_publish():
    auth_id, _, version = await prepare()

    async with make_auth_client(GUARDIAN) as ac:
        response = await ac.post(
            f"{BASE}/authorizations/{auth_id}/wellbeing?consent_version={version}",
            json={
                "wellbeing": "doing_well",
                "consent": True,
            },
        )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_client_cannot_access_guardian_dashboard():
    await prepare()

    async with make_auth_client(CLIENT) as ac:
        response = await ac.get(f"{BASE}/dashboard")

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_cross_client_cannot_modify_update():
    auth_id, _, version = await prepare()

    await register_test_user(
        "unrelated-client", "client", "Other Client"
    )

    assert (await publish(auth_id, version)).status_code == 200

    async with make_auth_client("unrelated-client") as ac:
        response = await ac.post(
            f"{BASE}/authorizations/{auth_id}/wellbeing?consent_version={version}",
            json={"wellbeing": "managing", "consent": True},
        )

        assert response.status_code == 404

        response = await ac.delete(
            f"{BASE}/authorizations/{auth_id}/wellbeing?consent_version={version}"
        )

        assert response.status_code == 404

    assert (await dashboard())[0]["wellbeing"] == "doing_well"


@pytest.mark.asyncio
@pytest.mark.parametrize("token", [CLIENT, GUARDIAN])
async def test_suspended_account_blocks_access(token):
    from app.models.user import User
    from tests.conftest import TestAsyncSessionLocal

    auth_id, _, version = await prepare()

    assert (await publish(auth_id, version)).status_code == 200

    user_id = await get_user_id_by_token(token)

    async with TestAsyncSessionLocal() as db:
        user = await db.get(User, user_id)
        user.account_status = "suspended"
        await db.commit()

    async with make_auth_client(GUARDIAN) as ac:
        response = await ac.get(f"{BASE}/dashboard")

    if token == GUARDIAN:
        assert response.status_code == 403
    else:
        assert response.status_code == 200
        assert response.json() == []

    assert (await publish(auth_id, version)).status_code == 403
