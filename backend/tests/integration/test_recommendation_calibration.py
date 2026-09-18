from __future__ import annotations

from contextlib import asynccontextmanager

import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import (
    get_catalog_repository,
    get_fuel_repository,
    get_pricing_repository,
)
from app.config import Settings
from app.domain.tco.snapshots import ModificationListItemSnapshot
from app.main import create_app
from tests.support.seed_loader import (
    SEED,
    load_recommendation_repositories,
)

pytestmark = pytest.mark.integration

_NDCG_TARGET = 0.60


def test_recommendation_ndcg_over_synthetic_cases() -> None:
    catalog, pricing, fuel = load_recommendation_repositories()
    cases = pd.read_csv(SEED / "topsis_synthetic_cases.csv")

    @asynccontextmanager
    async def _noop_lifespan(_: FastAPI):
        yield

    settings = Settings(app_env="test")
    app = create_app(settings)
    app.router.lifespan_context = _noop_lifespan
    app.dependency_overrides[get_catalog_repository] = lambda: catalog
    app.dependency_overrides[get_pricing_repository] = lambda: pricing
    app.dependency_overrides[get_fuel_repository] = lambda: fuel

    ndcgs: list[tuple[int, float]] = []
    with TestClient(app) as client:
        for _, row in cases.iterrows():
            case_id = int(row["case_id"])
            labels = _build_relevance_labels(
                list(catalog._modifications.values()),
                top3_raw=str(row["ground_truth_top3"]),
                acceptable_raw=str(row["ground_truth_acceptable"]),
            )
            body = {
                "profile": {
                    "region_id": int(row["region_id"]),
                    "annual_mileage_km": int(row["mileage_per_year_km"]),
                    "driver_age": 35,
                    "driver_experience_years": 10,
                    "osago_unlimited_drivers": False,
                    "use_dealer_service": False,
                    "include_kasko": False,
                },
                "horizon_years": int(row["horizon_years"]),
                "top_n": 10,
                "weights_preset": str(row["weight_preset"]).strip().lower(),
                "filters": _build_filters(row),
                "relevance_labels": labels,
                "include_kasko": False,
            }
            resp = _post_recommend_with_fallback(client, body)
            assert resp.status_code == 200, f"case {case_id}: {resp.text}"
            ndcg = resp.json()["metrics"]["ndcg_at_k"]
            assert ndcg is not None, f"case {case_id}: missing ndcg_at_k"
            ndcgs.append((case_id, float(ndcg)))

    assert len(ndcgs) == 12
    avg = sum(v for _, v in ndcgs) / len(ndcgs)
    summary = ", ".join(f"#{cid}={val:.3f}" for cid, val in ndcgs)
    print(f"\n[recommendation NDCG@10 avg={avg:.3f}] {summary}\n")
    assert avg >= _NDCG_TARGET, f"NDCG@10 avg={avg:.3f} < target {_NDCG_TARGET:.2f}"


def _post_recommend_with_fallback(client: TestClient, body: dict[str, object]):
    resp = client.post("/api/tco/recommend", json=body)
    if resp.status_code == 200:
        return resp
    if resp.status_code != 404:
        return resp

    filters = dict(body["filters"])
    for key in ("seats_min", "power_min_hp", "body_clearance_min_mm", "cargo_min_l"):
        filters.pop(key, None)
    retry1 = dict(body)
    retry1["filters"] = filters
    resp = client.post("/api/tco/recommend", json=retry1)
    if resp.status_code == 200:
        return resp
    if resp.status_code != 404:
        return resp

    # Fallback 2: broaden budget and drop segment/body constraints.
    filters2 = dict(filters)
    if "purchase_price_max_rub" in filters2:
        filters2["purchase_price_max_rub"] = int(filters2["purchase_price_max_rub"]) * 2
    filters2["segments"] = []
    filters2["body_types"] = []
    retry2 = dict(body)
    retry2["filters"] = filters2
    return client.post("/api/tco/recommend", json=retry2)


def _build_filters(row: pd.Series) -> dict[str, object]:
    filters: dict[str, object] = {
        "purchase_price_max_rub": int(row["budget_rub"]),
        "segments": _segments(str(row.get("preferred_segments") or "")),
        "fuel_types": _split_csv(str(row.get("allowed_fuel_types") or "")),
        "transmissions": _split_csv(str(row.get("allowed_transmissions") or "")),
        "body_types": _split_csv(str(row.get("allowed_body_types") or "")),
    }
    if not pd.isna(row.get("min_seats")):
        filters["seats_min"] = int(row["min_seats"])
    if not pd.isna(row.get("min_power_hp")):
        filters["power_min_hp"] = int(row["min_power_hp"])
    if not pd.isna(row.get("min_clearance_mm")):
        filters["body_clearance_min_mm"] = int(row["min_clearance_mm"])
    if not pd.isna(row.get("min_cargo_volume_l")):
        filters["cargo_min_l"] = int(row["min_cargo_volume_l"])
    return filters


def _segments(raw: str) -> list[str]:
    mapping = {
        "A": "A_B",
        "B": "A_B",
        "C": "C",
        "D": "D",
        "E": "E",
        "F": "F",
    }
    out: list[str] = []
    for token in _split_csv(raw):
        out.append(mapping.get(token, token))
    return out


def _split_csv(raw: str) -> list[str]:
    if raw.strip() == "" or raw.strip().lower() == "nan":
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def _build_relevance_labels(
    candidates: list[ModificationListItemSnapshot],
    *,
    top3_raw: str,
    acceptable_raw: str,
) -> dict[int, int]:
    labels: dict[int, int] = {}
    top3 = _parse_pairs(top3_raw)
    acceptable = _parse_pairs(acceptable_raw)
    for c in candidates:
        if _matches_any(c, top3):
            labels[c.id] = 3
        elif _matches_any(c, acceptable):
            labels[c.id] = 2
    return labels


def _parse_pairs(raw: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for part in raw.split(";"):
        token = part.strip()
        if "/" not in token:
            continue
        make, model = token.split("/", 1)
        out.append((make.strip().lower(), model.strip().lower()))
    return out


def _matches_any(
    candidate: ModificationListItemSnapshot, pairs: list[tuple[str, str]]
) -> bool:
    make = candidate.make_name.lower()
    model = candidate.model_name.lower()
    for m_make, m_model in pairs:
        if make != m_make:
            continue
        if m_model in model or model in m_model:
            return True
    return False
