from __future__ import annotations

from fastapi.testclient import TestClient


def _profile() -> dict[str, object]:
    return {
        "region_id": 1,
        "annual_mileage_km": 15_000,
        "driver_age": 35,
        "driver_experience_years": 10,
        "osago_unlimited_drivers": False,
        "use_dealer_service": False,
        "include_kasko": False,
    }


def test_recommend_happy_path(api_client: TestClient) -> None:
    body = {
        "profile": _profile(),
        "horizon_years": 5,
        "top_n": 3,
        "filters": {"purchase_price_max_rub": 2_000_000},
        "weights_preset": "balanced",
    }
    resp = api_client.post("/api/tco/recommend", json=body)
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["total_candidates"] >= 1
    assert len(payload["items"]) >= 1
    assert payload["items"][0]["rank"] == 1
    assert "metrics" in payload
    assert payload["metrics"]["diversity_at_k"] >= 1


def test_recommend_not_found_when_filters_too_strict(api_client: TestClient) -> None:
    body = {
        "profile": _profile(),
        "horizon_years": 5,
        "top_n": 5,
        "filters": {"purchase_price_max_rub": 100},
    }
    resp = api_client.post("/api/tco/recommend", json=body)
    assert resp.status_code == 404


def test_compare_happy_path(api_client: TestClient) -> None:
    body = {
        "profile": _profile(),
        "horizon_years": 5,
        "modification_ids": [1, 2],
    }
    resp = api_client.post("/api/tco/compare", json=body)
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert len(payload["items"]) == 2
    assert payload["items"][0]["delta_total_rub_vs_first"] == 0
    assert len(payload["items"][1]["delta_components_vs_first"]) == 7
