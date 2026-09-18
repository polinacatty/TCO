"""S4.1: validate ml_models_registry.csv against:
- schema columns
- value ranges (MAPE/cov95/AIC/orders)
- FK to regions.csv
- existence + loadability of every .pkl artifact
- target share in green zone (>= 80% with MAPE <= 5%)

Usage:
    python ml/pipelines/_ml_models_registry_validate.py
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sarima_io import load_compact  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "data" / "seed"
REGIONS_CSV = SEED / "regions.csv"
REGISTRY = SEED / "ml_models_registry.csv"

EXPECTED_COLUMNS = [
    "model_type", "region_id", "region_name", "fuel_type", "version",
    "artifact_path",
    "train_mape_pct", "train_rmse", "train_mae", "train_coverage_95_pct",
    "train_window_start", "train_window_end",
    "test_window_start", "test_window_end",
    "order_p", "order_d", "order_q",
    "seasonal_p", "seasonal_d", "seasonal_q", "seasonal_period",
    "aic", "bic",
    "fallback",
    "fit_seconds",
    "fitted_at",
    "status",
]

VALID_MODEL_TYPES = {"fuel_sarima"}
VALID_FUEL_TYPES = {"ai92", "ai95", "ai98", "diesel"}
VALID_STATUSES = {"active", "shadow", "deprecated"}

GREEN_MAPE = 5.0
YELLOW_MAPE = 10.0
TARGET_GREEN_SHARE = 0.80


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
    print("ml_models_registry.csv — VALIDATION")
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

    if not df["model_type"].isin(VALID_MODEL_TYPES).all():
        bad = df.loc[~df["model_type"].isin(VALID_MODEL_TYPES), "model_type"].unique().tolist()
        fail(f"invalid model_type values: {bad}")
    ok(f"model_type in {sorted(VALID_MODEL_TYPES)}")

    if not df["fuel_type"].isin(VALID_FUEL_TYPES).all():
        bad = df.loc[~df["fuel_type"].isin(VALID_FUEL_TYPES), "fuel_type"].unique().tolist()
        fail(f"invalid fuel_type values: {bad}")
    ok(f"fuel_type in {sorted(VALID_FUEL_TYPES)}")

    if not df["status"].isin(VALID_STATUSES).all():
        bad = df.loc[~df["status"].isin(VALID_STATUSES), "status"].unique().tolist()
        fail(f"invalid status values: {bad}")
    ok(f"status in {sorted(VALID_STATUSES)}")

    regions = pd.read_csv(REGIONS_CSV)
    valid_ids = set(regions["id"]) | {0}  # 0 is reserved sentinel for RU_AVG aggregate
    bad = df[~df["region_id"].isin(valid_ids)]
    if len(bad) > 0:
        fail(f"FK violation: {len(bad)} rows have region_id not in regions.csv (and not RU_AVG sentinel 0)")
    ok(f"FK to regions.id verified ({df['region_id'].nunique()} unique regions, RU_AVG sentinel 0 allowed)")

    ru_avg = df[df["region_id"] == 0]
    if len(ru_avg) > 0:
        if not (ru_avg["region_name"] == "RU_AVG").all():
            fail(f"region_id=0 must have region_name='RU_AVG'; found {ru_avg['region_name'].unique().tolist()}")
        ok(f"RU_AVG fallback rows ({len(ru_avg)}): region_name='RU_AVG'")

    if df.duplicated(["model_type", "region_id", "fuel_type"]).any():
        dup = df[df.duplicated(["model_type", "region_id", "fuel_type"], keep=False)]
        fail(f"duplicate (model_type, region_id, fuel_type): {len(dup)} rows")
    ok(f"uniqueness on (model_type, region_id, fuel_type) for all {len(df)} rows")

    range_checks = [
        ("train_mape_pct", 0, 100, "MAPE %"),
        ("train_rmse", 0, 50, "RMSE"),
        ("train_mae", 0, 50, "MAE"),
        ("train_coverage_95_pct", 0, 100, "coverage %"),
        ("order_p", 0, 5, "p"),
        ("order_d", 0, 2, "d"),
        ("order_q", 0, 5, "q"),
        ("seasonal_p", 0, 2, "P"),
        ("seasonal_d", 0, 2, "D"),
        ("seasonal_q", 0, 2, "Q"),
        ("seasonal_period", 1, 24, "s"),
        ("fit_seconds", 0, 600, "fit_seconds"),
    ]
    for col, lo, hi, label in range_checks:
        v = df[col]
        if (v < lo).any() or (v > hi).any():
            bad_idx = df.loc[(v < lo) | (v > hi)].index.tolist()[:5]
            fail(f"{col} out of [{lo}, {hi}] in rows {bad_idx} ({label})")
    ok("all numeric columns within plausible ranges")

    if not (df["seasonal_period"] == 12).all():
        fail(f"seasonal_period must be 12 for fuel_sarima; found {df['seasonal_period'].unique().tolist()}")
    ok("seasonal_period = 12 for all rows")

    if not (df["order_d"] == 1).all() or not (df["seasonal_d"] == 1).all():
        fail(f"d=D=1 expected for fuel_sarima; found d={df['order_d'].unique().tolist()}, D={df['seasonal_d'].unique().tolist()}")
    ok("differencing orders d=1, D=1 for all rows")

    df["train_window_start_dt"] = pd.to_datetime(df["train_window_start"])
    df["train_window_end_dt"] = pd.to_datetime(df["train_window_end"])
    df["test_window_start_dt"] = pd.to_datetime(df["test_window_start"])
    df["test_window_end_dt"] = pd.to_datetime(df["test_window_end"])
    if not (df["train_window_end_dt"] < df["test_window_start_dt"]).all():
        fail("train window must end before test window starts")
    ok("temporal split: train window precedes test window for all rows")

    missing_files = []
    bad_loads = []
    for _, row in df.iterrows():
        p = ROOT.parent / row["artifact_path"]
        if not p.exists():
            p_alt = ROOT / row["artifact_path"].replace("ml/", "", 1)
            if not p_alt.exists():
                missing_files.append(row["artifact_path"])
                continue
            p = p_alt
        try:
            obj = load_compact(p)
            if "model" not in obj or "metrics" not in obj:
                bad_loads.append(f"{row['artifact_path']}: missing 'model' or 'metrics' keys")
                continue
            metrics = obj["metrics"]
            for k in ("mape", "rmse", "mae", "coverage_95"):
                if k not in metrics:
                    bad_loads.append(f"{row['artifact_path']}: missing metrics.{k}")
                    break
            try:
                fc = obj["model"].get_forecast(steps=3)
                _ = fc.predicted_mean.values[:3]
            except Exception as e:  # noqa: BLE001
                bad_loads.append(f"{row['artifact_path']}: forecast failed — {type(e).__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            bad_loads.append(f"{row['artifact_path']}: {type(e).__name__}: {e}")

    if missing_files:
        fail(f"{len(missing_files)} artifact files not found: {missing_files[:3]}")
    ok(f"all {len(df)} .pkl artifacts exist on disk")

    if bad_loads:
        fail(f"{len(bad_loads)} artifacts failed to load: {bad_loads[:3]}")
    ok(f"all {len(df)} .pkl artifacts load and have valid structure")

    n_green = (df["train_mape_pct"] <= GREEN_MAPE).sum()
    n_yellow = ((df["train_mape_pct"] > GREEN_MAPE) & (df["train_mape_pct"] <= YELLOW_MAPE)).sum()
    n_red = (df["train_mape_pct"] > YELLOW_MAPE).sum()
    pct_green = n_green / len(df)

    if pct_green < TARGET_GREEN_SHARE:
        warn(f"only {pct_green*100:.1f}% models have MAPE <= {GREEN_MAPE}% (target {TARGET_GREEN_SHARE*100:.0f}%)")
    else:
        ok(f"{n_green}/{len(df)} ({pct_green*100:.1f}%) models in GREEN zone (MAPE <= {GREEN_MAPE}%)")

    if n_red > 0:
        fail(f"{n_red} models in RED zone (MAPE > {YELLOW_MAPE}%) — must be fixed")
    ok(f"no models in RED zone (MAPE > {YELLOW_MAPE}%)")

    low_cov = (df["train_coverage_95_pct"] < 80).sum()
    if low_cov > len(df) * 0.5:
        warn(f"{low_cov} models have coverage_95 < 80% (limited model uncertainty calibration)")
    else:
        ok(f"coverage_95 >= 80% for {len(df) - low_cov}/{len(df)} models")

    print()
    print("  Stats:")
    print(f"    rows:                      {len(df)}")
    print(f"    unique regions:            {df['region_id'].nunique()}")
    print(f"    unique fuel_types:         {df['fuel_type'].nunique()}")
    print(f"    MAPE median / max:         {df['train_mape_pct'].median():.2f}% / {df['train_mape_pct'].max():.2f}%")
    print(f"    RMSE median / max:         {df['train_rmse'].median():.2f} / {df['train_rmse'].max():.2f}")
    print(f"    coverage_95 median / min:  {df['train_coverage_95_pct'].median():.1f}% / {df['train_coverage_95_pct'].min():.1f}%")
    print(f"    AIC median / max:          {df['aic'].median():.1f} / {df['aic'].max():.1f}")
    print(f"    fallbacks:                 {df['fallback'].sum()}/{len(df)}")
    print(f"    by fuel_type:              {df['fuel_type'].value_counts().to_dict()}")
    print(f"    by status:                 {df['status'].value_counts().to_dict()}")

    print()
    print("=" * 70)
    print("OK  ml_models_registry.csv passed all checks")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except CheckFailed as e:
        print()
        print(f"FAILED: {e}")
        sys.exit(1)
