import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_missing_authorization_header(client: AsyncClient):
    """Test accessing protected conversation endpoint without Authorization header returns HTTP 401."""
    response = await client.post("/api/v1/conversations", json={})
    assert response.status_code == 401
    data = response.json()
    assert "detail" in data
    assert data["detail"] == "Missing or invalid authorization token"


@pytest.mark.asyncio
async def test_malformed_authorization_header(client: AsyncClient):
    """Test accessing protected endpoint with malformed Authorization headers returns HTTP 401."""
    # Case 1: Missing 'Bearer' prefix
    response1 = await client.post("/api/v1/conversations", json={}, headers={"Authorization": "Basic xyz123"})
    assert response1.status_code == 401

    # Case 2: Bearer prefix without token string
    response2 = await client.post("/api/v1/conversations", json={}, headers={"Authorization": "Bearer "})
    assert response2.status_code == 401


@pytest.mark.asyncio
async def test_invalid_token(client: AsyncClient):
    """Test accessing protected endpoint with invalid token returns HTTP 401."""
    response = await client.post("/api/v1/conversations", json={}, headers={"Authorization": "Bearer invalid-token-xyz"})
    assert response.status_code == 401
    data = response.json()
    assert data["detail"] == "Invalid authentication credentials"


@pytest.mark.asyncio
async def test_valid_token_authenticated_user_extraction(auth_client_user1: AsyncClient):
    """Test valid Bearer token extracts authenticated user and creates conversation."""
    response = await auth_client_user1.post("/api/v1/conversations", json={})
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert "user_id" in data
    assert "started_at" in data
