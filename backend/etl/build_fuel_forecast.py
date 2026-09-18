from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import Engine

from etl._common import (
    get_sync_engine,
    insert_rows,
    logger,
    sarima_dir,
    truncate,
)
from etl._sarima_loader import load_compact

MODEL_VERSION = "v1.0.0"
DEFAULT_HORIZON_MONTHS = 72  # 6 лет — с запасом под горизонт владения

# имя файла: '{region_id}_{fuel_type}.pkl' — например '1_ai92.pkl'
_FNAME_RE = re.compile(r"^(?P<region_id>\d+)_(?P<fuel>[a-z0-9]+)\.pkl$")


def _iter_artifacts() -> list[tuple[int, str, Path]]:
    """Найти все pkl и распарсить (region_id, fuel_type)."""

    out: list[tuple[int, str, Path]] = []
    for p in sorted(sarima_dir().glob("*.pkl")):
        m = _FNAME_RE.match(p.name)
        if not m:
            logger.warning("skip artifact with unexpected name: %s", p.name)
            continue
        out.append((int(m["region_id"]), m["fuel"], p))
    return out


def _forecast_one(
    path: Path, *, horizon_months: int
) -> tuple[list[float], pd.Timestamp]:

    sarima = load_compact(path)
    fit = sarima.model
    fc = fit.get_forecast(steps=horizon_months)
    mean = fc.predicted_mean
    if not isinstance(mean, pd.Series):  # paranoia
        raise TypeError(f"forecast returned {type(mean).__name__}, expected Series")
    train_end = pd.Timestamp(sarima.train_window[1])
    return [float(v) for v in mean.tolist()], train_end


def _rows_for_artifact(
    region_id: int, fuel: str, values: list[float], train_end: pd.Timestamp,
    horizon_months: int,
) -> list[dict[str, object]]:

    fallback = region_id == 0  # RU_AVG = fallback "по умолчанию"

    rows: list[dict[str, object]] = []
    for step in range(1, horizon_months + 1):
        forecast_month = (train_end + pd.DateOffset(months=step)).normalize()
        rows.append(
            {
                "region_id": region_id,
                "fuel_type": fuel,
                "price_month": forecast_month.date(),
                "price_rub_per_l": round(values[step - 1], 2),
                "forecast_origin_month": train_end.date(),
                "horizon_step": step,
                "model_version": MODEL_VERSION,
                "fallback": fallback,
            }
        )
    return rows


_COLS = (
    "region_id", "fuel_type", "price_month", "price_rub_per_l",
    "forecast_origin_month", "horizon_step", "model_version", "fallback",
)


def run(*, horizon_months: int = DEFAULT_HORIZON_MONTHS,
        engine: Engine | None = None) -> int:
    eng = engine or get_sync_engine()
    artifacts = _iter_artifacts()
    if not artifacts:
        raise FileNotFoundError(f"no SARIMA artifacts in {sarima_dir()}")
    logger.info("forecast: %d artifacts found, horizon=%d months",
                len(artifacts), horizon_months)

    all_rows: list[dict[str, object]] = []
    for region_id, fuel, path in artifacts:
        values, train_end = _forecast_one(path, horizon_months=horizon_months)
        all_rows.extend(_rows_for_artifact(region_id, fuel, values, train_end,
                                           horizon_months))
        logger.info(
            "forecast: %d_%s  train_end=%s  ->  %d rows (last=%.2f ₽/л)",
            region_id, fuel, train_end.date(), horizon_months, values[-1],
        )

    with eng.begin() as conn:
        truncate(conn, "fuel_price_forecast")
        n = insert_rows(conn, "fuel_price_forecast", _COLS, all_rows)

    logger.info("forecast: done, %d rows inserted", n)
    return n


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--horizon-months", type=int, default=DEFAULT_HORIZON_MONTHS,
        help=f"months to forecast (default {DEFAULT_HORIZON_MONTHS})",
    )
    args = parser.parse_args(argv)

    try:
        run(horizon_months=args.horizon_months)
    except Exception:
        logger.exception("fuel forecast build failed")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
