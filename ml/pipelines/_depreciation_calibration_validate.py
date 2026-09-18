"""Checks for ``depreciation_calibration.csv`` (шаг 2.9).

Per план спринта 2 §S2.9: ≥ 30 строк; покрытие всех ``brand_tier``;
наблюдения не старше 12 месяцев. Дополнительно валидируем ссылочную
целостность с ``depreciation_rates.csv`` и реалистичность диапазонов.

Validates:
1. Schema (column names match exactly).
2. Row count >= 30.
3. Unique ``case_id``, monotonically increasing from 1.
4. ``segment`` ∈ {A_B, C_D, E_F, J_SUV, J_CROSS, LCV} — синхронно с depreciation_rates.csv.
5. ``brand_tier`` ∈ {russian, mass, japanese_korean_mass, chinese, premium}.
6. Coverage: все 5 brand_tier представлены.
7. Coverage: все 6 segment представлены.
8. ``year_of_purchase`` in [1990, current_year].
9. ``age_years_at_observation`` in [1, 20] и согласован с ``observation_date - year_of_purchase``.
10. ``mileage_km`` in [1000, 500000].
11. ``msrp_new_rub`` and ``observed_market_price_rub`` in (0, 50_000_000].
12. ``observed`` < ``msrp`` (амортизация — потеря, не рост).
13. ``observation_date`` ISO-8601, не старше 12 месяцев от current_date.
14. ``source_url`` is HTTP(S) URL.
15. Non-empty ``source_note``.
16. Cross-check: каждая (segment, brand_tier) пара существует в ``depreciation_rates.csv``.
"""

from __future__ import annotations

import csv
import re
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CALIBRATION_PATH = REPO / "ml" / "data" / "seed" / "depreciation_calibration.csv"
RATES_PATH = REPO / "ml" / "data" / "seed" / "depreciation_rates.csv"

REQUIRED_COLS = [
    "case_id", "make", "model", "segment", "brand_tier",
    "year_of_purchase", "age_years_at_observation", "mileage_km",
    "msrp_new_rub", "observed_market_price_rub",
    "observation_date", "source_url", "source_note",
]
SEGMENTS = {"A_B", "C_D", "E_F", "J_SUV", "J_CROSS", "LCV"}
TIERS = {"russian", "mass", "japanese_korean_mass", "chinese", "premium"}
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
URL_RE = re.compile(r"^https?://[^\s]+$")
TODAY = date.today()


def load_rates_pairs() -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    with RATES_PATH.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            pairs.add((row["segment"], row["brand_tier"]))
    return pairs


