from __future__ import annotations

from fastapi.testclient import TestClient


def test_list_regions(api_client: TestClient) -> None:
    resp = api_client.get("/api/catalog/regions")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 2
    moscow = next(r for r in body if r["name"] == "Москва")
    assert moscow["iso_code"] == "RU-MOW"
    assert moscow["federal_district"] == "ЦФО"


def test_list_makes_no_filter(api_client: TestClient) -> None:
    resp = api_client.get("/api/catalog/makes")
    assert resp.status_code == 200
    body = resp.json()
    assert {m["name"] for m in body} == {"Hyundai", "Toyota"}


def test_list_makes_query(api_client: TestClient) -> None:
    resp = api_client.get("/api/catalog/makes", params={"q": "hyun"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["name"] == "Hyundai"


def test_list_models_by_make(api_client: TestClient) -> None:
    resp = api_client.get("/api/catalog/makes/1/models")
    assert resp.status_code == 200
    body = resp.json()
    assert {m["name"] for m in body} == {"Solaris", "Creta"}


def test_list_models_by_unknown_make_returns_404(api_client: TestClient) -> None:
    resp = api_client.get("/api/catalog/makes/999/models")
    assert resp.status_code == 404
    assert resp.json()["title"] == "Resource not found"


def test_list_generations_by_model(api_client: TestClient) -> None:
    resp = api_client.get("/api/catalog/models/1/generations")
    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["name"] == "II"
    assert body[0]["year_from"] == 2020


def test_list_modifications_by_generation(api_client: TestClient) -> None:
    resp = api_client.get("/api/catalog/generations/1/modifications")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    item = body[0]
    assert item["id"] == 1
    assert item["make"] == "Hyundai"
    assert item["fuel_consumption_combined_l_100km"] == 7.0


def test_get_modification_details(api_client: TestClient) -> None:
    resp = api_client.get("/api/catalog/modifications/1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == 1
    assert body["power_hp"] == 123
    assert body["fuel_type"] == "AI95"


def test_get_modification_not_found(api_client: TestClient) -> None:
    resp = api_client.get("/api/catalog/modifications/9999")
    assert resp.status_code == 404
    assert resp.json()["title"] == "Resource not found"
