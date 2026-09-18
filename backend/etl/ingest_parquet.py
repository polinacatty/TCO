from __future__ import annotations

import math
import sys
from typing import Any, cast

import pandas as pd
from sqlalchemy import Engine
from sqlalchemy.engine import Connection

from etl._common import (
    coerce,
    get_sync_engine,
    insert_rows,
    logger,
    processed_dir,
    read_csv_rows,
    seed_dir,
    truncate,
)

# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #


def _is_missing(value: object) -> bool:

    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    try:
        result = pd.isna(cast(Any, value))
    except (TypeError, ValueError):
        return False
    if hasattr(result, "__len__"):
        return False
    return bool(result)


def _df_to_records(df: pd.DataFrame) -> list[dict[str, Any]]:

    records = cast(list[dict[str, Any]], df.to_dict(orient="records"))
    for r in records:
        for k, v in r.items():
            if _is_missing(v):
                r[k] = None
    return records


# --------------------------------------------------------------------------- #
# car_modifications                                                           #
# --------------------------------------------------------------------------- #


_CAR_MODS_COLS = (
    "id", "generation_id", "trim_name", "engine_volume_l", "power_hp",
    "torque_nm", "fuel_type", "transmission", "drive",
    "fuel_consumption_combined_l_100km", "fuel_consumption_city_l_100km",
    "fuel_consumption_highway_l_100km",
    "length_mm", "width_mm", "height_mm", "curb_weight_kg",
    "seats", "cargo_volume_l", "body_clearance_mm",
    "msrp_new_rub", "reliability_score",
    "msrp_source", "reliability_source", "enriched_at",
)


def _ingest_car_modifications(conn: Connection) -> int:
    path = processed_dir() / "car_modifications.parquet"
    df = pd.read_parquet(path)
    records = _df_to_records(df)
    truncate(conn, "car_modifications")
    n = insert_rows(conn, "car_modifications", _CAR_MODS_COLS, records)
    logger.info("parquet: car_modifications -> %d rows", n)
    return n


# --------------------------------------------------------------------------- #
# tire_sizes (csv, но FK к car_modifications)                                 #
# --------------------------------------------------------------------------- #


def _ingest_tire_sizes(conn: Connection) -> int:
    path = seed_dir() / "tire_sizes.csv"
    raw = read_csv_rows(path)
    rows = coerce(
        raw,
        int_cols=("modification_id",),
        bool_cols=("is_default",),
    )
    cols = ("modification_id", "axle", "size_code", "is_default")
    trimmed = [{k: r.get(k) for k in cols} for r in rows]
    truncate(conn, "tire_sizes")
    n = insert_rows(conn, "tire_sizes", cols, trimmed)
    logger.info("csv (post-mods): tire_sizes -> %d rows", n)
    return n


# --------------------------------------------------------------------------- #
# fuel_prices                                                                 #
# --------------------------------------------------------------------------- #


_FUEL_PRICES_COLS = (
    "region_id", "fuel_type", "price_rub_per_l", "price_month",
    "source", "ingested_at",
)


def _ingest_fuel_prices(conn: Connection) -> int:
    path = processed_dir() / "fuel_prices.parquet"
    df = pd.read_parquet(path)
    records = _df_to_records(df)
    truncate(conn, "fuel_prices")
    n = insert_rows(conn, "fuel_prices", _FUEL_PRICES_COLS, records)
    logger.info("parquet: fuel_prices -> %d rows", n)
    return n


# --------------------------------------------------------------------------- #
# cbr_rates                                                                   #
# --------------------------------------------------------------------------- #


_CBR_RATES_COLS = ("metric_date", "metric_type", "value", "source")


def _ingest_cbr_rates(conn: Connection) -> int:
    path = processed_dir() / "cbr_rates.parquet"
    df = pd.read_parquet(path)
    records = _df_to_records(df)
    truncate(conn, "cbr_rates")
    n = insert_rows(conn, "cbr_rates", _CBR_RATES_COLS, records)
    logger.info("parquet: cbr_rates -> %d rows", n)
    return n


# --------------------------------------------------------------------------- #
# Orchestrator                                                                #
# --------------------------------------------------------------------------- #


def run(engine: Engine | None = None) -> int:
    eng = engine or get_sync_engine()
    total = 0
    with eng.begin() as conn:
        total += _ingest_car_modifications(conn)
        total += _ingest_tire_sizes(conn)
        total += _ingest_fuel_prices(conn)
        total += _ingest_cbr_rates(conn)
    logger.info("parquet: done, %d rows total", total)
    return total


def main() -> int:
    try:
        run()
    except Exception:
        logger.exception("parquet ingest failed")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
