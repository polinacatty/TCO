from __future__ import annotations

import shutil
import sys
from pathlib import Path

from sqlalchemy import Engine
from sqlalchemy.engine import Connection

from app.config import BACKEND_ROOT
from etl._common import (
    coerce,
    get_sync_engine,
    insert_rows,
    logger,
    read_csv_rows,
    sarima_dir,
    seed_dir,
    truncate,
)

ARTIFACTS_FUEL_SARIMA = BACKEND_ROOT / "artifacts" / "fuel_sarima"


# --------------------------------------------------------------------------- #
# Копирование артефактов                                                      #
# --------------------------------------------------------------------------- #


def _copy_sarima_artifacts() -> int:
    src = sarima_dir()
    if not src.exists():
        raise FileNotFoundError(f"SARIMA dir not found: {src}")

    ARTIFACTS_FUEL_SARIMA.mkdir(parents=True, exist_ok=True)

    n = 0
    for pkl in src.glob("*.pkl"):
        dst = ARTIFACTS_FUEL_SARIMA / pkl.name
        shutil.copy2(pkl, dst)
        n += 1
    logger.info("artifacts: copied %d SARIMA pkl -> %s", n, ARTIFACTS_FUEL_SARIMA)
    return n


def _rewrite_artifact_path(raw: str) -> str:

    name = Path(raw).name  # '1_ai92.pkl'
    return f"artifacts/fuel_sarima/{name}"


# --------------------------------------------------------------------------- #
# ml_models_registry                                                          #
# --------------------------------------------------------------------------- #


_MODELS_COLS = (
    "model_type", "region_id", "region_name", "fuel_type", "version",
    "artifact_path",
    "train_mape_pct", "train_rmse", "train_mae", "train_coverage_95_pct",
    "train_window_start", "train_window_end",
    "test_window_start", "test_window_end",
    "order_p", "order_d", "order_q",
    "seasonal_p", "seasonal_d", "seasonal_q", "seasonal_period",
    "aic", "bic", "fallback", "fit_seconds", "fitted_at", "status",
)


def _ingest_models_registry(conn: Connection) -> int:
    path = seed_dir() / "ml_models_registry.csv"
    raw = read_csv_rows(path)
    rows = coerce(
        raw,
        int_cols=(
            "region_id",
            "order_p", "order_d", "order_q",
            "seasonal_p", "seasonal_d", "seasonal_q", "seasonal_period",
        ),
        float_cols=(
            "train_mape_pct", "train_rmse", "train_mae", "train_coverage_95_pct",
            "aic", "bic", "fit_seconds",
        ),
        bool_cols=("fallback",),
        nullable=(
            "train_mape_pct", "train_rmse", "train_mae", "train_coverage_95_pct",
            "train_window_start", "train_window_end",
            "test_window_start", "test_window_end",
            "order_p", "order_d", "order_q",
            "seasonal_p", "seasonal_d", "seasonal_q", "seasonal_period",
            "aic", "bic", "fit_seconds", "fitted_at",
        ),
    )

    for r in rows:
        r["artifact_path"] = _rewrite_artifact_path(str(r["artifact_path"]))

    trimmed = [{k: r.get(k) for k in _MODELS_COLS} for r in rows]

    truncate(conn, "ml_models_registry")
    n = insert_rows(conn, "ml_models_registry", _MODELS_COLS, trimmed)
    logger.info("registry: ml_models_registry -> %d rows", n)
    return n


# --------------------------------------------------------------------------- #
# ml_strategies_registry                                                      #
# --------------------------------------------------------------------------- #


_STRATEGIES_COLS = (
    "model_type", "version", "algorithm", "description",
    "criteria_count", "has_artifact", "artifact_path",
    "ndcg_at_10_median", "diversity_at_10_median",
    "coverage_pct", "stability_median",
    "target_ndcg", "target_diversity",
    "target_coverage_pct", "target_stability",
    "validator_path", "methodology_doc", "validation_set_path",
    "last_validated_at", "status",
)


def _ingest_strategies_registry(conn: Connection) -> int:
    path = seed_dir() / "ml_strategies_registry.csv"
    raw = read_csv_rows(path)
    rows = coerce(
        raw,
        int_cols=("criteria_count",),
        float_cols=(
            "ndcg_at_10_median", "diversity_at_10_median",
            "coverage_pct", "stability_median",
            "target_ndcg", "target_diversity",
            "target_coverage_pct", "target_stability",
        ),
        bool_cols=("has_artifact",),
        nullable=(
            "description", "artifact_path",
            "ndcg_at_10_median", "diversity_at_10_median",
            "coverage_pct", "stability_median",
            "target_ndcg", "target_diversity",
            "target_coverage_pct", "target_stability",
            "validator_path", "methodology_doc", "validation_set_path",
            "last_validated_at", "criteria_count",
        ),
    )
    trimmed = [{k: r.get(k) for k in _STRATEGIES_COLS} for r in rows]
    truncate(conn, "ml_strategies_registry")
    n = insert_rows(conn, "ml_strategies_registry", _STRATEGIES_COLS, trimmed)
    logger.info("registry: ml_strategies_registry -> %d rows", n)
    return n


# --------------------------------------------------------------------------- #
# Orchestrator                                                                #
# --------------------------------------------------------------------------- #


def run(engine: Engine | None = None) -> int:
    eng = engine or get_sync_engine()
    n_files = _copy_sarima_artifacts()
    with eng.begin() as conn:
        n_models = _ingest_models_registry(conn)
        n_strats = _ingest_strategies_registry(conn)
    logger.info(
        "registry: done, models=%d, strategies=%d, artifacts=%d",
        n_models, n_strats, n_files,
    )
    return n_models + n_strats


def main() -> int:
    try:
        run()
    except Exception:
        logger.exception("ml registry ingest failed")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
