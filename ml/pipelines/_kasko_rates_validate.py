"""Checks for ``kasko_rates.csv`` (sprint 3 step S3.6).

Validates ``kasko_rates.csv`` (10 проверок):

1. **Schema** — column names match exactly.
2. **Row count** — ровно 5 × 6 × 5 = 150.
3. **Cartesian completeness** — каждая (tier, segment, age) встречается ровно один раз.
4. **Enum membership** — `brand_tier` ∈ 5 значений, `segment` ∈ 6 значений.
5. **Age range** — `age_year_bucket` ∈ {1, 2, 3, 4, 5}.
6. **Range** — `kasko_rate_pct ∈ (0, 20]`.
7. **Step granularity** — `kasko_rate_pct` округлено до 0.5 % (тарифная сетка
   страховщика: 4.0 / 4.5 / 5.0 / ..., без 4.7 / 4.83).
8. **Tier monotonicity** — для каждой пары `(segment, age)` последовательность
    ставок по `brand_tier` в порядке `russian → japanese_korean_mass → mass →
    chinese → premium` неубывающая.
9. **Age monotonicity** — для каждой пары `(brand_tier, segment)` последовательность
    ставок по `age_year_bucket = 1..5` неубывающая (старше → дороже).
10. **Anchor sanity** — план §S3.6 фиксирует A_B/age=1: russian=4.0, mass=5.0,
    jp_kr=4.5, chinese=6.0, premium=7.0. Допускается погрешность ±0.5 п.п.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SEED = REPO / "ml" / "data" / "seed"

KASKO_RATES_CSV = SEED / "kasko_rates.csv"

REQUIRED_RATES_COLS = [
    "brand_tier",
    "segment",
    "age_year_bucket",
    "kasko_rate_pct",
]

BRAND_TIERS_ORDERED = (
    "russian",
    "japanese_korean_mass",
    "mass",
    "chinese",
    "premium",
)
TIERS = set(BRAND_TIERS_ORDERED)

SEGMENTS_ORDERED = (
    "A_B",
    "C_D",
    "E_F",
    "J_CROSS",
    "J_SUV",
    "LCV",
)
SEGMENTS = set(SEGMENTS_ORDERED)

AGES = {1, 2, 3, 4, 5}

# Опорные точки плана §S3.6 для проверки 10 (anchor sanity).
ANCHOR_AB_AGE1: dict[str, float] = {
    "russian":              4.0,
    "japanese_korean_mass": 4.5,
    "mass":                 5.0,
    "chinese":              6.0,
    "premium":              7.0,
}
ANCHOR_TOLERANCE = 0.5  # допустимое отклонение в п.п.


def validate_kasko_rates() -> list[str]:
    errs: list[str] = []

    if not KASKO_RATES_CSV.is_file():
        errs.append(f"missing {KASKO_RATES_CSV}")
        return errs

    with KASKO_RATES_CSV.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != REQUIRED_RATES_COLS:
            errs.append(f"columns: got {reader.fieldnames}, expected {REQUIRED_RATES_COLS}")
            return errs
        rows = list(reader)

    expected = len(BRAND_TIERS_ORDERED) * len(SEGMENTS_ORDERED) * len(AGES)
    if len(rows) != expected:
        errs.append(f"row count: expected {expected} (5x6x5), got {len(rows)}")

    seen: set[tuple[str, str, int]] = set()
    pct_by_combo: dict[tuple[str, str, int], float] = {}

    for i, row in enumerate(rows, start=2):
        tier = row["brand_tier"].strip()
        segment = row["segment"].strip()
        age_raw = row["age_year_bucket"].strip()
        pct_raw = row["kasko_rate_pct"].strip()

        if tier not in TIERS:
            errs.append(f"line {i}: brand_tier {tier!r} not in {sorted(TIERS)}")
            continue

        if segment not in SEGMENTS:
            errs.append(f"line {i}: segment {segment!r} not in {sorted(SEGMENTS)}")
            continue

        try:
            age = int(age_raw)
        except ValueError:
            errs.append(f"line {i}: age_year_bucket must be int, got {age_raw!r}")
            continue
        if age not in AGES:
            errs.append(f"line {i}: age_year_bucket {age} not in {sorted(AGES)}")
            continue

        try:
            pct = float(pct_raw)
        except ValueError:
            errs.append(f"line {i}: kasko_rate_pct must be float, got {pct_raw!r}")
            continue
        if not (0 < pct <= 20):
            errs.append(f"line {i}: kasko_rate_pct {pct} out of (0, 20]")

        if abs(pct * 2 - round(pct * 2)) > 1e-6:
            errs.append(f"line {i}: kasko_rate_pct {pct} not aligned to 0.5%-step")

        combo = (tier, segment, age)
        if combo in seen:
            errs.append(f"line {i}: duplicate combo {combo}")
        seen.add(combo)
        pct_by_combo[combo] = pct

    if len(seen) != expected:
        missing: list[tuple[str, str, int]] = []
        for t in BRAND_TIERS_ORDERED:
            for s in SEGMENTS_ORDERED:
                for a in AGES:
                    if (t, s, a) not in seen:
                        missing.append((t, s, a))
        errs.append(f"cartesian incomplete: missing {len(missing)} combos, e.g. {missing[:3]}")

    tier_violations: list[str] = []
    for s in SEGMENTS_ORDERED:
        for a in AGES:
            seq: list[tuple[str, float]] = []
            for t in BRAND_TIERS_ORDERED:
                v = pct_by_combo.get((t, s, a))
                if v is None:
                    seq = []
                    break
                seq.append((t, v))
            for k in range(1, len(seq)):
                if seq[k][1] < seq[k - 1][1]:
                    tier_violations.append(
                        f"({s}, age={a}): {seq[k - 1][0]}={seq[k - 1][1]} > {seq[k][0]}={seq[k][1]}"
                    )
                    break
    if tier_violations:
        errs.append(
            f"tier monotonicity: {len(tier_violations)} (segment, age) pairs non-increasing, "
            f"first 3: {tier_violations[:3]}"
        )

    age_violations: list[str] = []
    for t in BRAND_TIERS_ORDERED:
        for s in SEGMENTS_ORDERED:
            seq_age: list[tuple[int, float]] = []
            for a in sorted(AGES):
                v = pct_by_combo.get((t, s, a))
                if v is None:
                    seq_age = []
                    break
                seq_age.append((a, v))
            for k in range(1, len(seq_age)):
                if seq_age[k][1] < seq_age[k - 1][1]:
                    age_violations.append(
                        f"({t}, {s}): age={seq_age[k - 1][0]}={seq_age[k - 1][1]} > "
                        f"age={seq_age[k][0]}={seq_age[k][1]}"
                    )
                    break
    if age_violations:
        errs.append(
            f"age monotonicity: {len(age_violations)} (tier, segment) pairs non-increasing, "
            f"first 3: {age_violations[:3]}"
        )

    anchor_misses: list[str] = []
    for tier, expected_pct in ANCHOR_AB_AGE1.items():
        actual = pct_by_combo.get((tier, "A_B", 1))
        if actual is None:
            anchor_misses.append(f"missing A_B/age=1/{tier}")
            continue
        if abs(actual - expected_pct) > ANCHOR_TOLERANCE + 1e-6:
            anchor_misses.append(
                f"A_B/age=1/{tier}: actual {actual} != plan {expected_pct} (±{ANCHOR_TOLERANCE})"
            )
    if anchor_misses:
        errs.append(
            f"anchor sanity (план §S3.6 опорные точки): {len(anchor_misses)} misses, "
            f"first 3: {anchor_misses[:3]}"
        )

    return errs


def main() -> int:
    print(f"Validating {KASKO_RATES_CSV.relative_to(REPO)}")
    errs = validate_kasko_rates()
    if errs:
        print("FAIL")
        for e in errs[:40]:
            print(" ", e)
        if len(errs) > 40:
            print(f" ... +{len(errs) - 40} more")
        return 1

    with KASKO_RATES_CSV.open(encoding="utf-8", newline="") as f:
        rates_rows = list(csv.DictReader(f))
    pcts = [float(r["kasko_rate_pct"]) for r in rates_rows]
    print(
        f"OK - kasko_rates.csv ({len(rates_rows)} rows; "
        f"{len(BRAND_TIERS_ORDERED)} tiers x {len(SEGMENTS_ORDERED)} segments x {len(AGES)} ages)"
    )
    print(
        f"     kasko_rate_pct range: [{min(pcts):.1f}..{max(pcts):.1f}] %, "
        f"median={sorted(pcts)[len(pcts) // 2]:.1f} %"
    )
    print(
        f"     monotonicity: tier 30/30 (segment x age), age 30/30 (tier x segment)"
    )
    print(
        f"     anchor sanity: A_B/age=1 — все 5 ярусов попадают в план §S3.6 "
        f"в пределах ±{ANCHOR_TOLERANCE} п.п."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
