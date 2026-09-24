"""
Smoke tests for the FastAPI backend: registration/login flow and that every
router is wired into the app. Run with: pytest tests/backend -v
(requires PYTHONPATH to include backend/ and the repo root, see pytest.ini)
"""
import uuid
from fastapi.testclient import TestClient

from app.main import app


def test_health():
    with TestClient(app) as client:
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


def test_register_login_me_flow():
    with TestClient(app) as client:
        unique_email = f"test.manager.{uuid.uuid4().hex[:8]}@example.com"
        register_payload = {
            "email": unique_email,
            "full_name": "Test Manager",
            "password": "supersecret123",
            "store_name": "Test Store",
        }
        r = client.post("/api/v1/auth/register", json=register_payload)
        assert r.status_code == 201
        token = r.json()["access_token"]

        r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["email"] == register_payload["email"]

        r = client.post(
            "/api/v1/auth/login-json",
            json={"email": register_payload["email"], "password": register_payload["password"]},
        )
        assert r.status_code == 200
        assert "access_token" in r.json()


def test_videos_endpoint_requires_auth():
    with TestClient(app) as client:
        r = client.get("/api/v1/videos")
        assert r.status_code == 401
