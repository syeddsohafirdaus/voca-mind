"""Guardian consent lifecycle security tests."""

import pytest

from tests.test_guardians import (
    make_auth_client,
    register_test_user,
    get_user_id_by_token,
)

from tests.test_guardian_wellbeing import (
    prepare,
    publish,
    dashboard,
    CLIENT,
    BASE,
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "extra",
    [
        {},
        {"consent": False},
        {"consent": "true"},
        {"consent": 1},
        {"consent": True, "unexpected": True},
    ],
)
async def test_invalid_grant_consent(extra):
    await register_test_user(
        CLIENT, "client", "Test Client"
    )

    await register_test_user(
        "consent-guardian", "guardian", "Test Guardian"
    )

    guardian_id = await get_user_id_by_token(
        "consent-guardian"
    )

    async with make_auth_client(CLIENT) as ac:
        response = await ac.post(
            f"{BASE}/authorizations",
            json={
                "guardian_id": str(guardian_id),
                **extra,
            },
        )

        assert response.status_code == 422

        response = await ac.get(
            f"{BASE}/authorizations"
        )

        assert response.status_code == 200
        assert response.json() == []


@pytest.mark.asyncio
async def test_stale_actions_after_reauthorization():
    auth_id, guardian_id, old_version = await prepare()

    path = f"{BASE}/authorizations/{auth_id}"

    async with make_auth_client(CLIENT) as ac:
        response = await ac.post(
            f"{path}/revoke",
            params={"consent_version": old_version},
        )

        assert response.status_code == 200

        response = await ac.post(
            f"{BASE}/authorizations",
            json={
                "guardian_id": guardian_id,
                "consent": True,
            },
        )

        assert response.status_code == 201
        assert response.json()["id"] == auth_id

        new_version = response.json()["consent_version"]

        assert old_version != new_version

        response = await publish(
            auth_id, old_version
        )

        assert response.status_code == 409
        assert (await dashboard())[0]["wellbeing"] is None

        response = await publish(
            auth_id, new_version, "managing"
        )

        assert response.status_code == 200

        stale = {"consent_version": old_version}

        response = await ac.delete(
            f"{path}/wellbeing", params=stale
        )

        assert response.status_code == 409

        response = await ac.post(
            f"{path}/revoke", params=stale
        )

        assert response.status_code == 409

        response = await ac.delete(
            path, params=stale
        )

        assert response.status_code == 409

        response = await ac.post(
            f"{BASE}/{guardian_id}/revoke",
            params=stale,
        )

        assert response.status_code == 409

        assert (await dashboard())[0]["wellbeing"] == "managing"

        response = await ac.delete(
            f"{path}/wellbeing",
            params={"consent_version": new_version},
        )

        assert response.status_code == 204

        assert (await dashboard())[0]["wellbeing"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "params",
    [{}, {"consent_version": "invalid-uuid"}],
)
async def test_missing_or_invalid_version(params):
    auth_id, guardian_id, version = await prepare()

    path = f"{BASE}/authorizations/{auth_id}"

    async with make_auth_client(CLIENT) as ac:
        response = await ac.post(
            f"{path}/wellbeing",
            params=params,
            json={
                "wellbeing": "doing_well",
                "consent": True,
            },
        )

        assert response.status_code == 422

        response = await ac.delete(
            f"{path}/wellbeing",
            params=params,
        )

        assert response.status_code == 422

        response = await ac.post(
            f"{path}/revoke",
            params=params,
        )

        assert response.status_code == 422

        response = await ac.delete(
            path,
            params=params,
        )

        assert response.status_code == 422

        response = await ac.post(
            f"{BASE}/{guardian_id}/revoke",
            params=params,
        )

        assert response.status_code == 422

    assert len(await dashboard()) == 1
    assert (await dashboard())[0]["wellbeing"] is None