def main() -> int:
    errs: list[str] = []

    if not CALIBRATION_PATH.is_file():
        print("FAIL: missing", CALIBRATION_PATH)
        return 1
    if not RATES_PATH.is_file():
        print("FAIL: missing", RATES_PATH)
        return 1

    rates_pairs = load_rates_pairs()

    with CALIBRATION_PATH.open(encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        if r.fieldnames != REQUIRED_COLS:
            errs.append(f"columns: got {r.fieldnames}")
        rows = list(r)

    if len(rows) < 30:
        errs.append(f"expected >= 30 rows (план §S2.9), got {len(rows)}")

    case_ids: list[int] = []
    seen_tiers: set[str] = set()
    seen_segments: set[str] = set()
    tier_counts: dict[str, int] = {}
    segment_counts: dict[str, int] = {}

    for i, row in enumerate(rows, start=2):
        try:
            cid = int(row["case_id"])
        except ValueError:
            errs.append(f"line {i}: case_id must be int, got {row['case_id']!r}")
            continue
        case_ids.append(cid)

        if row["segment"] not in SEGMENTS:
            errs.append(f"line {i}: segment {row['segment']!r} not in {sorted(SEGMENTS)}")
        else:
            seen_segments.add(row["segment"])
            segment_counts[row["segment"]] = segment_counts.get(row["segment"], 0) + 1

        if row["brand_tier"] not in TIERS:
            errs.append(f"line {i}: brand_tier {row['brand_tier']!r} not in {sorted(TIERS)}")
        else:
            seen_tiers.add(row["brand_tier"])
            tier_counts[row["brand_tier"]] = tier_counts.get(row["brand_tier"], 0) + 1

        pair = (row["segment"], row["brand_tier"])
        if pair not in rates_pairs:
            errs.append(f"line {i}: pair {pair} not present in depreciation_rates.csv (FK violation)")

        try:
            year_p = int(row["year_of_purchase"])
        except ValueError:
            errs.append(f"line {i}: year_of_purchase invalid: {row['year_of_purchase']!r}")
            continue
        if not (1990 <= year_p <= TODAY.year):
            errs.append(f"line {i}: year_of_purchase {year_p} out of [1990, {TODAY.year}]")

        try:
            age = int(row["age_years_at_observation"])
        except ValueError:
            errs.append(f"line {i}: age invalid: {row['age_years_at_observation']!r}")
            continue
        if not (1 <= age <= 20):
            errs.append(f"line {i}: age {age} out of [1, 20]")

        try:
            mileage = int(row["mileage_km"])
        except ValueError:
            errs.append(f"line {i}: mileage invalid: {row['mileage_km']!r}")
            continue
        if not (1_000 <= mileage <= 500_000):
            errs.append(f"line {i}: mileage {mileage} out of [1k, 500k]")

        try:
            msrp = int(row["msrp_new_rub"])
        except ValueError:
            errs.append(f"line {i}: msrp_new_rub invalid: {row['msrp_new_rub']!r}")
            continue
        if not (0 < msrp <= 50_000_000):
            errs.append(f"line {i}: msrp {msrp} out of (0, 50M]")

        try:
            observed = int(row["observed_market_price_rub"])
        except ValueError:
            errs.append(f"line {i}: observed invalid: {row['observed_market_price_rub']!r}")
            continue
        if not (0 < observed <= 50_000_000):
            errs.append(f"line {i}: observed {observed} out of (0, 50M]")

        if observed >= msrp:
            errs.append(f"line {i}: observed {observed:,} >= msrp {msrp:,} — depreciation expects observed < msrp")

        obs_date_str = row["observation_date"].strip()
        if not ISO_DATE_RE.match(obs_date_str):
            errs.append(f"line {i}: observation_date {obs_date_str!r} not ISO")
        else:
            try:
                obs_date = date.fromisoformat(obs_date_str)
            except ValueError:
                errs.append(f"line {i}: observation_date {obs_date_str!r} not parseable")
                continue

            days_old = (TODAY - obs_date).days
            if days_old > 365:
                errs.append(f"line {i}: observation_date {obs_date_str} older than 12 months ({days_old} days)")
            if days_old < -1:
                errs.append(f"line {i}: observation_date {obs_date_str} is in the future")

            implied_age = obs_date.year - year_p
            if abs(implied_age - age) > 1:
                errs.append(
                    f"line {i}: age_years {age} mismatches "
                    f"(observation_date.year - year_of_purchase) = {implied_age}"
                )

        if not URL_RE.match(row["source_url"].strip()):
            errs.append(f"line {i}: source_url {row['source_url']!r} not a valid HTTP(S) URL")

        if not row["source_note"].strip():
            errs.append(f"line {i}: empty source_note")

    if case_ids:
        if case_ids[0] != 1:
            errs.append(f"case_id must start at 1, got {case_ids[0]}")
        if case_ids != sorted(case_ids):
            errs.append("case_id is not monotonically increasing")
        if len(set(case_ids)) != len(case_ids):
            errs.append("case_id duplicates found")

    missing_tiers = TIERS - seen_tiers
    if missing_tiers:
        errs.append(f"brand_tier coverage: missing {sorted(missing_tiers)}")

    missing_segments = SEGMENTS - seen_segments
    if missing_segments:
        errs.append(f"segment coverage: missing {sorted(missing_segments)}")

    if errs:
        print("FAIL")
        for e in errs[:30]:
            print(" ", e)
        return 1

    tier_str = ", ".join(f"{k}:{v}" for k, v in sorted(tier_counts.items()))
    seg_str = ", ".join(f"{k}:{v}" for k, v in sorted(segment_counts.items()))
    print(f"OK - depreciation_calibration.csv ({len(rows)} cases)")
    print(f"     brand_tier coverage: {tier_str}")
    print(f"     segment    coverage: {seg_str}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
