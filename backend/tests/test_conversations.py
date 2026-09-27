import uuid
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_conversation(client: AsyncClient):
    """Test POST /api/v1/conversations creates a conversation session."""
    response = await client.post("/api/v1/conversations", json={})
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert "user_id" in data
    assert "started_at" in data
    assert data["ended_at"] is None
    assert data["messages"] == []


@pytest.mark.asyncio
async def test_get_conversation(client: AsyncClient):
    """Test GET /api/v1/conversations/{conversation_id} retrieves a created conversation."""
    create_resp = await client.post("/api/v1/conversations", json={})
    assert create_resp.status_code == 201
    conv_id = create_resp.json()["id"]

    get_resp = await client.get(f"/api/v1/conversations/{conv_id}")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["id"] == conv_id
    assert "messages" in data


@pytest.mark.asyncio
async def test_add_user_message(client: AsyncClient):
    """Test POST /api/v1/conversations/{id}/messages with user role."""
    create_resp = await client.post("/api/v1/conversations", json={})
    conv_id = create_resp.json()["id"]

    msg_payload = {
        "role": "user",
        "content": "I have been feeling stressed at work."
    }
    msg_resp = await client.post(f"/api/v1/conversations/{conv_id}/messages", json=msg_payload)
    assert msg_resp.status_code == 201
    data = msg_resp.json()
    assert data["conversation_id"] == conv_id
    assert data["role"] == "user"
    assert data["content"] == "I have been feeling stressed at work."
    assert "id" in data
    assert "created_at" in data

    # Verify message is returned when retrieving conversation
    get_resp = await client.get(f"/api/v1/conversations/{conv_id}")
    assert get_resp.status_code == 200
    conv_data = get_resp.json()
    assert len(conv_data["messages"]) == 1
    assert conv_data["messages"][0]["id"] == data["id"]


@pytest.mark.asyncio
async def test_add_assistant_message(client: AsyncClient):
    """Test POST /api/v1/conversations/{id}/messages with assistant role."""
    create_resp = await client.post("/api/v1/conversations", json={})
    conv_id = create_resp.json()["id"]

    msg_payload = {
        "role": "assistant",
        "content": "Thank you for sharing that. I am here to listen."
    }
    msg_resp = await client.post(f"/api/v1/conversations/{conv_id}/messages", json=msg_payload)
    assert msg_resp.status_code == 201
    data = msg_resp.json()
    assert data["conversation_id"] == conv_id
    assert data["role"] == "assistant"
    assert data["content"] == "Thank you for sharing that. I am here to listen."


@pytest.mark.asyncio
async def test_invalid_message_role(client: AsyncClient):
    """Test POST /api/v1/conversations/{id}/messages rejects roles other than user/assistant."""
    create_resp = await client.post("/api/v1/conversations", json={})
    conv_id = create_resp.json()["id"]

    # Role 'system' is prohibited by validation schema
    msg_payload = {
        "role": "system",
        "content": "System prompt text"
    }
    msg_resp = await client.post(f"/api/v1/conversations/{conv_id}/messages", json=msg_payload)
    assert msg_resp.status_code == 422
    data = msg_resp.json()
    assert "error" in data or "detail" in data


@pytest.mark.asyncio
async def test_non_existent_conversation(client: AsyncClient):
    """Test GET and POST message on a non-existent conversation ID returns 404."""
    fake_id = str(uuid.uuid4())

    get_resp = await client.get(f"/api/v1/conversations/{fake_id}")
    assert get_resp.status_code == 404

    msg_payload = {
        "role": "user",
        "content": "Hello?"
    }
    msg_resp = await client.post(f"/api/v1/conversations/{fake_id}/messages", json=msg_payload)
    assert msg_resp.status_code == 404
