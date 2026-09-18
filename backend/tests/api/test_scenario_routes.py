from __future__ import annotations

from fastapi.testclient import TestClient


def _auth_headers(client: TestClient) -> dict[str, str]:
    resp = client.post(
        "/api/auth/register",
        json={
            "email": "scenario@example.com",
            "password": "StrongPass123!",
            "pdn_consent": True,
        },
    )
    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _payload() -> dict[str, object]:
    return {
        "name": "Family scenario",
        "modifications": [
            {"modification_id": 1, "custom_purchase_price_rub": 1_450_000, "age_at_purchase_months": 0},
            {"modification_id": 2, "custom_purchase_price_rub": 1_850_000, "age_at_purchase_months": 0},
        ],
        "horizon_years": 5,
        "profile": {
            "region_id": 1,
            "annual_mileage_km": 15000,
            "driver_age": 35,
            "driver_experience_years": 10,
            "osago_unlimited_drivers": False,
            "use_dealer_service": False,
            "include_kasko": False,
            "weights_preset": "balanced",
        },
        "options": {"include_kasko": False, "discount_rate_pct": 0.0},
    }


def test_scenario_crud_and_recalculate(api_client: TestClient) -> None:
    headers = _auth_headers(api_client)

    create = api_client.post(
        "/api/scenarios",
        json=_payload(),
        headers={**headers, "Idempotency-Key": "key-1"},
    )
    assert create.status_code == 201, create.text
    created = create.json()
    scenario_id = created["id"]
    assert len(created["cars"]) == 2
    assert created["summary_total_tco_rub"] > 0

    idem = api_client.post(
        "/api/scenarios",
        json=_payload(),
        headers={**headers, "Idempotency-Key": "key-1"},
    )
    assert idem.status_code == 201
    assert idem.json()["id"] == scenario_id

    listed = api_client.get("/api/scenarios", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 1

    get_one = api_client.get(f"/api/scenarios/{scenario_id}", headers=headers)
    assert get_one.status_code == 200
    assert get_one.json()["id"] == scenario_id

    update_payload = _payload()
    update_payload["name"] = "Updated scenario"
    update = api_client.put(f"/api/scenarios/{scenario_id}", json=update_payload, headers=headers)
    assert update.status_code == 200
    assert update.json()["name"] == "Updated scenario"

    recalc = api_client.post(f"/api/scenarios/{scenario_id}/recalculate", headers=headers)
    assert recalc.status_code == 200
    assert recalc.json()["summary_total_tco_rub"] > 0

    delete = api_client.delete(f"/api/scenarios/{scenario_id}", headers=headers)
    assert delete.status_code == 204
    missing = api_client.get(f"/api/scenarios/{scenario_id}", headers=headers)
    assert missing.status_code == 404


def test_scenario_cursor_pagination_and_duplicate_guard(api_client: TestClient) -> None:
    headers = _auth_headers(api_client)
    for idx in range(3):
        payload = _payload()
        payload["name"] = f"Scenario {idx}"
        created = api_client.post(
            "/api/scenarios",
            json=payload,
            headers={**headers, "Idempotency-Key": f"page-{idx}"},
        )
        assert created.status_code == 201, created.text

    page1 = api_client.get("/api/scenarios?limit=2", headers=headers)
    assert page1.status_code == 200
    body1 = page1.json()
    assert len(body1["items"]) == 2
    assert body1["has_more"] is True
    assert body1["next_cursor"] is not None

    page2 = api_client.get(f"/api/scenarios?limit=2&cursor={body1['next_cursor']}", headers=headers)
    assert page2.status_code == 200
    body2 = page2.json()
    assert len(body2["items"]) == 1
    assert body2["has_more"] is False
    assert body2["next_cursor"] is None

    bad_payload = _payload()
    bad_payload["modifications"] = [
        {"modification_id": 1, "custom_purchase_price_rub": 1_450_000, "age_at_purchase_months": 0},
        {"modification_id": 1, "custom_purchase_price_rub": 1_500_000, "age_at_purchase_months": 0},
    ]
    dup = api_client.post("/api/scenarios", json=bad_payload, headers=headers)
    assert dup.status_code == 422
    assert "duplicate modification_id" in dup.json()["detail"]
