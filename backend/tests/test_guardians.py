"""Automated test suite for Client-controlled Guardian authorization and privacy.

Validates:
1. Active Clients can grant authorization to existing active Guardians.
2. Self-authorization is strictly prohibited.
3. Authorizing non-existent, non-guardian, or inactive users is rejected.
4. Duplicate active authorizations are prevented (HTTP 409).
5. Reauthorization after revocation succeeds and updates timestamps.
6. Clients can list only their own authorizations.
7. Revocation by authorization ID, DELETE, or guardian ID immediately revokes access.
8. Cross-client revocation is rejected (HTTP 404).
9. Guardians and Doctors cannot grant authorizations (HTTP 403).
10. Unauthenticated requests are rejected (HTTP 401).
11. Guardian registration never auto-authorizes.
12. Authorized Guardians receive HTTP 403 when attempting to access Client conversations or messages.
"""

import uuid
from datetime import datetime, timezone
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.main import app
from app.models.guardian_authorization import GuardianAuthorization
from app.models.user import User


# Helper functions for creating test HTTP clients with custom Bearer tokens
def make_auth_client(token: str) -> AsyncClient:
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {token}"}
    return AsyncClient(transport=transport, base_url="http://test", headers=headers)


async def register_test_user(
    token: str,
    role: str,
    display_name: str,
    date_of_birth: str = "2000-01-01",
) -> dict:
    """Helper to register a user via the public auth API."""
    async with make_auth_client(token) as ac:
        if role == "client":
            payload = {
                "display_name": display_name,
                "date_of_birth": date_of_birth,
            }
            resp = await ac.post("/api/v1/auth/register/client", json=payload)
        elif role == "guardian":
            payload = {"display_name": display_name}
            resp = await ac.post("/api/v1/auth/register/guardian", json=payload)
        elif role == "doctor":
            payload = {
                "display_name": display_name,
                "registration_number": "MED-12345",
                "licensing_authority": "Medical Council",
                "specialization": "Psychiatry",
            }
            resp = await ac.post("/api/v1/auth/register/doctor", json=payload)
        else:
            raise ValueError(f"Unknown test role: {role}")

        assert resp.status_code == 201, f"Registration failed: {resp.text}"
        return resp.json()


async def get_user_id_by_token(token: str) -> uuid.UUID:
    """Retrieve database user ID for a test token."""
    firebase_uid = f"uid-{token}"
    async for db in app.dependency_overrides[get_db]():
        result = await db.execute(
            select(User.id).where(User.firebase_uid == firebase_uid)
        )
        user_id = result.scalar_one()
        return user_id


@pytest.mark.asyncio
async def test_client_grants_guardian_authorization_success():
    """Test active Client successfully grants authorization to active Guardian."""
    await register_test_user("client-alice-token", "client", "Alice Client")
    await register_test_user("guardian-bob-token", "guardian", "Bob Guardian")
    bob_id = await get_user_id_by_token("guardian-bob-token")

    async with make_auth_client("client-alice-token") as client_ac:
        payload = {"guardian_id": str(bob_id)}
        resp = await client_ac.post("/api/v1/guardians/authorizations", json=payload)

        assert resp.status_code == 201
        data = resp.json()
        assert "id" in data
        assert data["guardian_id"] == str(bob_id)
        assert data["status"] == "active"
        assert data["consented_at"] is not None
        assert data["revoked_at"] is None
        assert data["guardian_display_name"] == "Bob Guardian"


@pytest.mark.asyncio
async def test_duplicate_authorization_returns_409_conflict():
    """Test granting duplicate authorization while active returns HTTP 409."""
    await register_test_user("client-dup-token", "client", "Dup Client")
    await register_test_user("guardian-dup-token", "guardian", "Dup Guardian")
    guardian_id = await get_user_id_by_token("guardian-dup-token")

    async with make_auth_client("client-dup-token") as client_ac:
        payload = {"guardian_id": str(guardian_id)}
        resp1 = await client_ac.post("/api/v1/guardians/authorizations", json=payload)
        assert resp1.status_code == 201

        resp2 = await client_ac.post("/api/v1/guardians/authorizations", json=payload)
        assert resp2.status_code == 409
        assert "already exists" in resp2.json()["detail"]


