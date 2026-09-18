from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.mark.unit
def test_liveness(client: TestClient) -> None:
    r = client.get("/health/live")
    assert r.status_code == 200
    assert r.json() == {"status": "alive"}


@pytest.mark.unit
def test_version(client: TestClient) -> None:
    r = client.get("/version")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "tco-backend"
    assert body["version"]
    assert body["env"] in {"dev", "staging", "prod"}


@pytest.mark.unit
def test_readiness_returns_503_when_deps_unavailable(client: TestClient) -> None:
    r = client.get("/health/ready")
    assert r.status_code in {200, 503}
    body = r.json()
    assert body["status"] in {"ready", "not_ready"}
    assert "db" in body and "redis" in body


@pytest.mark.unit
def test_request_id_header_present(client: TestClient) -> None:
    r = client.get("/health/live")
    assert r.headers.get("x-request-id"), "middleware must add request-id"


@pytest.mark.unit
def test_validation_error_uses_problem_format(client: TestClient) -> None:
    r = client.get("/no/such/route")
    assert r.status_code == 404
    body = r.json()
    assert body["status"] == 404
    assert body["type"].startswith("https://tco.example.ru/errors/")
