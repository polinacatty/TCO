from __future__ import annotations

import pytest

from app.infrastructure.orm import Base
from app.infrastructure.orm.base import NAMING_CONVENTION

pytestmark = pytest.mark.unit

EXPECTED_TABLES: set[str] = {
    "regions",
    "car_makes",
    "car_models",
    "car_generations",
    "car_modifications",
    "tire_sizes",
    "tire_size_prices",
    "osago_base_tariffs",
    "osago_territory_coefs",
    "osago_power",
    "osago_kbm",
    "osago_age_exp",
    "osago_drivers",
    "osago_seasonal",
    "transport_tax_rates",
    "luxury_cars",
    "depreciation_rates",
    "mileage_penalties",
    "kasko_rates",
    "service_operations",
    "service_plan_ops",
    "parts_costs",
    "labor_rates",
    "fuel_prices",
    "fuel_price_forecast",
    "cbr_rates",
    "ml_models_registry",
    "ml_strategies_registry",
    "users",
    "refresh_tokens",
    "password_reset_tokens",
    "user_profiles",
    "saved_scenarios",
    "scenario_cars",
    "scenario_idempotency_keys",
}


def test_metadata_contains_all_expected_tables() -> None:
    actual = set(Base.metadata.tables.keys())
    missing = EXPECTED_TABLES - actual
    extra = actual - EXPECTED_TABLES
    assert not missing, f"missing ORM tables: {missing}"
    assert not extra, f"unexpected ORM tables: {extra}"


def test_total_table_count() -> None:
    assert len(Base.metadata.tables) == 35


def test_naming_convention_is_consistent() -> None:
    meta = Base.metadata
    assert meta.naming_convention == NAMING_CONVENTION

    for table in meta.tables.values():
        if table.primary_key is not None and table.primary_key.name:
            assert table.primary_key.name.startswith("pk_"), table.primary_key.name
        for fk in table.foreign_keys:
            assert fk.constraint is not None
            assert (fk.constraint.name or "").startswith("fk_"), fk.constraint.name


def test_fuel_price_forecast_table_has_audit_columns() -> None:

    tbl = Base.metadata.tables["fuel_price_forecast"]
    cols = set(tbl.columns.keys())
    required = {
        "region_id", "fuel_type", "price_month", "price_rub_per_l",
        "forecast_origin_month", "horizon_step", "model_version",
        "fallback", "generated_at",
    }
    missing = required - cols
    assert not missing, f"fuel_price_forecast missing columns: {missing}"


def test_fk_targets_are_resolvable() -> None:

    meta = Base.metadata
    for table in meta.tables.values():
        for fk in table.foreign_keys:
            target_table = fk.column.table.name
            target_col = fk.column.name
            assert target_table in meta.tables, (
                f"FK in {table.name}.{fk.parent.name} -> unknown table {target_table}"
            )
            assert target_col in meta.tables[target_table].columns, (
                f"FK in {table.name}.{fk.parent.name} -> "
                f"unknown column {target_table}.{target_col}"
            )
