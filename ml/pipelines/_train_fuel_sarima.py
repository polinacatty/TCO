"""S4.1: train SARIMA models for fuel price forecasting.

Trains a family of SARIMA(p, 1, q)(P, 1, Q, 12) models for each
(region_id × fuel_type) pair, using a narrow manual grid-search over
p, q in {0, 1, 2} and P, Q in {0, 1} (36 combinations per series),
selecting the best by AIC.

Train/test split: 132/12 months (or 96/12 in --smoke mode).

For each successful fit, persists:
    ml/models/fuel_sarima/{region_id}_{fuel_type}.pkl
And appends a row to:
    ml/data/seed/ml_models_registry.csv

Usage:
    python -m ml.pipelines._train_fuel_sarima --smoke
    python ml/pipelines/_train_fuel_sarima.py --smoke
    python ml/pipelines/_train_fuel_sarima.py
    python ml/pipelines/_train_fuel_sarima.py --regions 1,19,2 --fuels ai92,ai95
"""

import argparse
import sys
import warnings
from datetime import datetime, timezone
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sarima_io import save_compact  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

# Suppress noisy warnings from statsmodels grid-search
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning)

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
SEED = ROOT / "data" / "seed"
MODELS = ROOT / "models" / "fuel_sarima"

DEFAULT_REGIONS = [1, 19, 2, 33, 60, 48, 45, 63, 56, 36]
DEFAULT_FUELS = ["ai92", "ai95", "diesel"]
SMOKE_REGIONS = [1, 19, 2]
SMOKE_FUELS = ["ai92", "ai95", "diesel"]

P_GRID = [0, 1, 2]
Q_GRID = [0, 1, 2]
SP_GRID = [0, 1]
SQ_GRID = [0, 1]
SEASONAL_PERIOD = 12

TEST_HORIZON_MONTHS = 12
DEFAULT_TARGET_MAPE_PCT = 5.0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Train SARIMA fuel-price models.")
    p.add_argument("--regions", type=str, default="", help="comma-separated region_ids; default = top-10")
    p.add_argument("--fuels", type=str, default="", help="comma-separated fuel_types; default = ai92,ai95,diesel")
    p.add_argument("--smoke", action="store_true", help="quick run on 9 series (top-3 regions x 3 fuels)")
    p.add_argument(
        "--ru-avg",
        action="store_true",
        help="train 3 RU_AVG fallback models on cross-region median (region_id=0)",
    )
    p.add_argument("--max-test-mape", type=float, default=DEFAULT_TARGET_MAPE_PCT, help="warn threshold for MAPE %%")
    p.add_argument("--registry-path", type=str, default=str(SEED / "ml_models_registry.csv"))
    p.add_argument("--output-dir", type=str, default=str(MODELS))
    p.add_argument("--no-write", action="store_true", help="dry-run (do not save .pkl or registry)")
    return p.parse_args()


RU_AVG_REGION_ID = 0
RU_AVG_REGION_NAME = "RU_AVG"


def load_series(fp: pd.DataFrame, region_id: int, fuel_type: str) -> pd.Series:
    if region_id == RU_AVG_REGION_ID:
        # cross-region median for each (price_month, fuel_type)
        sub = (
            fp[fp["fuel_type"] == fuel_type]
            .groupby("price_month")["price_rub_per_l"]
            .median()
            .reset_index()
            .sort_values("price_month")
        )
    else:
        sub = (
            fp[(fp["region_id"] == region_id) & (fp["fuel_type"] == fuel_type)]
            .sort_values("price_month")
            [["price_month", "price_rub_per_l"]]
        )
    if len(sub) == 0:
        raise ValueError(f"empty series for region={region_id}, fuel={fuel_type}")
    s = pd.Series(
        sub["price_rub_per_l"].values,
        index=pd.DatetimeIndex(sub["price_month"], freq="MS"),
        name=f"r{region_id}_{fuel_type}",
    )
    return s.astype(float)


