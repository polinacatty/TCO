from __future__ import annotations

from collections.abc import Iterator
from contextlib import asynccontextmanager
from datetime import date
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import (
    get_auth_repository,
    get_catalog_repository,
    get_fuel_repository,
    get_password_reset_notifier,
    get_pricing_repository,
    get_scenario_repository,
)
from app.config import Settings
from app.core.metrics import metrics_registry
from app.core.rate_limit import rate_limiter
from app.domain.tco.snapshots import (
    CarSnapshot,
    DepreciationRateSnapshot,
    FuelPriceForecastSnapshot,
    GenerationSnapshot,
    KaskoRateSnapshot,
    LaborRateSnapshot,
    MakeSnapshot,
    MileagePenaltySnapshot,
    ModelSnapshot,
    ModificationListItemSnapshot,
    OsagoCoefficientsSnapshot,
    PartsCostSnapshot,
    RegionSnapshot,
    ServicePlanOpSnapshot,
    TirePriceSnapshot,
    TireSizeSnapshot,
    TransportTaxRateSnapshot,
)
from app.main import create_app
from tests.support.stubs import (
    StubAuthRepository,
    StubCatalogRepository,
    StubFuelRepository,
    StubPasswordResetNotifier,
    StubPricingRepository,
    StubScenarioRepository,
)


def _build_fuel_forecast() -> tuple[FuelPriceForecastSnapshot, ...]:
    months: list[FuelPriceForecastSnapshot] = []
    year, month = date.today().year, date.today().month
    for i in range(60):
        months.append(
            FuelPriceForecastSnapshot(
                region_id=1,
                fuel_type="ai95",
                price_month=date(year, month, 1),
                price_rub_per_l=Decimal("60") + Decimal("0.25") * Decimal(i),
            )
        )
        month += 1
        if month > 12:
            month = 1
            year += 1
    return tuple(months)


@pytest.fixture
def stub_catalog() -> StubCatalogRepository:
    car = CarSnapshot(
        modification_id=1,
        generation_id=1,
        model_id=1,
        make_id=1,
        make_name="Hyundai",
        model_name="Solaris",
        brand_tier="mass",
        country="South Korea",
        segment="B",
        msrp_new_rub=1_500_000,
        power_hp=123,
        engine_volume_l=Decimal("1.6"),
        fuel_type="AI95",
        fuel_consumption_combined_l_100km=Decimal("7.0"),
    )
    car2 = CarSnapshot(
        modification_id=2,
        generation_id=2,
        model_id=2,
        make_id=2,
        make_name="Toyota",
        model_name="Corolla",
        brand_tier="japanese_korean_mass",
        country="Japan",
        segment="C",
        msrp_new_rub=1_850_000,
        power_hp=132,
        engine_volume_l=Decimal("1.8"),
        fuel_type="AI95",
        fuel_consumption_combined_l_100km=Decimal("6.8"),
    )
    mod_item = ModificationListItemSnapshot(
        id=1,
        make_name="Hyundai",
        model_name="Solaris",
        generation_name="II",
        trim_name="Comfort",
        year_from=2020,
        year_to=None,
        body_type="sedan",
        segment="B",
        power_hp=123,
        engine_volume_l=Decimal("1.6"),
        fuel_type="AI95",
        transmission="AT",
        drive="FWD",
        fuel_consumption_combined_l_100km=Decimal("7.0"),
        msrp_new_rub=1_500_000,
        reliability_score=0.78,
        cargo_volume_l=480,
        seats=5,
        body_clearance_mm=160,
    )
    mod_item2 = ModificationListItemSnapshot(
        id=2,
        make_name="Toyota",
        model_name="Corolla",
        generation_name="XII",
        trim_name="Prestige",
        year_from=2021,
        year_to=None,
        body_type="sedan",
        segment="C",
        power_hp=132,
        engine_volume_l=Decimal("1.8"),
        fuel_type="AI95",
        transmission="CVT",
        drive="FWD",
        fuel_consumption_combined_l_100km=Decimal("6.8"),
        msrp_new_rub=1_850_000,
        reliability_score=0.91,
        cargo_volume_l=520,
        seats=5,
        body_clearance_mm=150,
    )
    return StubCatalogRepository(
        cars={1: car, 2: car2},
        modifications={1: mod_item, 2: mod_item2},
        tire_sizes={
            1: (TireSizeSnapshot(size_code="195/55 R16", axle="both"),),
            2: (TireSizeSnapshot(size_code="205/55 R16", axle="both"),),
        },
        tire_prices=(
            TirePriceSnapshot(
                size_code="195/55 R16", summer_price_rub=20_000, winter_price_rub=24_000
            ),
            TirePriceSnapshot(
                size_code="205/55 R16", summer_price_rub=22_000, winter_price_rub=27_000
            ),
        ),
        regions=(
            RegionSnapshot(
                id=1,
                name="Москва",
                iso_code="RU-MOW",
                federal_district="ЦФО",
                climate_zone="central",
            ),
            RegionSnapshot(
                id=2,
                name="Санкт-Петербург",
                iso_code="RU-SPE",
                federal_district="СЗФО",
                climate_zone="central",
            ),
        ),
        makes=(
            MakeSnapshot(id=1, name="Hyundai", country="South Korea", brand_tier="mass"),
            MakeSnapshot(id=2, name="Toyota", country="Japan", brand_tier="japanese_korean_mass"),
        ),
        models_by_make={
            1: (
                ModelSnapshot(id=1, make_id=1, name="Solaris", segment="B", body_type="sedan"),
                ModelSnapshot(id=2, make_id=1, name="Creta", segment="J_CROSS", body_type="suv"),
            )
        },
        generations_by_model={
            1: (
                GenerationSnapshot(
                    id=1, model_id=1, name="II", year_from=2020, year_to=None, restyling=0
                ),
            ),
            2: (
                GenerationSnapshot(
                    id=2, model_id=2, name="XII", year_from=2021, year_to=None, restyling=0
                ),
            ),
        },
        modifications_by_generation={1: (mod_item,), 2: (mod_item2,)},
    )


