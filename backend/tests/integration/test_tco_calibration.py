from __future__ import annotations

from contextlib import asynccontextmanager

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import (
    get_catalog_repository,
    get_fuel_repository,
    get_pricing_repository,
)
from app.config import Settings
from app.main import create_app
from tests.support.seed_loader import load_calibration_repositories

pytestmark = pytest.mark.integration

_MAPE_TARGET = 25.0


def test_tco_calibration_mape_under_target() -> None:
    catalog, pricing_by_case, fuel, case_rows = load_calibration_repositories()

    apes: list[tuple[int, float, int, int]] = []
    for case_id, case in case_rows.items():
        observed = int(case["observed_total_tco_rub"])
        pricing = pricing_by_case[case_id]

        @asynccontextmanager
        async def _noop_lifespan(_: FastAPI):
            yield

        settings = Settings(app_env="test")
        app = create_app(settings)
        app.router.lifespan_context = _noop_lifespan
        app.dependency_overrides[get_catalog_repository] = lambda c=catalog: c
        app.dependency_overrides[get_pricing_repository] = lambda p=pricing: p
        app.dependency_overrides[get_fuel_repository] = lambda f=fuel: f

        gen_id = int(case["generation_id"])
        modification_id = next(
            mod_id
            for mod_id, snap in catalog._cars.items()
            if snap.generation_id == gen_id
        )

        body = {
            "modification_id": modification_id,
            "purchase_price_rub": int(case["msrp_new_rub"]),
            "year_of_manufacture": int(case["year_of_purchase"]),
            "horizon_years": int(case["owner_horizon_years"]),
            "profile": {
                "region_id": int(case["region_id"]),
                "annual_mileage_km": int(case["mileage_per_year_km"]),
                "driver_age": 35,
                "driver_experience_years": 10,
                "osago_unlimited_drivers": False,
                "use_dealer_service": case["sto_type"] == "dealer",
                "include_kasko": False,
            },
            "options": {"include_kasko": False},
        }

        with TestClient(app) as client:
            resp = client.post("/api/tco/calculate", json=body)
        assert resp.status_code == 200, resp.text
        predicted = int(resp.json()["total_tco_rub"])
        ape = abs(predicted - observed) / observed * 100.0
        apes.append((case_id, ape, predicted, observed))

    n = len(apes)
    mape = sum(ape for _, ape, _, _ in apes) / n
    summary = " | ".join(
        f"#{cid}: pred={pred:>10,} obs={obs:>10,} ape={ape:5.1f}%"
        for cid, ape, pred, obs in sorted(apes)
    )
    print(f"\n[calibration MAPE = {mape:.2f}% on {n} cases]\n{summary}\n")

    assert all(pred > 0 for _, _, pred, _ in apes)

    assert mape <= _MAPE_TARGET, f"MAPE = {mape:.2f}% exceeds target {_MAPE_TARGET}%"
