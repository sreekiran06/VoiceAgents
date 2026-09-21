from fastapi.testclient import TestClient

from voice_call_agent.main import app as fastapi_app

client = TestClient(fastapi_app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_website_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert "SK Voice Agents" in response.text
