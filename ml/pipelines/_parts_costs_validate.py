"""Checks for ``parts_costs.csv`` (sprint 3 step S3.4).

Validates:

1. **Schema** — column names match exactly.
2. **Row count** — ровно 32 × 7 = 224 (32 операции из `service_operations.csv`,
   7 brand_segments из схемы БД).
3. **Cartesian completeness** — каждая комбинация (operation_id, brand_segment)
   встречается ровно один раз.
4. **FK to service_operations** — каждый ``operation_id`` существует в
   `service_operations.csv`, и `operation_code` соответствует ему.
5. **Enum membership** — `brand_segment` ∈ 7 допустимых значений.
6. **Range** — `avg_parts_cost_rub ∈ [50, 50_000]` (плановое ТО, не
   ремонт; верхняя граница — комплект ГРМ для премиум).
7. **Monotonicity** — для каждой операции последовательность цен по
   `brand_segment` в каноническом порядке
   ``russian ≤ chinese ≤ korean ≤ japanese ≤ european_mass ≤ american ≤
     european_premium`` неубывающая (стрательно `<=`, не `<`, чтобы
   разрешить округлительные равенства).
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SEED = REPO / "ml" / "data" / "seed"

PARTS_COSTS_CSV = SEED / "parts_costs.csv"
SERVICE_OPS_CSV = SEED / "service_operations.csv"

REQUIRED_COLS = [
    "operation_id",
    "operation_code",
    "brand_segment",
    "avg_parts_cost_rub",
]

BRAND_SEGMENTS_ORDERED = (
    "russian",
    "chinese",
    "korean",
    "japanese",
    "european_mass",
    "american",
    "european_premium",
)
BRAND_SEGMENTS = set(BRAND_SEGMENTS_ORDERED)


def main() -> int:
    if not PARTS_COSTS_CSV.is_file():
        print("FAIL: missing", PARTS_COSTS_CSV, file=sys.stderr)
        return 1
    if not SERVICE_OPS_CSV.is_file():
        print("FAIL: missing", SERVICE_OPS_CSV, file=sys.stderr)
        return 1

    op_id_to_code: dict[int, str] = {}
    with SERVICE_OPS_CSV.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            op_id_to_code[int(row["id"])] = row["code"]
    expected_ops = len(op_id_to_code)

    with PARTS_COSTS_CSV.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != REQUIRED_COLS:
            print(f"FAIL: columns: got {reader.fieldnames}, expected {REQUIRED_COLS}")
            return 1
        rows = list(reader)

    errs: list[str] = []
    expected_total = expected_ops * len(BRAND_SEGMENTS_ORDERED)
    if len(rows) != expected_total:
        errs.append(
            f"row count: expected {expected_total} ({expected_ops} ops x "
            f"{len(BRAND_SEGMENTS_ORDERED)} segments), got {len(rows)}"
        )

    seen_combo: set[tuple[int, str]] = set()
    prices_by_op: dict[int, dict[str, int]] = defaultdict(dict)

    for i, row in enumerate(rows, start=2):
        try:
            op_id = int(row["operation_id"])
        except ValueError:
            errs.append(f"line {i}: operation_id must be int, got {row['operation_id']!r}")
            continue

        if op_id not in op_id_to_code:
            errs.append(
                f"line {i}: operation_id={op_id} not present in service_operations.csv"
            )
            continue

        if row["operation_code"] != op_id_to_code[op_id]:
            errs.append(
                f"line {i}: operation_code {row['operation_code']!r} != "
                f"{op_id_to_code[op_id]!r} for id={op_id}"
            )

        seg = row["brand_segment"].strip()
        if seg not in BRAND_SEGMENTS:
            errs.append(f"line {i}: brand_segment {seg!r} not in {sorted(BRAND_SEGMENTS)}")
            continue

        try:
            price = int(row["avg_parts_cost_rub"])
        except ValueError:
            errs.append(
                f"line {i}: avg_parts_cost_rub must be int, got {row['avg_parts_cost_rub']!r}"
            )
            continue
        if not (50 <= price <= 50_000):
            errs.append(f"line {i}: avg_parts_cost_rub {price} out of [50, 50_000]")

        combo = (op_id, seg)
        if combo in seen_combo:
            errs.append(f"line {i}: duplicate combo {combo}")
        seen_combo.add(combo)
        prices_by_op[op_id][seg] = price

    if len(seen_combo) != expected_total:
        missing: list[tuple[int, str]] = []
        for op_id in op_id_to_code:
            for seg in BRAND_SEGMENTS_ORDERED:
                if (op_id, seg) not in seen_combo:
                    missing.append((op_id, seg))
        errs.append(
            f"cartesian incomplete: missing {len(missing)} combos, e.g. {missing[:3]}"
        )

    monotonic_violations: list[str] = []
    for op_id, seg_prices in prices_by_op.items():
        if len(seg_prices) != len(BRAND_SEGMENTS_ORDERED):
            continue
        seq = [seg_prices[s] for s in BRAND_SEGMENTS_ORDERED]
        for k in range(1, len(seq)):
            if seq[k] < seq[k - 1]:
                monotonic_violations.append(
                    f"op_id={op_id} ({op_id_to_code[op_id]}): {BRAND_SEGMENTS_ORDERED[k - 1]}={seq[k - 1]} > "
                    f"{BRAND_SEGMENTS_ORDERED[k]}={seq[k]}"
                )
                break

    if monotonic_violations:
        errs.append(
            f"non-monotonic prices for {len(monotonic_violations)} operations, "
            f"first 3: {monotonic_violations[:3]}"
        )

    if errs:
        print("FAIL")
        for e in errs[:40]:
            print(" ", e)
        if len(errs) > 40:
            print(f" ... +{len(errs) - 40} more")
        return 1

    prices = [int(r["avg_parts_cost_rub"]) for r in rows]
    print(
        f"OK - parts_costs.csv ({len(rows)} rows; "
        f"{expected_ops} operations x {len(BRAND_SEGMENTS_ORDERED)} brand_segments)"
    )
    print(
        f"     price range RUB: [{min(prices):,}..{max(prices):,}], "
        f"median={sorted(prices)[len(prices) // 2]:,}"
    )
    print(
        f"     monotonicity: {expected_ops}/{expected_ops} operations are non-decreasing "
        f"across brand_segments in canonical order"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
