"""Checks for ``service_operations.csv`` (шаг 3.1).

Per план спринта 3 §S3.1: каталог типовых операций ТО, ~30–40 строк,
все 7 категорий из enum-а схемы БД покрыты, топ-15 «базовых» операций
обязательно присутствуют.

Validates:
1. Schema (column names match exactly).
2. Row count in [30, 40].
3. Monotonic ``id`` starting from 1.
4. Unique ``code``.
5. Unique ``name`` (для UX-стабильности).
6. ``code`` matches regex ``^[a-z0-9_]+$`` (lowercase + underscore).
7. ``category`` ∈ {fluids, filters, brakes, belts, electrics, body, other}.
8. ``default_norm_hours`` ∈ (0, 8].
9. Coverage: все 7 категорий присутствуют.
10. Coverage: top-15 «базовых» операций обязательно присутствуют
    (масло, фильтры, колодки, свечи, ГРМ, антифриз, диагностика, и т.д.).
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CSV_PATH = REPO / "ml" / "data" / "seed" / "service_operations.csv"

REQUIRED_COLS = ["id", "code", "name", "default_norm_hours", "category"]
CATEGORIES = {"fluids", "filters", "brakes", "belts", "electrics", "body", "other"}
CODE_RE = re.compile(r"^[a-z0-9_]+$")

ESSENTIAL_CODES = {
    "oil_change_engine",
    "oil_filter",
    "air_filter",
    "cabin_filter",
    "spark_plugs",
    "brake_pads_front",
    "brake_pads_rear",
    "brake_fluid_change",
    "coolant_change",
    "timing_belt_kit",
    "battery_replacement",
    "wiper_blades_front",
    "tyre_swap_seasonal",
    "wheel_balancing",
    "diagnostics_full",
}


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

    if not (30 <= len(rows) <= 40):
        errs.append(f"row count {len(rows)} not in [30, 40]")

    ids: list[int] = []
    codes: list[str] = []
    names: list[str] = []
    seen_categories: set[str] = set()
    category_counts: dict[str, int] = {}

    for i, row in enumerate(rows, start=2):
        try:
            rid = int(row["id"])
        except ValueError:
            errs.append(f"line {i}: id must be int, got {row['id']!r}")
            continue
        ids.append(rid)

        code = row["code"].strip()
        if not CODE_RE.match(code):
            errs.append(f"line {i}: code {code!r} doesn't match ^[a-z0-9_]+$")
        codes.append(code)

        name = row["name"].strip()
        if not name:
            errs.append(f"line {i}: empty name")
        names.append(name)

        try:
            nh = float(row["default_norm_hours"])
        except ValueError:
            errs.append(f"line {i}: default_norm_hours must be float, got {row['default_norm_hours']!r}")
            continue
        if not (0 < nh <= 8):
            errs.append(f"line {i}: default_norm_hours {nh} out of (0, 8]")

        cat = row["category"].strip()
        if cat not in CATEGORIES:
            errs.append(f"line {i}: category {cat!r} not in {sorted(CATEGORIES)}")
        else:
            seen_categories.add(cat)
            category_counts[cat] = category_counts.get(cat, 0) + 1

    if ids:
        if ids[0] != 1:
            errs.append(f"id must start at 1, got {ids[0]}")
        if ids != sorted(ids):
            errs.append("id is not monotonically increasing")
        if len(set(ids)) != len(ids):
            errs.append("id duplicates found")

    if len(set(codes)) != len(codes):
        from collections import Counter

        dups = [c for c, n in Counter(codes).items() if n > 1]
        errs.append(f"code duplicates: {dups}")

    if len(set(names)) != len(names):
        from collections import Counter

        dups = [n for n, c in Counter(names).items() if c > 1]
        errs.append(f"name duplicates: {dups}")

    missing_categories = CATEGORIES - seen_categories
    if missing_categories:
        errs.append(f"category coverage: missing {sorted(missing_categories)}")

    code_set = set(codes)
    missing_essential = ESSENTIAL_CODES - code_set
    if missing_essential:
        errs.append(f"essential top-15 codes missing: {sorted(missing_essential)}")

    if errs:
        print("FAIL")
        for e in errs[:30]:
            print(" ", e)
        return 1

    cat_str = ", ".join(f"{k}:{v}" for k, v in sorted(category_counts.items()))
    print(f"OK - service_operations.csv ({len(rows)} rows; 7/7 categories covered)")
    print(f"     by category: {cat_str}")
    print(f"     essential top-15: 15/15 present")
    return 0


if __name__ == "__main__":
    sys.exit(main())
