from __future__ import annotations

from fastapi.testclient import TestClient


def _valid_request_body() -> dict[str, object]:
    return {
        "modification_id": 1,
        "horizon_years": 5,
        "profile": {
            "region_id": 1,
            "annual_mileage_km": 15_000,
            "driver_age": 35,
            "driver_experience_years": 10,
            "osago_unlimited_drivers": False,
            "use_dealer_service": False,
            "include_kasko": False,
        },
        "options": {"include_kasko": False, "discount_rate_pct": 0.0},
    }


def test_tco_calculate_happy_path(api_client: TestClient) -> None:
    resp = api_client.post("/api/tco/calculate", json=_valid_request_body())
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["modification_id"] == 1
    assert body["horizon_years"] == 5
    assert body["purchase_price_rub"] == 1_500_000

    assert set(body["components"]) == {
        "depreciation",
        "fuel",
        "osago",
        "kasko",
        "transport_tax",
        "maintenance",
        "tyres",
    }
    total = body["total_tco_rub"]
    components_sum = sum(c["total_rub"] for c in body["components"].values())
    assert total == components_sum > 0

    yearly = body["yearly"]
    assert len(yearly) == 5
    assert yearly[-1]["cumulative_rub"] == total
    fuel_by_year = [row["by_component"]["fuel"] for row in yearly]
    assert sum(fuel_by_year) == body["components"]["fuel"]["total_rub"]
    assert fuel_by_year[-1] > fuel_by_year[0]

    assert body["components"]["kasko"]["total_rub"] == 0  # disabled by default
    assert body["meta"]["scope_disclaimer_ru"].startswith("Расчёт TCO включает 7")
    assert "Внеплановые ремонты" in body["meta"]["excluded_items_ru"][0]


def test_tco_calculate_kasko_increases_total(api_client: TestClient) -> None:
    base = api_client.post("/api/tco/calculate", json=_valid_request_body())
    body = _valid_request_body()
    body["options"] = {"include_kasko": True, "discount_rate_pct": 0.0}
    with_kasko = api_client.post("/api/tco/calculate", json=body)

    assert base.status_code == 200
    assert with_kasko.status_code == 200
    assert with_kasko.json()["components"]["kasko"]["total_rub"] > 0
    assert with_kasko.json()["total_tco_rub"] > base.json()["total_tco_rub"]


def test_tco_calculate_unknown_modification_404(api_client: TestClient) -> None:
    body = _valid_request_body()
    body["modification_id"] = 9999
    resp = api_client.post("/api/tco/calculate", json=body)
    assert resp.status_code == 404
    assert resp.json()["title"] == "Resource not found"


def test_tco_calculate_validation_422(api_client: TestClient) -> None:
    body = _valid_request_body()
    body["horizon_years"] = 50  # > 10
    resp = api_client.post("/api/tco/calculate", json=body)
    assert resp.status_code == 422
    assert resp.json()["title"] == "Validation error"


def test_tco_calculate_driver_experience_check(api_client: TestClient) -> None:
    body = _valid_request_body()
    body["profile"]["driver_age"] = 20  # type: ignore[index]
    body["profile"]["driver_experience_years"] = 10  # type: ignore[index]
    resp = api_client.post("/api/tco/calculate", json=body)
    assert resp.status_code == 422


def test_tco_calculate_msrp_override(api_client: TestClient) -> None:
    body = _valid_request_body()
    body["purchase_price_rub"] = 2_500_000
    resp = api_client.post("/api/tco/calculate", json=body)
    assert resp.status_code == 200
    assert resp.json()["purchase_price_rub"] == 2_500_000


def test_tco_calculate_per_km_value(api_client: TestClient) -> None:
    resp = api_client.post("/api/tco/calculate", json=_valid_request_body())
    body = resp.json()
    total = body["total_tco_rub"]
    total_km = 15_000 * 5
    assert body["total_tco_per_km_rub"] == round(total / total_km, 2)
