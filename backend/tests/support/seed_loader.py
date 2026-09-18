from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import pandas as pd

from app.domain.tco.snapshots import (
    CarSnapshot,
    DepreciationRateSnapshot,
    FuelPriceForecastSnapshot,
    KaskoRateSnapshot,
    LaborRateSnapshot,
    LuxuryCarSnapshot,
    MileagePenaltySnapshot,
    ModificationListItemSnapshot,
    OsagoCoefficientsSnapshot,
    PartsCostSnapshot,
    ServicePlanOpSnapshot,
    TirePriceSnapshot,
    TireSizeSnapshot,
    TransportTaxRateSnapshot,
)
from tests.support.stubs import (
    StubCatalogRepository,
    StubFuelRepository,
    StubPricingRepository,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
SEED = REPO_ROOT / "ml" / "data" / "seed"
PROCESSED = REPO_ROOT / "ml" / "data" / "processed"


def _dec(value: Any) -> Decimal:
    if pd.isna(value):
        return Decimal("0")
    return Decimal(str(value))


def _int(value: Any, default: int = 0) -> int:
    if pd.isna(value):
        return default
    return int(value)


def _opt_int(value: Any) -> int | None:
    if pd.isna(value):
        return None
    return int(value)


def _opt_dec(value: Any) -> Decimal | None:
    if pd.isna(value):
        return None
    return Decimal(str(value))


def load_calibration_repositories() -> tuple[
    StubCatalogRepository,
    dict[int, StubPricingRepository],
    StubFuelRepository,
    dict[int, dict[str, Any]],
]:
    
    cases = pd.read_csv(SEED / "tco_calibration.csv")
    makes = pd.read_csv(SEED / "car_makes.csv")
    models = pd.read_csv(SEED / "car_models.csv")
    generations = pd.read_csv(SEED / "car_generations.csv")
    modifications = pd.read_parquet(PROCESSED / "car_modifications.parquet")

    fuel_prices = pd.read_parquet(PROCESSED / "fuel_prices.parquet")
    depreciation = pd.read_csv(SEED / "depreciation_rates.csv")
    mileage_penalties = pd.read_csv(SEED / "mileage_penalties.csv")
    kasko = pd.read_csv(SEED / "kasko_rates.csv")
    transport_tax = pd.read_csv(SEED / "transport_tax_rates.csv")
    luxury = pd.read_csv(SEED / "luxury_car_list.csv")
    service_ops = pd.read_csv(SEED / "service_operations.csv")
    plan_ops = pd.read_csv(SEED / "service_plan_ops.csv")
    parts_costs = pd.read_csv(SEED / "parts_costs.csv")
    labor_rates = pd.read_csv(SEED / "labor_rates.csv")
    tire_sizes = pd.read_csv(SEED / "tire_sizes.csv")
    tire_prices = pd.read_csv(SEED / "tire_size_prices.csv")
    osago_base = pd.read_csv(SEED / "osago_base_tariffs.csv")
    osago_power = pd.read_csv(SEED / "osago_power.csv")
    osago_territory = pd.read_csv(SEED / "osago_territory_coefs.csv")
    osago_age_exp = pd.read_csv(SEED / "osago_age_exp.csv")
    osago_drivers = pd.read_csv(SEED / "osago_drivers.csv")

    cars: dict[int, CarSnapshot] = {}
    mods_list: dict[int, ModificationListItemSnapshot] = {}
    tire_sizes_by_mod: dict[int, Sequence[TireSizeSnapshot]] = {}
    case_rows: dict[int, dict[str, Any]] = {}

    median_mod_by_generation: dict[int, pd.Series] = {}
    for gen_id, group in modifications.groupby("generation_id"):
        sorted_group = group.sort_values("power_hp")
        median_mod_by_generation[int(gen_id)] = sorted_group.iloc[len(sorted_group) // 2]

    for _, case in cases.iterrows():
        case_id = int(case["case_id"])
        case_rows[case_id] = case.to_dict()

        gen_id = int(case["generation_id"])
        mod = median_mod_by_generation.get(gen_id)
        if mod is None:
            continue

        gen_row = generations[generations["id"] == gen_id].iloc[0]
        model_row = models[models["id"] == int(case["model_id"])].iloc[0]
        make_row = makes[makes["name"] == case["make"]].iloc[0]

        mod_id = int(mod["id"])
        cars[mod_id] = CarSnapshot(
            modification_id=mod_id,
            generation_id=gen_id,
            model_id=int(model_row["id"]),
            make_id=int(make_row["id"]),
            make_name=str(make_row["name"]),
            model_name=str(model_row["name"]),
            brand_tier=str(make_row["brand_tier"]),
            country=str(make_row["country"]),
            segment=str(model_row["segment"]),
            msrp_new_rub=int(case["msrp_new_rub"]),
            power_hp=_int(mod.get("power_hp")),
            engine_volume_l=_opt_dec(mod.get("engine_volume_l")),
            fuel_type=str(mod.get("fuel_type") or "AI95"),
            fuel_consumption_combined_l_100km=_dec(
                mod.get("fuel_consumption_combined_l_100km")
            ),
        )
        mods_list[mod_id] = ModificationListItemSnapshot(
            id=mod_id,
            make_name=str(make_row["name"]),
            model_name=str(model_row["name"]),
            generation_name=str(gen_row["name"]),
            trim_name=str(mod.get("trim_name") or "") or None,
            year_from=_int(gen_row.get("year_from"), 2020),
            year_to=_opt_int(gen_row.get("year_to")),
            body_type=str(model_row.get("body_type", "")),
            segment=str(model_row.get("segment", "C")),
            power_hp=_int(mod.get("power_hp")),
            engine_volume_l=_opt_dec(mod.get("engine_volume_l")),
            fuel_type=str(mod.get("fuel_type") or "AI95"),
            transmission=str(mod.get("transmission", "AT")),
            drive=str(mod.get("drive", "FWD")),
            fuel_consumption_combined_l_100km=_dec(
                mod.get("fuel_consumption_combined_l_100km")
            ),
            msrp_new_rub=int(case["msrp_new_rub"]),
        )

        sizes_df = tire_sizes[tire_sizes["modification_id"] == mod_id]
        tire_sizes_by_mod[mod_id] = tuple(
            TireSizeSnapshot(size_code=str(r["size_code"]), axle=str(r["axle"]))
            for _, r in sizes_df.iterrows()
        )

    tire_prices_snapshots: list[TirePriceSnapshot] = []
    grouped = tire_prices.pivot_table(
        index="size_code", columns="season", values="avg_set_price_rub", aggfunc="first"
    )
    for code, row in grouped.iterrows():
        tire_prices_snapshots.append(
            TirePriceSnapshot(
                size_code=str(code),
                summer_price_rub=_int(row.get("summer"), 18000),
                winter_price_rub=_int(row.get("winter"), 22000),
            )
        )

    catalog = StubCatalogRepository(
        cars=cars,
        modifications=mods_list,
        tire_sizes=tire_sizes_by_mod,
        tire_prices=tire_prices_snapshots,
    )

    transport_tax_rows = [
        TransportTaxRateSnapshot(
            region_id=_int(r["region_id"]),
            hp_min=int(float(r["hp_min"]) if not pd.isna(r["hp_min"]) else 0),
            hp_max=int(float(r["hp_max"]) if not pd.isna(r["hp_max"]) else 99999),
            rate_rub_per_hp=Decimal(str(r["rate_rub_per_hp"])),
        )
        for _, r in transport_tax.iterrows()
    ]

    luxury_rows = [
        LuxuryCarSnapshot(
            make_name=str(r["make"]),
            model_name=str(r["model"]),
            engine_type=(str(r["engine_type"]) if not pd.isna(r["engine_type"]) else None),
            engine_volume_l=_opt_dec(r.get("engine_volume_l")),
            price_tier_min_rub=int(r["price_tier_min_rub"]),
        )
        for _, r in luxury.iterrows()
    ]

    depreciation_rows = [
        DepreciationRateSnapshot(
            segment_6=str(r["segment"]),
            brand_tier=str(r["brand_tier"]),
            age_year_bucket=int(r["age_year_bucket"]),
            annual_depreciation_pct=_dec(r["annual_depreciation_pct"]),
        )
        for _, r in depreciation.iterrows()
    ]
    mileage_rows = [
        MileagePenaltySnapshot(
            mileage_threshold_km=int(r["mileage_threshold_km"]),
            extra_depreciation_pct=_dec(r["extra_depreciation_pct"]),
        )
        for _, r in mileage_penalties.iterrows()
    ]
    kasko_rows = [
        KaskoRateSnapshot(
            brand_tier=str(r["brand_tier"]),
            segment_6=str(r["segment"]),
            age_year_bucket=int(r["age_year_bucket"]),
            kasko_rate_pct=_dec(r["kasko_rate_pct"]),
        )
        for _, r in kasko.iterrows()
    ]

    plan_ops_full = plan_ops.merge(
        service_ops[["id", "code", "default_norm_hours"]],
        left_on="operation_id",
        right_on="id",
        how="left",
    )
    service_plan_by_generation: dict[int, list[ServicePlanOpSnapshot]] = {}
    for _, r in plan_ops_full.iterrows():
        snap = ServicePlanOpSnapshot(
            operation_id=int(r["operation_id"]),
            operation_code=str(r["code"]),
            default_norm_hours=_dec(r["default_norm_hours"]),
            every_km=_opt_int(r["every_km"]),
            every_months=_opt_int(r["every_months"]),
        )
        service_plan_by_generation.setdefault(int(r["generation_id"]), []).append(snap)

    parts_costs_rows = [
        PartsCostSnapshot(
            operation_id=int(r["operation_id"]),
            brand_segment=str(r["brand_segment"]),
            avg_parts_cost_rub=int(float(r["avg_parts_cost_rub"])),
        )
        for _, r in parts_costs.iterrows()
    ]
    labor_rates_map = {
        (int(r["region_id"]), str(r["sto_type"])): LaborRateSnapshot(
            region_id=int(r["region_id"]),
            sto_type=str(r["sto_type"]),
            rate_rub_per_hour=int(float(r["rate_rub_per_hour"])),
        )
        for _, r in labor_rates.iterrows()
    }

    base_row = osago_base[
        (osago_base["vehicle_categories"] == "B,BE")
        & (osago_base["owner_type"] == "physical")
    ].iloc[0]
    tb_min, tb_max = Decimal(str(base_row["tb_min_rub"])), Decimal(str(base_row["tb_max_rub"]))

    def _kt(region_id: int) -> Decimal:
        rows = osago_territory[osago_territory["region_id"] == region_id]
        if rows.empty:
            return Decimal("1.96")
        return Decimal(str(rows.iloc[0]["kt_general"]))

    def _km(power_hp: int) -> Decimal:
        sub = osago_power[osago_power["vehicle_family"] == "B_BE"]
        for _, row in sub.iterrows():
            lo = float(row["power_min_hp_excl"])
            hi = float(row["power_max_hp_incl"])
            if lo < power_hp <= hi:
                return Decimal(str(row["km_value"]))
        return Decimal("1.20")

    kvs_row = osago_age_exp[
        (osago_age_exp["vehicle_family"] == "B_BE_other")
        & (osago_age_exp["age_min_incl"] <= 35)
        & (osago_age_exp["age_max_incl"] >= 35)
        & (osago_age_exp["exp_min_years_incl"] <= 10)
        & (osago_age_exp["exp_max_years_excl"] > 10)
    ].iloc[0]
    kvs_value = Decimal(str(kvs_row["kvs_value"]))

    ko_row = osago_drivers[
        (osago_drivers["restricted"] == True)  # noqa: E712
        & (osago_drivers["owner_type"] == "physical")
    ].iloc[0]
    ko_value = Decimal(str(ko_row["ko_value"]))

    pricing_by_case: dict[int, StubPricingRepository] = {}
    for case_id, case in case_rows.items():
        gen_id = int(case["generation_id"])
        mod_for_case = median_mod_by_generation.get(gen_id)
        power_hp = _int(mod_for_case.get("power_hp")) if mod_for_case is not None else 100
        osago = OsagoCoefficientsSnapshot(
            tb_min_rub=tb_min,
            tb_max_rub=tb_max,
            kt_general=_kt(int(case["region_id"])),
            km_value=_km(power_hp),
            kvs_value=kvs_value,
            ko_value=ko_value,
        )
        pricing_by_case[case_id] = StubPricingRepository(
            transport_tax_rates=transport_tax_rows,
            luxury_matches=luxury_rows,
            osago=osago,
            depreciation_rates=depreciation_rows,
            mileage_penalties=mileage_rows,
            kasko_rates=kasko_rows,
            service_plan_ops=tuple(service_plan_by_generation.get(gen_id, [])),
            parts_costs=parts_costs_rows,
            labor_rates_by_region_sto=labor_rates_map,
        )

    fuel_prices_sorted = fuel_prices.sort_values("price_month")
    last_month = pd.to_datetime(fuel_prices_sorted["price_month"].max())
    next_month = (last_month + pd.offsets.MonthBegin(1)).date()
    forecast_rows: list[FuelPriceForecastSnapshot] = []
    latest = (
        fuel_prices_sorted.groupby(["region_id", "fuel_type"], as_index=False)
        .tail(1)[["region_id", "fuel_type", "price_rub_per_l"]]
    )
    for _, r in latest.iterrows():
        region_id = int(r["region_id"])
        fuel = str(r["fuel_type"])
        last_price = Decimal(str(r["price_rub_per_l"]))
        m = next_month
        for i in range(60):
            forecast_rows.append(
                FuelPriceForecastSnapshot(
                    region_id=region_id,
                    fuel_type=fuel,
                    price_month=m,
                    price_rub_per_l=last_price * (Decimal("1.005") ** i),
                )
            )
            m = (pd.Timestamp(m) + pd.offsets.MonthBegin(1)).date()

    fuel_repo = StubFuelRepository(rows=forecast_rows)
    return catalog, pricing_by_case, fuel_repo, cast(dict[int, dict[str, Any]], case_rows)


def load_recommendation_repositories() -> tuple[
    StubCatalogRepository,
    StubPricingRepository,
    StubFuelRepository,
]:
    makes = pd.read_csv(SEED / "car_makes.csv")
    models = pd.read_csv(SEED / "car_models.csv")
    generations = pd.read_csv(SEED / "car_generations.csv")
    modifications = pd.read_parquet(PROCESSED / "car_modifications.parquet")
    tire_sizes = pd.read_csv(SEED / "tire_sizes.csv")
    tire_prices = pd.read_csv(SEED / "tire_size_prices.csv")

    fuel_prices = pd.read_parquet(PROCESSED / "fuel_prices.parquet")
    depreciation = pd.read_csv(SEED / "depreciation_rates.csv")
    mileage_penalties = pd.read_csv(SEED / "mileage_penalties.csv")
    kasko = pd.read_csv(SEED / "kasko_rates.csv")
    transport_tax = pd.read_csv(SEED / "transport_tax_rates.csv")
    luxury = pd.read_csv(SEED / "luxury_car_list.csv")
    service_ops = pd.read_csv(SEED / "service_operations.csv")
    plan_ops = pd.read_csv(SEED / "service_plan_ops.csv")
    parts_costs = pd.read_csv(SEED / "parts_costs.csv")
    labor_rates = pd.read_csv(SEED / "labor_rates.csv")
    osago_base = pd.read_csv(SEED / "osago_base_tariffs.csv")
    osago_territory = pd.read_csv(SEED / "osago_territory_coefs.csv")
    osago_power = pd.read_csv(SEED / "osago_power.csv")
    osago_age_exp = pd.read_csv(SEED / "osago_age_exp.csv")
    osago_drivers = pd.read_csv(SEED / "osago_drivers.csv")

    makes_idx = makes.set_index("id")
    models_idx = models.set_index("id")
    generations_idx = generations.set_index("id")

    cars: dict[int, CarSnapshot] = {}
    mods_list: dict[int, ModificationListItemSnapshot] = {}
    by_generation: dict[int, list[ModificationListItemSnapshot]] = {}

    for _, mod in modifications.iterrows():
        mod_id = _int(mod["id"])
        gen_id = _int(mod["generation_id"])
        if gen_id not in generations_idx.index:
            continue
        gen_row = generations_idx.loc[gen_id]
        model_id = _int(gen_row["model_id"])
        if model_id not in models_idx.index:
            continue
        model_row = models_idx.loc[model_id]
        make_id = _int(model_row["make_id"])
        if make_id not in makes_idx.index:
            continue
        make_row = makes_idx.loc[make_id]

        cars[mod_id] = CarSnapshot(
            modification_id=mod_id,
            generation_id=gen_id,
            model_id=model_id,
            make_id=make_id,
            make_name=str(make_row["name"]),
            model_name=str(model_row["name"]),
            brand_tier=str(make_row["brand_tier"]),
            country=str(make_row["country"]),
            segment=str(model_row["segment"]),
            msrp_new_rub=_int(mod.get("msrp_new_rub")),
            power_hp=_int(mod.get("power_hp")),
            engine_volume_l=_opt_dec(mod.get("engine_volume_l")),
            fuel_type=str(mod.get("fuel_type") or "AI95"),
            fuel_consumption_combined_l_100km=_dec(
                mod.get("fuel_consumption_combined_l_100km")
            ),
        )
        item = ModificationListItemSnapshot(
            id=mod_id,
            make_name=str(make_row["name"]),
            model_name=str(model_row["name"]),
            generation_name=str(gen_row["name"]),
            trim_name=str(mod.get("trim_name") or "") or None,
            year_from=_int(gen_row.get("year_from"), 2020),
            year_to=_opt_int(gen_row.get("year_to")),
            body_type=str(model_row.get("body_type", "")),
            segment=str(model_row.get("segment", "C")),
            power_hp=_int(mod.get("power_hp")),
            engine_volume_l=_opt_dec(mod.get("engine_volume_l")),
            fuel_type=str(mod.get("fuel_type") or "AI95"),
            transmission=str(mod.get("transmission") or "AT"),
            drive=str(mod.get("drive") or "FWD"),
            fuel_consumption_combined_l_100km=_dec(
                mod.get("fuel_consumption_combined_l_100km")
            ),
            msrp_new_rub=_int(mod.get("msrp_new_rub")),
            reliability_score=float(mod.get("reliability_score") or 0.5),
            cargo_volume_l=_opt_int(mod.get("cargo_volume_l")),
            seats=_opt_int(mod.get("seats")),
            body_clearance_mm=_opt_int(mod.get("body_clearance_mm")),
        )
        mods_list[mod_id] = item
        by_generation.setdefault(gen_id, []).append(item)

    tire_sizes_by_mod: dict[int, Sequence[TireSizeSnapshot]] = {}
    for mod_id, group in tire_sizes.groupby("modification_id"):
        tire_sizes_by_mod[int(mod_id)] = tuple(
            TireSizeSnapshot(size_code=str(r["size_code"]), axle=str(r["axle"]))
            for _, r in group.iterrows()
        )

    tire_prices_snapshots: list[TirePriceSnapshot] = []
    grouped = tire_prices.pivot_table(
        index="size_code", columns="season", values="avg_set_price_rub", aggfunc="first"
    )
    for code, row in grouped.iterrows():
        tire_prices_snapshots.append(
            TirePriceSnapshot(
                size_code=str(code),
                summer_price_rub=_int(row.get("summer"), 18_000),
                winter_price_rub=_int(row.get("winter"), 22_000),
            )
        )

    catalog = StubCatalogRepository(
        cars=cars,
        modifications=mods_list,
        tire_sizes=tire_sizes_by_mod,
        tire_prices=tire_prices_snapshots,
        modifications_by_generation=by_generation,
    )

    transport_tax_rows = [
        TransportTaxRateSnapshot(
            region_id=_int(r["region_id"]),
            hp_min=int(float(r["hp_min"]) if not pd.isna(r["hp_min"]) else 0),
            hp_max=int(float(r["hp_max"]) if not pd.isna(r["hp_max"]) else 99999),
            rate_rub_per_hp=Decimal(str(r["rate_rub_per_hp"])),
        )
        for _, r in transport_tax.iterrows()
    ]
    luxury_rows = [
        LuxuryCarSnapshot(
            make_name=str(r["make"]),
            model_name=str(r["model"]),
            engine_type=(str(r["engine_type"]) if not pd.isna(r["engine_type"]) else None),
            engine_volume_l=_opt_dec(r.get("engine_volume_l")),
            price_tier_min_rub=int(r["price_tier_min_rub"]),
        )
        for _, r in luxury.iterrows()
    ]
    depreciation_rows = [
        DepreciationRateSnapshot(
            segment_6=str(r["segment"]),
            brand_tier=str(r["brand_tier"]),
            age_year_bucket=int(r["age_year_bucket"]),
            annual_depreciation_pct=_dec(r["annual_depreciation_pct"]),
        )
        for _, r in depreciation.iterrows()
    ]
    mileage_rows = [
        MileagePenaltySnapshot(
            mileage_threshold_km=int(r["mileage_threshold_km"]),
            extra_depreciation_pct=_dec(r["extra_depreciation_pct"]),
        )
        for _, r in mileage_penalties.iterrows()
    ]
    kasko_rows = [
        KaskoRateSnapshot(
            brand_tier=str(r["brand_tier"]),
            segment_6=str(r["segment"]),
            age_year_bucket=int(r["age_year_bucket"]),
            kasko_rate_pct=_dec(r["kasko_rate_pct"]),
        )
        for _, r in kasko.iterrows()
    ]

    plan_ops_full = plan_ops.merge(
        service_ops[["id", "code", "default_norm_hours"]],
        left_on="operation_id",
        right_on="id",
        how="left",
    )
    service_plan_by_generation: dict[int, list[ServicePlanOpSnapshot]] = {}
    for _, r in plan_ops_full.iterrows():
        snap = ServicePlanOpSnapshot(
            operation_id=int(r["operation_id"]),
            operation_code=str(r["code"]),
            default_norm_hours=_dec(r["default_norm_hours"]),
            every_km=_opt_int(r["every_km"]),
            every_months=_opt_int(r["every_months"]),
        )
        service_plan_by_generation.setdefault(int(r["generation_id"]), []).append(snap)

    parts_costs_rows = [
        PartsCostSnapshot(
            operation_id=int(r["operation_id"]),
            brand_segment=str(r["brand_segment"]),
            avg_parts_cost_rub=int(float(r["avg_parts_cost_rub"])),
        )
        for _, r in parts_costs.iterrows()
    ]
    labor_rates_map = {
        (int(r["region_id"]), str(r["sto_type"])): LaborRateSnapshot(
            region_id=int(r["region_id"]),
            sto_type=str(r["sto_type"]),
            rate_rub_per_hour=int(float(r["rate_rub_per_hour"])),
        )
        for _, r in labor_rates.iterrows()
    }

    base_row = osago_base[
        (osago_base["vehicle_categories"] == "B,BE")
        & (osago_base["owner_type"] == "physical")
    ].iloc[0]
    tb_min, tb_max = Decimal(str(base_row["tb_min_rub"])), Decimal(str(base_row["tb_max_rub"]))
    ko_row = osago_drivers[
        (osago_drivers["restricted"] == True)  # noqa: E712
        & (osago_drivers["owner_type"] == "physical")
    ].iloc[0]
    ko_value = Decimal(str(ko_row["ko_value"]))
    kvs_row = osago_age_exp[
        (osago_age_exp["vehicle_family"] == "B_BE_other")
        & (osago_age_exp["age_min_incl"] <= 35)
        & (osago_age_exp["age_max_incl"] >= 35)
        & (osago_age_exp["exp_min_years_incl"] <= 10)
        & (osago_age_exp["exp_max_years_excl"] > 10)
    ].iloc[0]
    kvs_value = Decimal(str(kvs_row["kvs_value"]))

    def _kt(region_id: int) -> Decimal:
        rows = osago_territory[osago_territory["region_id"] == region_id]
        if rows.empty:
            return Decimal("1.96")
        return Decimal(str(rows.iloc[0]["kt_general"]))

    def _km(power_hp: int) -> Decimal:
        sub = osago_power[osago_power["vehicle_family"] == "B_BE"]
        for _, row in sub.iterrows():
            lo = float(row["power_min_hp_excl"])
            hi = float(row["power_max_hp_incl"])
            if lo < power_hp <= hi:
                return Decimal(str(row["km_value"]))
        return Decimal("1.20")

    pricing = StubPricingRepository(
        transport_tax_rates=transport_tax_rows,
        luxury_matches=luxury_rows,
        osago=OsagoCoefficientsSnapshot(
            tb_min_rub=tb_min,
            tb_max_rub=tb_max,
            kt_general=_kt(1),
            km_value=_km(120),
            kvs_value=kvs_value,
            ko_value=ko_value,
        ),
        depreciation_rates=depreciation_rows,
        mileage_penalties=mileage_rows,
        kasko_rates=kasko_rows,
        service_plan_ops_by_generation=service_plan_by_generation,
        parts_costs=parts_costs_rows,
        labor_rates_by_region_sto=labor_rates_map,
    )

    fuel_prices_sorted = fuel_prices.sort_values("price_month")
    last_month = pd.to_datetime(fuel_prices_sorted["price_month"].max())
    next_month = (last_month + pd.offsets.MonthBegin(1)).date()
    forecast_rows: list[FuelPriceForecastSnapshot] = []
    latest = (
        fuel_prices_sorted.groupby(["region_id", "fuel_type"], as_index=False)
        .tail(1)[["region_id", "fuel_type", "price_rub_per_l"]]
    )
    for _, r in latest.iterrows():
        region_id = int(r["region_id"])
        fuel = str(r["fuel_type"])
        last_price = Decimal(str(r["price_rub_per_l"]))
        m = next_month
        for i in range(60):
            forecast_rows.append(
                FuelPriceForecastSnapshot(
                    region_id=region_id,
                    fuel_type=fuel,
                    price_month=m,
                    price_rub_per_l=last_price * (Decimal("1.005") ** i),
                )
            )
            m = (pd.Timestamp(m) + pd.offsets.MonthBegin(1)).date()

    return catalog, pricing, StubFuelRepository(rows=forecast_rows)


__all__ = [
    "load_calibration_repositories",
    "load_recommendation_repositories",
    "REPO_ROOT",
    "SEED",
    "PROCESSED",
]