def grid_search_sarima(train: pd.Series) -> dict:
    """Brute-force AIC over 36 (p,q,P,Q) combinations; return best fit summary."""
    from statsmodels.tsa.statespace.sarimax import SARIMAX

    best = {"aic": float("inf"), "bic": None, "order": None, "sorder": None, "fit": None}

    for p, q in product(P_GRID, Q_GRID):
        for P, Q in product(SP_GRID, SQ_GRID):
            if p + q + P + Q == 0:
                continue
            try:
                model = SARIMAX(
                    train,
                    order=(p, 1, q),
                    seasonal_order=(P, 1, Q, SEASONAL_PERIOD),
                    trend="c",
                    enforce_stationarity=False,
                    enforce_invertibility=False,
                )
                res = model.fit(disp=False, maxiter=200, method="lbfgs")
                if not np.isfinite(res.aic):
                    continue
                if res.aic < best["aic"]:
                    best.update({
                        "aic": float(res.aic),
                        "bic": float(res.bic),
                        "order": (p, 1, q),
                        "sorder": (P, 1, Q, SEASONAL_PERIOD),
                        "fit": res,
                    })
            except Exception:  # noqa: BLE001 — grid-search expects many failures
                continue

    if best["fit"] is None:
        # Fallback: try the canonical SARIMA(0,1,1)(0,1,1,12)
        try:
            model = SARIMAX(
                train,
                order=(0, 1, 1),
                seasonal_order=(0, 1, 1, SEASONAL_PERIOD),
                trend="c",
                enforce_stationarity=False,
                enforce_invertibility=False,
            )
            res = model.fit(disp=False, maxiter=200)
            best.update({
                "aic": float(res.aic),
                "bic": float(res.bic),
                "order": (0, 1, 1),
                "sorder": (0, 1, 1, SEASONAL_PERIOD),
                "fit": res,
                "fallback": True,
            })
        except Exception:
            return best

    return best


def evaluate(fit, test: pd.Series, train_last_value: float) -> dict:
    forecast = fit.get_forecast(steps=len(test))
    yhat = forecast.predicted_mean.values
    ci = forecast.conf_int(alpha=0.05).values  # shape (h, 2)

    y = test.values
    err = y - yhat
    mae = float(np.mean(np.abs(err)))
    rmse = float(np.sqrt(np.mean(err ** 2)))
    mape = float(np.mean(np.abs(err) / np.abs(y)) * 100)
    coverage_95 = float(np.mean((y >= ci[:, 0]) & (y <= ci[:, 1])) * 100)
    last_to_first_pred_ratio = float(yhat[-1] / yhat[0])

    return {
        "mape": mape,
        "rmse": rmse,
        "mae": mae,
        "coverage_95": coverage_95,
        "yhat_first": float(yhat[0]),
        "yhat_last": float(yhat[-1]),
        "yhat_growth_ratio": last_to_first_pred_ratio,
        "ci_lo": ci[:, 0].tolist(),
        "ci_hi": ci[:, 1].tolist(),
        "yhat": yhat.tolist(),
        "y_true": y.tolist(),
    }


def train_one(
    fp: pd.DataFrame,
    region_id: int,
    fuel_type: str,
    region_name: str,
    smoke: bool = False,
    test_h: int = TEST_HORIZON_MONTHS,
) -> dict | None:
    series = load_series(fp, region_id, fuel_type)

    if smoke:
        train = series[-96 - test_h : -test_h]
    else:
        train = series[:-test_h]
    test = series[-test_h:]

    if len(train) < 60:
        print(f"  SKIP region={region_id}, fuel={fuel_type}: train too short ({len(train)} months)")
        return None

    t0 = datetime.now()
    best = grid_search_sarima(train)
    t1 = datetime.now()

    if best["fit"] is None:
        print(f"  FAIL region={region_id}, fuel={fuel_type}: no model converged")
        return None

    metrics = evaluate(best["fit"], test, float(train.iloc[-1]))

    elapsed = (t1 - t0).total_seconds()

    out = {
        "region_id": region_id,
        "region_name": region_name,
        "fuel_type": fuel_type,
        "order": best["order"],
        "seasonal_order": best["sorder"],
        "aic": best["aic"],
        "bic": best["bic"],
        "fallback": best.get("fallback", False),
        "train_window": (str(train.index[0].date()), str(train.index[-1].date())),
        "test_window": (str(test.index[0].date()), str(test.index[-1].date())),
        "train_n": len(train),
        "test_n": len(test),
        "metrics": {k: v for k, v in metrics.items() if not isinstance(v, list)},
        "metrics_arrays": {k: v for k, v in metrics.items() if isinstance(v, list)},
        "fit_seconds": round(elapsed, 1),
        "fitted_at": datetime.now(timezone.utc).isoformat(),
    }

    flag = "OK " if metrics["mape"] <= DEFAULT_TARGET_MAPE_PCT else (
        "WARN" if metrics["mape"] <= 10 else "FAIL"
    )
    fb = " [FALLBACK SARIMA(0,1,1)(0,1,1,12)]" if out["fallback"] else ""
    print(
        f"  {flag} r={region_id:>2} f={fuel_type:6} "
        f"order={best['order']}{best['sorder']}  "
        f"MAPE={metrics['mape']:5.2f}%  "
        f"RMSE={metrics['rmse']:5.2f}  "
        f"cov95={metrics['coverage_95']:5.1f}%  "
        f"AIC={best['aic']:7.1f}  "
        f"({elapsed:4.1f}s){fb}"
    )

    return {"summary": out, "fit": best["fit"]}