@pytest.mark.asyncio
async def test_reauthorization_after_revocation_success():
    """Test reauthorizing a previously revoked Guardian reactivates the authorization."""
    await register_test_user("client-reauth-token", "client", "Reauth Client")
    await register_test_user("guardian-reauth-token", "guardian", "Reauth Guardian")
    guardian_id = await get_user_id_by_token("guardian-reauth-token")

    async with make_auth_client("client-reauth-token") as client_ac:
        payload = {"guardian_id": str(guardian_id)}

        # 1. Grant authorization
        resp1 = await client_ac.post("/api/v1/guardians/authorizations", json=payload)
        assert resp1.status_code == 201
        auth_id = resp1.json()["id"]

        # 2. Revoke authorization
        revoke_resp = await client_ac.post(f"/api/v1/guardians/authorizations/{auth_id}/revoke")
        assert revoke_resp.status_code == 200
        assert revoke_resp.json()["status"] == "revoked"
        assert revoke_resp.json()["revoked_at"] is not None

        # 3. Reauthorize the same guardian
        resp2 = await client_ac.post("/api/v1/guardians/authorizations", json=payload)
        assert resp2.status_code == 201
        data = resp2.json()
        assert data["id"] == auth_id  # Preserves record identity
        assert data["status"] == "active"
        assert data["revoked_at"] is None


@pytest.mark.asyncio
async def test_prevent_self_authorization():
    """Test Client cannot authorize themselves as a Guardian."""
    await register_test_user("client-self-token", "client", "Self Client")
    client_id = await get_user_id_by_token("client-self-token")

    async with make_auth_client("client-self-token") as client_ac:
        payload = {"guardian_id": str(client_id)}
        resp = await client_ac.post("/api/v1/guardians/authorizations", json=payload)

        assert resp.status_code == 400
        assert "cannot authorize themselves" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_reject_non_existent_guardian():
    """Test authorizing non-existent user returns HTTP 404."""
    await register_test_user("client-fakeg-token", "client", "FakeG Client")
    random_uuid = str(uuid.uuid4())

    async with make_auth_client("client-fakeg-token") as client_ac:
        payload = {"guardian_id": random_uuid}
        resp = await client_ac.post("/api/v1/guardians/authorizations", json=payload)

        assert resp.status_code == 404
        assert "Guardian account not found" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_reject_user_with_non_guardian_role():
    """Test authorizing a Client or Doctor as a Guardian is rejected with HTTP 400."""
    await register_test_user("client-caller-token", "client", "Caller Client")
    await register_test_user("client-target-token", "client", "Target Client")
    target_client_id = await get_user_id_by_token("client-target-token")

    async with make_auth_client("client-caller-token") as client_ac:
        payload = {"guardian_id": str(target_client_id)}
        resp = await client_ac.post("/api/v1/guardians/authorizations", json=payload)

        assert resp.status_code == 400
        assert "guardian role" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_reject_inactive_guardian():
    """Test authorizing an inactive/suspended Guardian is rejected with HTTP 400."""
    await register_test_user("client-inact-token", "client", "Inact Client")
    await register_test_user("guardian-inact-token", "guardian", "Suspended Guardian")
    guardian_id = await get_user_id_by_token("guardian-inact-token")

    # Suspend the guardian in database
    async for db in app.dependency_overrides[get_db]():
        result = await db.execute(select(User).where(User.id == guardian_id))
        user = result.scalar_one()
        user.account_status = "suspended"
        await db.commit()

    async with make_auth_client("client-inact-token") as client_ac:
        payload = {"guardian_id": str(guardian_id)}
        resp = await client_ac.post("/api/v1/guardians/authorizations", json=payload)

        assert resp.status_code == 400
        assert "not active" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_list_and_filter_guardian_authorizations():
    """Test listing authorizations and filtering by active/revoked status."""
    await register_test_user("client-list-token", "client", "List Client")
    await register_test_user("guardian-g1-token", "guardian", "G1 Guardian")
    await register_test_user("guardian-g2-token", "guardian", "G2 Guardian")
    g1_id = await get_user_id_by_token("guardian-g1-token")
    g2_id = await get_user_id_by_token("guardian-g2-token")

    async with make_auth_client("client-list-token") as client_ac:
        # Authorize G1 and G2
        resp_g1 = await client_ac.post("/api/v1/guardians/authorizations", json={"guardian_id": str(g1_id)})
        resp_g2 = await client_ac.post("/api/v1/guardians/authorizations", json={"guardian_id": str(g2_id)})
        assert resp_g1.status_code == 201
        assert resp_g2.status_code == 201
        g2_auth_id = resp_g2.json()["id"]

        # Revoke G2
        await client_ac.post(f"/api/v1/guardians/authorizations/{g2_auth_id}/revoke")

        # List all
        all_resp = await client_ac.get("/api/v1/guardians/authorizations")
        assert all_resp.status_code == 200
        all_items = all_resp.json()
        assert len(all_items) == 2

        # Filter active
        active_resp = await client_ac.get("/api/v1/guardians/authorizations?status=active")
        assert active_resp.status_code == 200
        active_items = active_resp.json()
        assert len(active_items) == 1
        assert active_items[0]["guardian_id"] == str(g1_id)

        # Filter revoked
        revoked_resp = await client_ac.get("/api/v1/guardians/authorizations?status=revoked")
        assert revoked_resp.status_code == 200
        revoked_items = revoked_resp.json()
        assert len(revoked_items) == 1
        assert revoked_items[0]["guardian_id"] == str(g2_id)


