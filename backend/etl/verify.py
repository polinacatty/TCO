from __future__ import annotations

import sys

from sqlalchemy import Engine, text

from app.infrastructure.orm import Base
from etl._common import get_sync_engine, logger

EXPECTED_MIN: dict[str, int] = {
    # Catalog
    "regions": 80,
    "car_makes": 50,
    "car_models": 200,
    "car_generations": 200,
    "car_modifications": 800,
    "tire_sizes": 900,
    "tire_size_prices": 100,
    # ОСАГО
    "osago_base_tariffs": 1,
    "osago_territory_coefs": 80,
    "osago_power": 10,
    "osago_kbm": 15,
    "osago_age_exp": 100,
    "osago_drivers": 2,
    "osago_seasonal": 5,
    # Налоги
    "transport_tax_rates": 50,
    "luxury_cars": 100,
    # Амортизация
    "depreciation_rates": 50,
    "mileage_penalties": 3,
    # КАСКО
    "kasko_rates": 50,
    # ТО
    "service_operations": 10,
    "service_plan_ops": 100,
    "parts_costs": 50,
    "labor_rates": 100,
    # Топливо
    "fuel_prices": 40000,
    "fuel_price_forecast": 30 * 12,
    "cbr_rates": 10000,
    # ML
    "ml_models_registry": 33,
    "ml_strategies_registry": 1,
}


def run(engine: Engine | None = None) -> int:
    eng = engine or get_sync_engine()
    all_tables = sorted(Base.metadata.tables.keys())

    failures: list[str] = []
    counts: dict[str, int] = {}

    with eng.connect() as conn:
        for t in all_tables:
            row = conn.execute(text(f"SELECT COUNT(*) FROM {t}")).first()
            n = int(row[0]) if row else 0
            counts[t] = n
            expected = EXPECTED_MIN.get(t, 0)
            mark = "ok " if n >= expected else "BAD"
            logger.info("%s  %-26s  %8d  (>= %d)", mark, t, n, expected)
            if n < expected:
                failures.append(f"{t}: {n} < {expected}")

    logger.info(
        "verify: %d tables total, %d non-empty, %d failures",
        len(all_tables),
        sum(1 for v in counts.values() if v > 0),
        len(failures),
    )
    if failures:
        for f in failures:
            logger.error("FAIL  %s", f)
        return 1
    return 0


def main() -> int:
    return run()


if __name__ == "__main__":
    sys.exit(main())
