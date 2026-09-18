"""S4.3: validate ml_strategies_registry.csv.

Реестр **логических** ML-моделей (без обучаемых .pkl-файлов): TOPSIS, в будущем
LTR/Pareto-стратегии. Отделён от `ml_models_registry.csv` (time-series) потому,
что схема и набор валидируемых полей радикально различаются.

Проверки:
- schema columns;
- enum-валидация `model_type` и `status`;
- `target_*` <= наблюдаемая метрика (метрики прошли свои target);
- наличие методологии, валидатора и validation set на диске;
- если `has_artifact=True` — `artifact_path` существует.

Usage:
    python ml/pipelines/_ml_strategies_registry_validate.py
"""

import sys
from pathlib import Path

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "data" / "seed"
REGISTRY = SEED / "ml_strategies_registry.csv"
PROJECT_ROOT = ROOT.parent

EXPECTED_COLUMNS = [
    "model_type", "version", "algorithm", "description",
    "criteria_count", "has_artifact", "artifact_path",
    "ndcg_at_10_median", "diversity_at_10_median", "coverage_pct", "stability_median",
    "target_ndcg", "target_diversity", "target_coverage_pct", "target_stability",
    "validator_path", "methodology_doc", "validation_set_path",
    "last_validated_at", "status",
]

VALID_MODEL_TYPES = {"topsis_v1"}  # extend with ltr_v1, pareto_v1 etc.
VALID_STATUSES = {"active", "shadow", "deprecated"}


class CheckFailed(Exception):
    pass


def ok(msg: str) -> None:
    print(f"  OK    {msg}")


def warn(msg: str) -> None:
    print(f"  WARN  {msg}")


def fail(msg: str) -> None:
    print(f"  FAIL  {msg}")
    raise CheckFailed(msg)


def main() -> int:
    print("=" * 70)
    print("ml_strategies_registry.csv — VALIDATION")
    print("=" * 70)

    if not REGISTRY.exists():
        fail(f"registry file not found: {REGISTRY}")

    df = pd.read_csv(REGISTRY)
    print(f"  loaded: {len(df)} rows, {len(df.columns)} columns")

    if list(df.columns) != EXPECTED_COLUMNS:
        diff_extra = set(df.columns) - set(EXPECTED_COLUMNS)
        diff_missing = set(EXPECTED_COLUMNS) - set(df.columns)
        fail(f"schema mismatch: extra={diff_extra}, missing={diff_missing}")
    ok("schema columns match")

    bad_types = set(df["model_type"]) - VALID_MODEL_TYPES
    if bad_types:
        fail(f"invalid model_type values: {bad_types}")
    ok(f"model_type in {sorted(VALID_MODEL_TYPES)}")

    bad_st = set(df["status"]) - VALID_STATUSES
    if bad_st:
        fail(f"invalid status values: {bad_st}")
    ok(f"status in {sorted(VALID_STATUSES)}")

    if df.duplicated(["model_type", "version"]).any():
        fail("duplicate (model_type, version)")
    ok("uniqueness on (model_type, version)")

    metric_targets = [
        ("ndcg_at_10_median",   "target_ndcg",          ">="),
        ("diversity_at_10_median", "target_diversity",  ">="),
        ("coverage_pct",        "target_coverage_pct",  ">="),
        ("stability_median",    "target_stability",     ">="),
    ]
    for col, target_col, op in metric_targets:
        v = df[col].astype(float)
        t = df[target_col].astype(float)
        if op == ">=":
            bad = df[v < t]
            if len(bad) > 0:
                fail(f"{col} < {target_col} for {len(bad)} rows: {bad[['model_type', col, target_col]].to_dict('records')}")
        ok(f"{col:24s} >= {target_col} for all rows")

    for col in ("validator_path", "methodology_doc", "validation_set_path"):
        for _, row in df.iterrows():
            p = PROJECT_ROOT / row[col]
            if not p.exists():
                fail(f"{col} for {row['model_type']} not found on disk: {row[col]}")
        ok(f"{col} exists on disk for all {len(df)} rows")

    has_art = df[df["has_artifact"] == True]  # noqa: E712
    for _, row in has_art.iterrows():
        if pd.isna(row["artifact_path"]) or not (PROJECT_ROOT / row["artifact_path"]).exists():
            fail(f"has_artifact=True but artifact missing: {row['model_type']}")
    ok(f"artifact files verified ({len(has_art)} rows with has_artifact=True)")

    print()
    print("  Summary:")
    for _, row in df.iterrows():
        print(f"    {row['model_type']:12s} v{row['version']}: "
              f"NDCG={row['ndcg_at_10_median']:.3f}  "
              f"Div={int(row['diversity_at_10_median'])}  "
              f"Cov={row['coverage_pct']:.1f}%  "
              f"Stab={row['stability_median']:.3f}  "
              f"[{row['status']}]")

    print()
    print("=" * 70)
    print("OK  ml_strategies_registry.csv passed all checks")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except CheckFailed as e:
        print()
        print(f"FAILED: {e}")
        sys.exit(1)
