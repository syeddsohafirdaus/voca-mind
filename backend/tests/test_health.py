import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """Test GET /api/v1/health returns HTTP 200 and operational status."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "voca_mind"
    assert "version" in data
    # Ensure no internal secrets or database credentials are leaked
    assert "database" not in data
    assert "secret" not in data
