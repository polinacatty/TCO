"""Checks for ``labor_rates.csv`` (sprint 3 step S3.5).

Validates:

1. **Schema** — column names match exactly (4 columns).
2. **Row count** — ровно 85 × 3 = 255 (85 регионов × 3 типа СТО).
3. **Cartesian completeness** — каждая комбинация (region_id, sto_type)
   встречается ровно один раз.
4. **FK to regions** — каждый ``region_id`` существует в `regions.csv`,
   и `region_name` соответствует имени из `regions.csv`.
5. **Enum membership** — `sto_type` ∈ {private, independent, dealer}.
6. **Range** — `rate_rub_per_hour ∈ [300, 8000]` (типовая сетка тарифов).
7. **Per-region monotonicity** — для каждого региона
   ``private < independent < dealer`` строго возрастает.

Метаданные (`valid_from`, формула REGION_COEF) — в
``docs/03_data_collection/08_complex_components_methodology.md`` §5.0.
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SEED = REPO / "ml" / "data" / "seed"

LABOR_RATES_CSV = SEED / "labor_rates.csv"
REGIONS_CSV = SEED / "regions.csv"

REQUIRED_COLS = [
    "region_id",
    "region_name",
    "sto_type",
    "rate_rub_per_hour",
]

STO_TYPES_ORDERED = ("private", "independent", "dealer")
STO_TYPES = set(STO_TYPES_ORDERED)


def main() -> int:
    if not LABOR_RATES_CSV.is_file():
        print("FAIL: missing", LABOR_RATES_CSV, file=sys.stderr)
        return 1
    if not REGIONS_CSV.is_file():
        print("FAIL: missing", REGIONS_CSV, file=sys.stderr)
        return 1

    region_id_to_name: dict[int, str] = {}
    with REGIONS_CSV.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            region_id_to_name[int(row["id"])] = row["name"]
    expected_regions = len(region_id_to_name)

    with LABOR_RATES_CSV.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != REQUIRED_COLS:
            print(f"FAIL: columns: got {reader.fieldnames}, expected {REQUIRED_COLS}")
            return 1
        rows = list(reader)

    errs: list[str] = []
    expected_total = expected_regions * len(STO_TYPES_ORDERED)
    if len(rows) != expected_total:
        errs.append(
            f"row count: expected {expected_total} ({expected_regions} regions x "
            f"{len(STO_TYPES_ORDERED)} sto_types), got {len(rows)}"
        )

    seen_combo: set[tuple[int, str]] = set()
    rates_by_region: dict[int, dict[str, int]] = defaultdict(dict)

    for i, row in enumerate(rows, start=2):
        try:
            rid = int(row["region_id"])
        except ValueError:
            errs.append(f"line {i}: region_id must be int, got {row['region_id']!r}")
            continue

        if rid not in region_id_to_name:
            errs.append(
                f"line {i}: region_id={rid} not present in regions.csv"
            )
            continue

        if row["region_name"] != region_id_to_name[rid]:
            errs.append(
                f"line {i}: region_name {row['region_name']!r} != "
                f"{region_id_to_name[rid]!r} for region_id={rid}"
            )

        sto_type = row["sto_type"].strip()
        if sto_type not in STO_TYPES:
            errs.append(f"line {i}: sto_type {sto_type!r} not in {sorted(STO_TYPES)}")
            continue

        try:
            rate = int(row["rate_rub_per_hour"])
        except ValueError:
            errs.append(
                f"line {i}: rate_rub_per_hour must be int, got {row['rate_rub_per_hour']!r}"
            )
            continue
        if not (300 <= rate <= 8000):
            errs.append(f"line {i}: rate_rub_per_hour {rate} out of [300, 8000]")

        combo = (rid, sto_type)
        if combo in seen_combo:
            errs.append(f"line {i}: duplicate combo {combo}")
        seen_combo.add(combo)
        rates_by_region[rid][sto_type] = rate

    if len(seen_combo) != expected_total:
        missing: list[tuple[int, str]] = []
        for rid in region_id_to_name:
            for s in STO_TYPES_ORDERED:
                if (rid, s) not in seen_combo:
                    missing.append((rid, s))
        errs.append(
            f"cartesian incomplete: missing {len(missing)} combos, e.g. {missing[:3]}"
        )

    monotonic_violations: list[str] = []
    for rid, by_sto in rates_by_region.items():
        if len(by_sto) != len(STO_TYPES_ORDERED):
            continue
        seq = [by_sto[s] for s in STO_TYPES_ORDERED]
        for k in range(1, len(seq)):
            if seq[k] <= seq[k - 1]:
                monotonic_violations.append(
                    f"region_id={rid} ({region_id_to_name[rid]}): "
                    f"{STO_TYPES_ORDERED[k - 1]}={seq[k - 1]} >= "
                    f"{STO_TYPES_ORDERED[k]}={seq[k]}"
                )
                break

    if monotonic_violations:
        errs.append(
            f"non-strict-increasing rates for {len(monotonic_violations)} regions, "
            f"first 3: {monotonic_violations[:3]}"
        )

    if errs:
        print("FAIL")
        for e in errs[:40]:
            print(" ", e)
        if len(errs) > 40:
            print(f" ... +{len(errs) - 40} more")
        return 1

    rates = [int(r["rate_rub_per_hour"]) for r in rows]
    print(
        f"OK - labor_rates.csv ({len(rows)} rows; "
        f"{expected_regions} regions x {len(STO_TYPES_ORDERED)} sto_types)"
    )
    print(
        f"     rate range RUB/h: [{min(rates):,}..{max(rates):,}], "
        f"median={sorted(rates)[len(rates) // 2]:,}"
    )
    print(
        f"     monotonicity: {expected_regions}/{expected_regions} regions have "
        f"private < independent < dealer"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