@pytest.fixture
def stub_pricing() -> StubPricingRepository:
    return StubPricingRepository(
        transport_tax_rates=(
            TransportTaxRateSnapshot(
                region_id=1, hp_min=100, hp_max=125, rate_rub_per_hp=Decimal("25")
            ),
        ),
        depreciation_rates=tuple(
            DepreciationRateSnapshot(
                segment_6="A_B",
                brand_tier="mass",
                age_year_bucket=i + 1,
                annual_depreciation_pct=Decimal(str(p)),
            )
            for i, p in enumerate([15, 12, 10, 9, 8])
        ),
        mileage_penalties=(
            MileagePenaltySnapshot(
                mileage_threshold_km=75_000, extra_depreciation_pct=Decimal("3")
            ),
        ),
        kasko_rates=tuple(
            KaskoRateSnapshot(
                brand_tier="mass",
                segment_6="A_B",
                age_year_bucket=i + 1,
                kasko_rate_pct=Decimal("4.5"),
            )
            for i in range(5)
        ),
        service_plan_ops=(
            ServicePlanOpSnapshot(
                operation_id=1,
                operation_code="oil_change",
                default_norm_hours=Decimal("0.7"),
                every_km=15_000,
                every_months=12,
            ),
            ServicePlanOpSnapshot(
                operation_id=2,
                operation_code="tyre_swap_seasonal",
                default_norm_hours=Decimal("1.0"),
                every_km=None,
                every_months=6,
            ),
        ),
        parts_costs=(
            PartsCostSnapshot(operation_id=1, brand_segment="korean", avg_parts_cost_rub=4_500),
            PartsCostSnapshot(operation_id=2, brand_segment="korean", avg_parts_cost_rub=0),
        ),
        labor_rates_by_region_sto={
            (1, "independent"): LaborRateSnapshot(
                region_id=1, sto_type="independent", rate_rub_per_hour=2_000
            ),
            (1, "dealer"): LaborRateSnapshot(
                region_id=1, sto_type="dealer", rate_rub_per_hour=4_500
            ),
        },
        osago=OsagoCoefficientsSnapshot(
            tb_min_rub=Decimal("1399"),
            tb_max_rub=Decimal("8665"),
            kt_general=Decimal("1.96"),
            km_value=Decimal("1.20"),
            kvs_value=Decimal("0.95"),
            ko_value=Decimal("1.00"),
        ),
    )


@pytest.fixture
def stub_fuel() -> StubFuelRepository:
    return StubFuelRepository(rows=_build_fuel_forecast())


@pytest.fixture
def stub_auth() -> StubAuthRepository:
    return StubAuthRepository()


@pytest.fixture
def stub_password_reset_notifier() -> StubPasswordResetNotifier:
    return StubPasswordResetNotifier()


@pytest.fixture
def stub_scenario() -> StubScenarioRepository:
    return StubScenarioRepository()


@pytest.fixture
def api_app(
    stub_catalog: StubCatalogRepository,
    stub_pricing: StubPricingRepository,
    stub_fuel: StubFuelRepository,
    stub_auth: StubAuthRepository,
    stub_password_reset_notifier: StubPasswordResetNotifier,
    stub_scenario: StubScenarioRepository,
) -> FastAPI:
    """FastAPI application with stub repositories and a noop lifespan."""

    @asynccontextmanager
    async def _noop_lifespan(_: FastAPI):  # type: ignore[no-untyped-def]
        yield

    settings = Settings(app_env="test")
    rate_limiter.reset()
    metrics_registry.reset()
    app = create_app(settings)
    app.router.lifespan_context = _noop_lifespan
    app.dependency_overrides[get_catalog_repository] = lambda: stub_catalog
    app.dependency_overrides[get_pricing_repository] = lambda: stub_pricing
    app.dependency_overrides[get_fuel_repository] = lambda: stub_fuel
    app.dependency_overrides[get_auth_repository] = lambda: stub_auth
    app.dependency_overrides[get_scenario_repository] = lambda: stub_scenario
    app.dependency_overrides[get_password_reset_notifier] = (
        lambda: stub_password_reset_notifier
    )
    return app


@pytest.fixture
def api_client(api_app: FastAPI) -> Iterator[TestClient]:
    with TestClient(api_app) as client:
        yield client
