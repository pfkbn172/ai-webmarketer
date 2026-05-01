from fastapi.testclient import TestClient

from app.main import app


def test_healthz_returns_ok() -> None:
    client = TestClient(app)
    res = client.get("/api/v1/healthz")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}
