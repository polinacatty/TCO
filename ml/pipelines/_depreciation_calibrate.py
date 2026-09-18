"""Calibrate parametric depreciation against observed market prices.

Implements ADR-0001 §«Параметры таблицы»:

    P(t) = MSRP * ∏_{i=1..t} (1 - r_i / 100)

where r_i is taken from ``depreciation_rates.csv`` keyed by
(segment, brand_tier, age_year_bucket = clamp(i, 1, 5)).

Then a multiplicative mileage penalty from ``mileage_penalties.csv`` is
applied for each crossed threshold (100k / 150k / 200k km):

    P_with_mileage(t) = P(t) * ∏_{k: mileage >= threshold_k} (1 - extra_pct_k / 100)

Computes per-case absolute percentage error (APE) and aggregate MAPE
overall, by ``segment``, by ``brand_tier``. Целевая метрика ADR-0001:
**MAPE ≤ 20 %**.

Exit codes
----------
0  MAPE <= 20 %    (зелёный, цель ADR-0001 достигнута)
1  20 % < MAPE <= 25 %   (жёлтый: план Б §S2.9 — один проход корректировки)
2  MAPE > 25 %     (красный: эскалация, риск-finding в защите)

Idempotent. Read-only — никаких side-effects.
"""

from __future__ import annotations

import csv
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CALIBRATION_PATH = REPO / "ml" / "data" / "seed" / "depreciation_calibration.csv"
RATES_PATH = REPO / "ml" / "data" / "seed" / "depreciation_rates.csv"
PENALTIES_PATH = REPO / "ml" / "data" / "seed" / "mileage_penalties.csv"


def load_rates() -> dict[tuple[str, str], list[float]]:
    """Return {(segment, brand_tier): [r_1, r_2, r_3, r_4, r_5plus] in %}."""
    table: dict[tuple[str, str], dict[int, float]] = {}
    with RATES_PATH.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            key = (row["segment"], row["brand_tier"])
            bucket = int(row["age_year_bucket"])
            pct = float(row["annual_depreciation_pct"])
            table.setdefault(key, {})[bucket] = pct

    out: dict[tuple[str, str], list[float]] = {}
    for key, by_bucket in table.items():
        if set(by_bucket) != {1, 2, 3, 4, 5}:
            raise RuntimeError(f"depreciation_rates: incomplete buckets for {key}: {sorted(by_bucket)}")
        out[key] = [by_bucket[1], by_bucket[2], by_bucket[3], by_bucket[4], by_bucket[5]]
    return out


def load_penalties() -> list[tuple[int, float]]:
    out: list[tuple[int, float]] = []
    with PENALTIES_PATH.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            out.append((int(row["mileage_threshold_km"]), float(row["extra_depreciation_pct"])))
    return sorted(out)


def predict(msrp: float, segment: str, tier: str, age: int, mileage_km: int,
            rates: dict[tuple[str, str], list[float]],
            penalties: list[tuple[int, float]]) -> float:
    """Return predicted residual price using parametric model."""
    r = rates[(segment, tier)]
    factor = 1.0
    for i in range(1, age + 1):
        bucket_idx = min(i, 5) - 1
        factor *= (1.0 - r[bucket_idx] / 100.0)
    price = msrp * factor

    for threshold_km, extra_pct in penalties:
        if mileage_km >= threshold_km:
            price *= (1.0 - extra_pct / 100.0)
    return price


def main() -> int:
    rates = load_rates()
    penalties = load_penalties()

    with CALIBRATION_PATH.open(encoding="utf-8", newline="") as f:
        cases = list(csv.DictReader(f))

    if not cases:
        print("FAIL: no calibration cases")
        return 2

    apes: list[float] = []
    by_segment: dict[str, list[float]] = {}
    by_tier: dict[str, list[float]] = {}
    by_age: dict[int, list[float]] = {}

    print(f"{'#':>3}  {'make':<14} {'model':<18} {'seg':<8} {'tier':<22} "
          f"{'age':>3} {'mile_km':>8} {'msrp':>10} {'predicted':>10} {'observed':>10} {'APE%':>6}")
    print("-" * 130)

    for c in cases:
        cid = int(c["case_id"])
        make = c["make"]
        model = c["model"]
        segment = c["segment"]
        tier = c["brand_tier"]
        age = int(c["age_years_at_observation"])
        mileage = int(c["mileage_km"])
        msrp = float(c["msrp_new_rub"])
        observed = float(c["observed_market_price_rub"])

        pred = predict(msrp, segment, tier, age, mileage, rates, penalties)
        ape = abs(observed - pred) / observed * 100.0
        apes.append(ape)
        by_segment.setdefault(segment, []).append(ape)
        by_tier.setdefault(tier, []).append(ape)
        by_age.setdefault(age, []).append(ape)

        print(f"{cid:>3}  {make:<14} {model:<18} {segment:<8} {tier:<22} "
              f"{age:>3} {mileage:>8,} {msrp:>10,.0f} {pred:>10,.0f} {observed:>10,.0f} {ape:>6.1f}")

    print("-" * 130)
    mape = statistics.fmean(apes)
    median_ape = statistics.median(apes)
    max_ape = max(apes)
    n_under_20 = sum(1 for a in apes if a <= 20.0)
    n_under_25 = sum(1 for a in apes if a <= 25.0)

    print()
    print(f"OVERALL MAPE        : {mape:.2f} %   (target <= 20 %)")
    print(f"  median APE        : {median_ape:.2f} %")
    print(f"  max APE           : {max_ape:.2f} %")
    print(f"  cases with APE<=20: {n_under_20}/{len(apes)}")
    print(f"  cases with APE<=25: {n_under_25}/{len(apes)}")

    print()
    print("MAPE by segment:")
    for seg in sorted(by_segment):
        seg_apes = by_segment[seg]
        print(f"  {seg:<10} n={len(seg_apes):>2} MAPE={statistics.fmean(seg_apes):>6.2f}%  max={max(seg_apes):>5.1f}%")

    print()
    print("MAPE by brand_tier:")
    for tier in sorted(by_tier):
        tier_apes = by_tier[tier]
        print(f"  {tier:<22} n={len(tier_apes):>2} MAPE={statistics.fmean(tier_apes):>6.2f}%  max={max(tier_apes):>5.1f}%")

    print()
    print("MAPE by age (years):")
    for age in sorted(by_age):
        age_apes = by_age[age]
        print(f"  age={age}  n={len(age_apes):>2} MAPE={statistics.fmean(age_apes):>6.2f}%  max={max(age_apes):>5.1f}%")

    print()
    if mape <= 20.0:
        print(f"GREEN: MAPE {mape:.2f}% <= 20% (ADR-0001 target met)")
        return 0
    elif mape <= 25.0:
        print(f"YELLOW: MAPE {mape:.2f}% in (20, 25]% — план Б §S2.9: single corrective pass on depreciation_rates.csv")
        return 1
    else:
        print(f"RED: MAPE {mape:.2f}% > 25% — эскалация (risk-finding в защите, ML-надстройка в backlog)")
        return 2


if __name__ == "__main__":
    sys.exit(main())
