"""Checks for ``depreciation_rates.csv`` (шаг 2.7, ADR-0001).

Validates:
1. Schema (column names match exactly).
2. Row count: ровно 150 (6 сегментов x 5 ярусов x 5 возрастных корзин).
3. Cartesian completeness — каждая комбинация (segment, brand_tier,
   age_year_bucket) встречается ровно один раз.
4. Enum membership for ``segment``, ``brand_tier``.
5. ``age_year_bucket`` is INT in {1, 2, 3, 4, 5}.
6. ``annual_depreciation_pct`` in (0, 35].
7. Monotonicity — для каждой пары (segment, brand_tier) последовательность
   значений по age_year_bucket = 1..5 невозрастающая.
8. ``valid_from`` is ISO date.
9. ``source_note`` non-empty.
"""

from __future__ import annotations

import csv
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CSV_PATH = REPO / "ml" / "data" / "seed" / "depreciation_rates.csv"

REQUIRED_COLS = [
    "segment", "brand_tier", "age_year_bucket",
    "annual_depreciation_pct", "source_note", "valid_from",
]
SEGMENTS = {"A_B", "C_D", "E_F", "J_SUV", "J_CROSS", "LCV"}
TIERS = {"russian", "mass", "japanese_korean_mass", "chinese", "premium"}
AGES = {1, 2, 3, 4, 5}
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def main() -> int:
    errs: list[str] = []

    if not CSV_PATH.is_file():
        print("FAIL: missing", CSV_PATH)
        return 1

    with CSV_PATH.open(encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        if r.fieldnames != REQUIRED_COLS:
            errs.append(f"columns: got {r.fieldnames}")
        rows = list(r)

    if len(rows) != 150:
        errs.append(f"expected 150 rows (6 x 5 x 5), got {len(rows)}")

    seen_combo: set[tuple[str, str, int]] = set()
    values_by_pair: dict[tuple[str, str], dict[int, float]] = defaultdict(dict)

    for i, row in enumerate(rows, start=2):
        seg = row["segment"].strip()
        tier = row["brand_tier"].strip()
        age_raw = row["age_year_bucket"].strip()
        pct_raw = row["annual_depreciation_pct"].strip()
        valid_from = row["valid_from"].strip()
        source = row["source_note"].strip()

        if seg not in SEGMENTS:
            errs.append(f"line {i}: segment {seg!r} not in {sorted(SEGMENTS)}")
            continue
        if tier not in TIERS:
            errs.append(f"line {i}: brand_tier {tier!r} not in {sorted(TIERS)}")
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
            errs.append(f"line {i}: annual_depreciation_pct must be float, got {pct_raw!r}")
            continue
        if not (0 < pct <= 35):
            errs.append(f"line {i}: annual_depreciation_pct {pct} out of (0,35]")

        if not ISO_DATE_RE.match(valid_from):
            errs.append(f"line {i}: valid_from {valid_from!r} is not ISO date")
        else:
            try:
                date.fromisoformat(valid_from)
            except ValueError:
                errs.append(f"line {i}: valid_from {valid_from!r} not parseable")

        if not source:
            errs.append(f"line {i}: empty source_note")

        combo = (seg, tier, age)
        if combo in seen_combo:
            errs.append(f"line {i}: duplicate combo {combo}")
        seen_combo.add(combo)
        values_by_pair[(seg, tier)][age] = pct

    expected_total = len(SEGMENTS) * len(TIERS) * len(AGES)
    if len(seen_combo) != expected_total:
        missing = []
        for seg in SEGMENTS:
            for tier in TIERS:
                for age in AGES:
                    if (seg, tier, age) not in seen_combo:
                        missing.append((seg, tier, age))
        errs.append(
            f"cartesian incomplete: missing {len(missing)} combos, e.g. {missing[:3]}"
        )

    for (seg, tier), age_to_pct in values_by_pair.items():
        if len(age_to_pct) == len(AGES):
            seq = [age_to_pct[a] for a in sorted(AGES)]
            for k in range(1, len(seq)):
                if seq[k] > seq[k - 1]:
                    errs.append(
                        f"non-monotonic ({seg}, {tier}): age={k} pct={seq[k]} > age={k} pct={seq[k - 1]}"
                    )
                    break

    if errs:
        print("FAIL")
        for e in errs[:40]:
            print(" ", e)
        if len(errs) > 40:
            print(f" ... +{len(errs) - 40} more")
        return 1

    pcts = [float(r["annual_depreciation_pct"]) for r in rows]
    print(
        f"OK - depreciation_rates.csv ({len(rows)} rows; "
        f"{len(SEGMENTS)} segments x {len(TIERS)} tiers x {len(AGES)} ages)"
    )
    print(
        f"     pct range: [{min(pcts):.2f}..{max(pcts):.2f}], "
        f"median={sorted(pcts)[len(pcts)//2]:.2f}"
    )
    print(
        f"     monotonicity: 30/30 (segment, brand_tier) pairs are non-increasing over age"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
