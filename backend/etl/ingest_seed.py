from __future__ import annotations

import sys
from typing import TypedDict

from sqlalchemy import Engine
from sqlalchemy.engine import Connection

from etl._common import (
    coerce,
    get_sync_engine,
    insert_rows,
    logger,
    read_csv_rows,
    seed_dir,
    truncate,
)


class IngestSpec(TypedDict, total=False):
    csv: str
    table: str
    cols: tuple[str, ...]
    int: tuple[str, ...]
    float: tuple[str, ...]
    bool: tuple[str, ...]
    date: tuple[str, ...]
    nullable: tuple[str, ...]


SPECS: list[IngestSpec] = [
    {
        "csv": "regions.csv",
        "table": "regions",
        "cols": ("id", "name", "iso_code", "federal_district",
                 "climate_zone", "population_thousands"),
        "int": ("id", "population_thousands"),
        "nullable": ("population_thousands",),
    },
    {
        "csv": "car_makes.csv",
        "table": "car_makes",
        "cols": ("id", "name", "name_normalized", "country", "brand_tier"),
        "int": ("id",),
    },
    {
        "csv": "car_models.csv",
        "table": "car_models",
        "cols": ("id", "make_id", "name", "name_normalized", "segment", "body_type"),
        "int": ("id", "make_id"),
    },
    {
        "csv": "car_generations.csv",
        "table": "car_generations",
        "cols": ("id", "model_id", "name", "year_from", "year_to", "restyling"),
        "int": ("id", "model_id", "year_from", "year_to", "restyling"),
        "nullable": ("year_to",),
    },
    {
        "csv": "osago_base_tariffs.csv",
        "table": "osago_base_tariffs",
        "cols": ("category_id", "category_label", "vehicle_categories",
                 "owner_type", "tb_min_rub", "tb_max_rub"),
        "int": ("category_id",),
        "float": ("tb_min_rub", "tb_max_rub"),
    },
    {
        "csv": "osago_territory_coefs.csv",
        "table": "osago_territory_coefs",
        "cols": ("region_id", "region_name", "kt_capital_city",
                 "kt_general", "kt_special", "source_ref"),
        "int": ("region_id",),
        "float": ("kt_general", "kt_special"),
        "nullable": ("kt_capital_city", "kt_special", "source_ref"),
    },
    {
        "csv": "osago_power.csv",
        "table": "osago_power",
        "cols": ("vehicle_family", "power_min_hp_excl", "power_max_hp_incl", "km_value"),
        "int": ("power_min_hp_excl", "power_max_hp_incl"),
        "float": ("km_value",),
    },
    {
        "csv": "osago_kbm.csv",
        "table": "osago_kbm",
        "cols": ("kbm_class", "kbm_value", "class_after_no_claim",
                 "class_after_1_claim", "class_after_2_claims",
                 "class_after_3_claims", "class_after_more_than_3_claims"),
        "float": ("kbm_value",),
    },
    {
        "csv": "osago_age_exp.csv",
        "table": "osago_age_exp",
        "cols": ("vehicle_family", "age_min_incl", "age_max_incl",
                 "exp_min_years_incl", "exp_max_years_excl", "kvs_value"),
        "int": ("age_min_incl", "age_max_incl",
                "exp_min_years_incl", "exp_max_years_excl"),
        "float": ("kvs_value",),
    },
    {
        "csv": "osago_drivers.csv",
        "table": "osago_drivers",
        "cols": ("restricted", "owner_type", "ko_value"),
        "bool": ("restricted",),
        "float": ("ko_value",),
    },
    {
        "csv": "osago_seasonal.csv",
        "table": "osago_seasonal",
        "cols": ("period_min_months_excl", "period_max_months_incl", "ks_value"),
        "int": ("period_min_months_excl", "period_max_months_incl"),
        "float": ("ks_value",),
    },
    {
        "csv": "transport_tax_rates.csv",
        "table": "transport_tax_rates",
        "cols": ("region_id", "hp_min", "hp_max", "rate_rub_per_hp"),
        "int": ("region_id",),
        "float": ("hp_min", "hp_max", "rate_rub_per_hp"),
    },
    {
        "csv": "luxury_car_list.csv",
        "table": "luxury_cars",
        "cols": ("make", "model", "engine_type",
                 "engine_volume_l", "price_tier_min_rub"),
        "int": ("price_tier_min_rub",),
        "float": ("engine_volume_l",),
        "nullable": ("engine_type", "engine_volume_l"),
    },
    {
        "csv": "depreciation_rates.csv",
        "table": "depreciation_rates",
        "cols": ("segment", "brand_tier", "age_year_bucket",
                 "annual_depreciation_pct", "source_note", "valid_from"),
        "int": ("age_year_bucket",),
        "float": ("annual_depreciation_pct",),
        "date": ("valid_from",),
        "nullable": ("source_note",),
    },
    {
        "csv": "mileage_penalties.csv",
        "table": "mileage_penalties",
        "cols": ("mileage_threshold_km", "extra_depreciation_pct",
                 "source_note", "valid_from"),
        "int": ("mileage_threshold_km",),
        "float": ("extra_depreciation_pct",),
        "date": ("valid_from",),
        "nullable": ("source_note",),
    },
    {
        "csv": "kasko_rates.csv",
        "table": "kasko_rates",
        "cols": ("brand_tier", "segment", "age_year_bucket", "kasko_rate_pct"),
        "int": ("age_year_bucket",),
        "float": ("kasko_rate_pct",),
    },
    {
        "csv": "service_operations.csv",
        "table": "service_operations",
        "cols": ("id", "code", "name", "default_norm_hours", "category"),
        "int": ("id",),
        "float": ("default_norm_hours",),
    },
    {
        "csv": "service_plan_ops.csv",
        "table": "service_plan_ops",
        "cols": ("generation_id", "operation_id", "every_km", "every_months", "source"),
        "int": ("generation_id", "operation_id", "every_km", "every_months"),
        "nullable": ("every_km", "every_months", "source"),
    },
    {
        "csv": "parts_costs.csv",
        "table": "parts_costs",
        "cols": ("operation_id", "operation_code", "brand_segment", "avg_parts_cost_rub"),
        "int": ("operation_id",),
        "float": ("avg_parts_cost_rub",),
    },
    {
        "csv": "labor_rates.csv",
        "table": "labor_rates",
        "cols": ("region_id", "region_name", "sto_type", "rate_rub_per_hour"),
        "int": ("region_id",),
        "float": ("rate_rub_per_hour",),
    },
    {
        "csv": "tire_size_prices.csv",
        "table": "tire_size_prices",
        "cols": ("size_code", "season", "avg_set_price_rub"),
        "float": ("avg_set_price_rub",),
    },
]


