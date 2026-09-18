from __future__ import annotations

from fastapi.testclient import TestClient


def _token(client: TestClient) -> str:
    resp = client.post(
        "/api/auth/register",
        json={
            "email": "profile@example.com",
            "password": "StrongPass123!",
            "pdn_consent": True,
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    token = data.get("access_token")
    assert isinstance(token, str)
    return token


def test_profile_put_get_delete(api_client: TestClient) -> None:
    token = _token(api_client)
    headers = {"Authorization": f"Bearer {token}"}

    put = api_client.put(
        "/api/profile",
        json={
            "region_id": 1,
            "annual_mileage_km": 20000,
            "driver_age": 30,
            "driver_experience_years": 8,
            "osago_unlimited_drivers": False,
            "use_dealer_service": True,
            "include_kasko": True,
            "weights_preset": "family",
        },
        headers=headers,
    )
    assert put.status_code == 200, put.text
    assert put.json()["weights_preset"] == "family"

    get = api_client.get("/api/profile", headers=headers)
    assert get.status_code == 200
    assert get.json()["include_kasko"] is True

    preset = api_client.post("/api/profile/preset", json={"preset": "balanced"}, headers=headers)
    assert preset.status_code == 200
    assert preset.json()["weights_preset"] == "balanced"

    delete = api_client.delete("/api/profile", headers=headers)
    assert delete.status_code == 204

    missing = api_client.get("/api/profile", headers=headers)
    assert missing.status_code == 404


def test_profile_requires_auth(api_client: TestClient) -> None:
    resp = api_client.get("/api/profile")
    assert resp.status_code == 401