@pytest.mark.asyncio
async def test_client_isolation_in_listing():
    """Test Client 2 cannot view authorizations granted by Client 1."""
    await register_test_user("client-iso1-token", "client", "Iso1 Client")
    await register_test_user("client-iso2-token", "client", "Iso2 Client")
    await register_test_user("guardian-iso-token", "guardian", "Iso Guardian")
    g_id = await get_user_id_by_token("guardian-iso-token")

    async with make_auth_client("client-iso1-token") as c1_ac:
        await c1_ac.post("/api/v1/guardians/authorizations", json={"guardian_id": str(g_id)})

    async with make_auth_client("client-iso2-token") as c2_ac:
        c2_list = await c2_ac.get("/api/v1/guardians/authorizations")
        assert c2_list.status_code == 200
        assert len(c2_list.json()) == 0


@pytest.mark.asyncio
async def test_revoke_methods():
    """Test revoking via POST /revoke, DELETE, and POST /{guardian_id}/revoke."""
    await register_test_user("client-rev-token", "client", "Rev Client")
    await register_test_user("guardian-rev1-token", "guardian", "Rev1 Guardian")
    await register_test_user("guardian-rev2-token", "guardian", "Rev2 Guardian")
    g1_id = await get_user_id_by_token("guardian-rev1-token")
    g2_id = await get_user_id_by_token("guardian-rev2-token")

    async with make_auth_client("client-rev-token") as client_ac:
        # Revocation via DELETE
        res1 = await client_ac.post("/api/v1/guardians/authorizations", json={"guardian_id": str(g1_id)})
        auth1_id = res1.json()["id"]
        del_resp = await client_ac.delete(f"/api/v1/guardians/authorizations/{auth1_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["status"] == "revoked"

        # Revocation via guardian_id
        res2 = await client_ac.post("/api/v1/guardians/authorizations", json={"guardian_id": str(g2_id)})
        assert res2.status_code == 201
        gid_resp = await client_ac.post(f"/api/v1/guardians/{g2_id}/revoke")
        assert gid_resp.status_code == 200
        assert gid_resp.json()["status"] == "revoked"


@pytest.mark.asyncio
async def test_prevent_cross_client_revocation():
    """Test Client 2 cannot revoke Client 1's Guardian authorization."""
    await register_test_user("client-cross1-token", "client", "Cross1 Client")
    await register_test_user("client-cross2-token", "client", "Cross2 Client")
    await register_test_user("guardian-cross-token", "guardian", "Cross Guardian")
    g_id = await get_user_id_by_token("guardian-cross-token")

    async with make_auth_client("client-cross1-token") as c1_ac:
        res = await c1_ac.post("/api/v1/guardians/authorizations", json={"guardian_id": str(g_id)})
        auth_id = res.json()["id"]

    async with make_auth_client("client-cross2-token") as c2_ac:
        steal_resp = await c2_ac.post(f"/api/v1/guardians/authorizations/{auth_id}/revoke")
        assert steal_resp.status_code == 404
        assert "not found" in steal_resp.json()["detail"]


@pytest.mark.asyncio
async def test_non_clients_cannot_manage_authorizations():
    """Test Guardians and Doctors receive HTTP 403 when attempting authorization operations."""
    await register_test_user("guardian-actor-token", "guardian", "Actor Guardian")
    await register_test_user("doctor-actor-token", "doctor", "Actor Doctor")

    random_id = str(uuid.uuid4())

    async with make_auth_client("guardian-actor-token") as g_ac:
        g_post = await g_ac.post("/api/v1/guardians/authorizations", json={"guardian_id": random_id})
        assert g_post.status_code == 403
        g_get = await g_ac.get("/api/v1/guardians/authorizations")
        assert g_get.status_code == 403

    async with make_auth_client("doctor-actor-token") as d_ac:
        d_post = await d_ac.post("/api/v1/guardians/authorizations", json={"guardian_id": random_id})
        assert d_post.status_code == 403
        d_get = await d_ac.get("/api/v1/guardians/authorizations")
        assert d_get.status_code == 403


@pytest.mark.asyncio
async def test_unauthenticated_requests_rejected(client: AsyncClient):
    """Test unauthenticated calls to Guardian endpoints return HTTP 401."""
    resp1 = await client.post("/api/v1/guardians/authorizations", json={"guardian_id": str(uuid.uuid4())})
    assert resp1.status_code == 401

    resp2 = await client.get("/api/v1/guardians/authorizations")
    assert resp2.status_code == 401


@pytest.mark.asyncio
async def test_guardian_registration_does_not_auto_authorize():
    """Test that registering a Guardian does NOT create any authorization record."""
    await register_test_user("guardian-auto-check-token", "guardian", "Auto Guardian")
    g_id = await get_user_id_by_token("guardian-auto-check-token")

    async for db in app.dependency_overrides[get_db]():
        result = await db.execute(
            select(GuardianAuthorization).where(GuardianAuthorization.guardian_id == g_id)
        )
        auths = result.scalars().all()
        assert len(auths) == 0, "Guardian registration must never automatically authorize a guardian"


@pytest.mark.asyncio
async def test_privacy_guardian_cannot_access_client_conversations():
    """
    CRITICAL PRIVACY TEST:
    Guardians must NEVER access private AI conversations or message contents,
    even when they hold an active authorization from a Client.
    """
    await register_test_user("client-priv-token", "client", "Priv Client")
    await register_test_user("guardian-priv-token", "guardian", "Priv Guardian")
    g_id = await get_user_id_by_token("guardian-priv-token")

    # Client creates conversation
    async with make_auth_client("client-priv-token") as client_ac:
        conv_resp = await client_ac.post("/api/v1/conversations", json={})
        assert conv_resp.status_code == 201
        conv_id = conv_resp.json()["id"]

        # Client authorizes Guardian
        auth_resp = await client_ac.post(
            "/api/v1/guardians/authorizations",
            json={"guardian_id": str(g_id)},
        )
        assert auth_resp.status_code == 201
        assert auth_resp.json()["status"] == "active"

    # Authorized Guardian attempts to access client conversations -> HTTP 403 Forbidden
    async with make_auth_client("guardian-priv-token") as guardian_ac:
        # 1. List conversations
        list_resp = await guardian_ac.get("/api/v1/conversations")
        assert list_resp.status_code == 403
        assert "permission" in list_resp.json()["detail"].lower()

        # 2. Get specific conversation
        get_resp = await guardian_ac.get(f"/api/v1/conversations/{conv_id}")
        assert get_resp.status_code == 403

        # 3. Create conversation as guardian
        create_resp = await guardian_ac.post("/api/v1/conversations", json={})
        assert create_resp.status_code == 403

        # 4. Inject message into client conversation
        msg_payload = {"role": "user", "content": "Guardian attempting to read/write"}
        msg_resp = await guardian_ac.post(
            f"/api/v1/conversations/{conv_id}/messages",
            json=msg_payload,
        )
        assert msg_resp.status_code == 403
