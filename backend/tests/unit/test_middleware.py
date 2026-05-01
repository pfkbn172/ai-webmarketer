from fastapi.testclient import TestClient

from app.main import app


def test_request_id_header_is_set() -> None:
    client = TestClient(app)
    res = client.get("/api/v1/healthz")
    assert res.status_code == 200
    rid = res.headers.get("x-request-id")
    assert rid is not None
    assert len(rid) >= 8


def test_request_id_passes_through_when_provided() -> None:
    client = TestClient(app)
    res = client.get("/api/v1/healthz", headers={"x-request-id": "trace-123"})
    assert res.headers.get("x-request-id") == "trace-123"