def _ingest_one(conn: Connection, spec: IngestSpec) -> None:
    csv_name = spec["csv"]
    table = spec["table"]
    cols = spec["cols"]
    int_cols = spec.get("int", ())
    float_cols = spec.get("float", ())
    bool_cols = spec.get("bool", ())
    date_cols = spec.get("date", ())
    nullable = spec.get("nullable", ())

    path = seed_dir() / csv_name
    if not path.exists():
        raise FileNotFoundError(path)

    raw = read_csv_rows(path)
    if not raw:
        logger.warning("%s: empty CSV — skip", csv_name)
        return

    if table == "regions" and all((row.get("id") or "").strip() != "0" for row in raw):
        raw.append(
            {
                "id": "0",
                "name": "Российская Федерация (среднее)",
                "iso_code": "RU-AVG",
                "federal_district": "federal",
                "climate_zone": "mixed",
                "population_thousands": "",
            }
        )

    if table == "transport_tax_rates":
        for row in raw:
            if not row.get("hp_max"):
                row["hp_max"] = "9999"

    rows = coerce(
        raw,
        int_cols=int_cols,
        float_cols=float_cols,
        bool_cols=bool_cols,
        date_cols=date_cols,
        nullable=nullable,
    )

    trimmed = [{k: r.get(k) for k in cols} for r in rows]

    if table == "luxury_cars":
        unique: list[dict[str, object]] = []
        seen: set[tuple[object, object, object]] = set()
        for row in trimmed:
            key = (row.get("make"), row.get("model"), row.get("price_tier_min_rub"))
            if key in seen:
                continue
            seen.add(key)
            unique.append(row)
        trimmed = unique

    truncate(conn, table)
    n = insert_rows(conn, table, cols, trimmed)
    logger.info("seed: %-26s -> %-26s  %5d rows", csv_name, table, n)


def run(engine: Engine | None = None) -> int:
    """Залить все seed CSV. Возвращает количество таблиц."""

    eng = engine or get_sync_engine()
    n = 0
    with eng.begin() as conn:
        for spec in SPECS:
            _ingest_one(conn, spec)
            n += 1
    logger.info("seed: done, %d tables", n)
    return n


def main() -> int:
    try:
        run()
    except Exception:
        logger.exception("seed ingest failed")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
