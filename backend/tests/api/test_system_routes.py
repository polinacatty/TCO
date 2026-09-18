from __future__ import annotations

from fastapi.testclient import TestClient


def test_metrics_endpoint_exposes_http_metrics(api_client: TestClient) -> None:
    health = api_client.get("/health/live")
    assert health.status_code == 200

    metrics = api_client.get("/metrics")
    assert metrics.status_code == 200
    text = metrics.text
    assert "http_requests_total" in text
    assert 'path="/health/live"' in text
    assert "http_request_duration_ms_sum" in text
    assert "service_calls_total" in text
    assert "service_duration_ms_sum" in text
