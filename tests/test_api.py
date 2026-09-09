from fastapi.testclient import TestClient

from voice_call_agent.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_website_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert "SK Voice Agents" in response.text
