"""Tests for API endpoints."""

import pytest
from fastapi.testclient import TestClient

from src.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


def test_root_endpoint(client):
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["name"] == "Memoir"


def test_health_endpoint(client):
    """Test health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_config_endpoint(client):
    """Test config endpoint."""
    response = client.get("/v1/config")
    assert response.status_code == 200
    data = response.json()
    assert "llm" in data
    assert "server" in data


def test_list_memories(client):
    """Test list memories endpoint."""
    response = client.get(
        "/v1/memories",
        headers={"X-User-ID": "test-user"},
    )
    assert response.status_code == 200
    assert "memories" in response.json()


def test_list_logs(client):
    """Test list logs endpoint."""
    response = client.get(
        "/v1/logs",
        headers={"X-User-ID": "test-user"},
    )
    assert response.status_code == 200
    assert "logs" in response.json()