def save_artifact(result: dict, output_dir: Path) -> Path:
    summary = result["summary"]
    fname = output_dir / f"{summary['region_id']}_{summary['fuel_type']}.pkl"
    save_compact(
        result["fit"],
        metrics=summary["metrics"],
        train_window=summary["train_window"],
        test_window=summary["test_window"],
        fitted_at=summary["fitted_at"],
        output_path=fname,
    )
    return fname


REGISTRY_COLUMNS = [
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


def to_registry_row(summary: dict, artifact_path: Path) -> dict:
    o, s = summary["order"], summary["seasonal_order"]
    m = summary["metrics"]
    return {
        "model_type": "fuel_sarima",
        "region_id": summary["region_id"],
        "region_name": summary["region_name"],
        "fuel_type": summary["fuel_type"],
        "version": "v1.0.0",
        "artifact_path": str(artifact_path).replace("\\", "/"),
        "train_mape_pct": round(m["mape"], 2),
        "train_rmse": round(m["rmse"], 2),
        "train_mae": round(m["mae"], 2),
        "train_coverage_95_pct": round(m["coverage_95"], 1),
        "train_window_start": summary["train_window"][0],
        "train_window_end": summary["train_window"][1],
        "test_window_start": summary["test_window"][0],
        "test_window_end": summary["test_window"][1],
        "order_p": o[0], "order_d": o[1], "order_q": o[2],
        "seasonal_p": s[0], "seasonal_d": s[1], "seasonal_q": s[2], "seasonal_period": s[3],
        "aic": round(summary["aic"], 1),
        "bic": round(summary["bic"], 1),
        "fallback": summary["fallback"],
        "fit_seconds": summary["fit_seconds"],
        "fitted_at": summary["fitted_at"],
        "status": "active",
    }


def main() -> int:
    args = parse_args()

    if args.ru_avg:
        regions = [RU_AVG_REGION_ID]
        fuels = [f.strip() for f in args.fuels.split(",") if f] or DEFAULT_FUELS
        mode = "RU_AVG"
    elif args.smoke:
        regions = [int(r) for r in args.regions.split(",") if r] or SMOKE_REGIONS
        fuels = [f.strip() for f in args.fuels.split(",") if f] or SMOKE_FUELS
        mode = "SMOKE"
    else:
        regions = [int(r) for r in args.regions.split(",") if r] or DEFAULT_REGIONS
        fuels = [f.strip() for f in args.fuels.split(",") if f] or DEFAULT_FUELS
        mode = "FULL"

    output_dir = Path(args.output_dir)
    registry_path = Path(args.registry_path)

    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print(f"_train_fuel_sarima — mode={mode}")
    print(f"  regions: {regions}")
    print(f"  fuels:   {fuels}")
    print(f"  output:  {output_dir}")
    print(f"  registry:{registry_path}")
    print("=" * 80)

    fp = pd.read_parquet(PROC / "fuel_prices.parquet")
    regions_df = pd.read_csv(SEED / "regions.csv").set_index("id")
    print(f"  loaded fuel_prices: {len(fp):,} rows; {fp['region_id'].nunique()} regions")
    if mode == "RU_AVG":
        print(f"  RU_AVG: cross-region median over {fp['region_id'].nunique()} regions")
    print()

    summaries = []
    fits = []
    n_total = len(regions) * len(fuels)
    n_done = 0

    t_start = datetime.now()
    for r in regions:
        if r == RU_AVG_REGION_ID:
            rname = RU_AVG_REGION_NAME
        else:
            rname = regions_df.loc[r, "name"] if r in regions_df.index else f"region_{r}"
        for f in fuels:
            n_done += 1
            print(f"[{n_done}/{n_total}]", end="")
            res = train_one(fp, r, f, rname, smoke=args.smoke)
            if res is None:
                continue
            summaries.append(res["summary"])
            fits.append((res["summary"], res["fit"]))
    t_end = datetime.now()
    elapsed_total = (t_end - t_start).total_seconds()

    if not summaries:
        print()
        print("NO MODELS TRAINED")
        return 1

    df = pd.DataFrame([s["metrics"] for s in summaries])
    df["region_id"] = [s["region_id"] for s in summaries]
    df["fuel_type"] = [s["fuel_type"] for s in summaries]
    df["fallback"] = [s["fallback"] for s in summaries]

    print()
    print("=" * 80)
    print(f"SUMMARY ({mode}) — {len(summaries)}/{n_total} models trained, {elapsed_total:.1f}s elapsed")
    print("=" * 80)
    print(f"  MAPE  median={df['mape'].median():.2f}%  mean={df['mape'].mean():.2f}%  max={df['mape'].max():.2f}%")
    print(f"  RMSE  median={df['rmse'].median():.2f}   mean={df['rmse'].mean():.2f}    max={df['rmse'].max():.2f}")
    print(f"  cov95 median={df['coverage_95'].median():.1f}%  mean={df['coverage_95'].mean():.1f}%  min={df['coverage_95'].min():.1f}%")
    print(f"  fallbacks: {df['fallback'].sum()}/{len(df)}")

    n_green = (df["mape"] <= args.max_test_mape).sum()
    n_yellow = ((df["mape"] > args.max_test_mape) & (df["mape"] <= 10)).sum()
    n_red = (df["mape"] > 10).sum()
    pct_green = n_green / len(df) * 100
    print(f"  GREEN (MAPE <= {args.max_test_mape}%): {n_green}/{len(df)} ({pct_green:.1f}%)")
    print(f"  YELLOW (MAPE 5-10%):                  {n_yellow}/{len(df)}")
    print(f"  RED (MAPE > 10%):                     {n_red}/{len(df)}")

    print()
    print("  By fuel_type:")
    for ft, grp in df.groupby("fuel_type"):
        print(f"    {ft:>8}: n={len(grp):>2}  MAPE median={grp['mape'].median():5.2f}%  cov95 median={grp['coverage_95'].median():5.1f}%")

    if args.no_write:
        print()
        print("DRY-RUN: --no-write set, skipping artifact persistence")
        return 0

    rows = []
    for s, fit in fits:
        path = save_artifact({"summary": s, "fit": fit}, output_dir)
        rows.append(to_registry_row(s, path))

    new_reg = pd.DataFrame(rows, columns=REGISTRY_COLUMNS)

    if registry_path.exists() and not args.smoke:
        existing = pd.read_csv(registry_path)
        keep = ~existing.set_index(["region_id", "fuel_type"]).index.isin(
            new_reg.set_index(["region_id", "fuel_type"]).index
        )
        merged = pd.concat([existing[keep], new_reg], ignore_index=True)
    else:
        merged = new_reg

    merged.to_csv(registry_path, index=False)

    print()
    print("=" * 80)
    print(f"WROTE {len(new_reg)} models to {output_dir}/")
    print(f"WROTE registry: {registry_path} ({len(merged)} total rows)")
    print("=" * 80)

    target_share_green = 0.80
    if mode == "FULL":
        if pct_green / 100 >= target_share_green:
            print(f"GREEN: {pct_green:.1f}% models with MAPE <= {args.max_test_mape}% (>= 80% target). S4.1 PASSED.")
            return 0
        else:
            print(f"WARN: only {pct_green:.1f}% models in green zone (target 80%).")
            return 0
    else:
        print(f"SMOKE done. Green share = {pct_green:.1f}% (informational; threshold checked in FULL mode).")
        return 0


if __name__ == "__main__":
    sys.exit(main())
