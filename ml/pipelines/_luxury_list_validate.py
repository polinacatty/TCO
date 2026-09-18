"""Checks for ``luxury_car_list.csv`` (Minpromtorgs «дорогие» авто, п. 2 ст. 362 НК РФ)."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CSV_PATH = REPO / "ml" / "data" / "seed" / "luxury_car_list.csv"

REQUIRED_COLS = [
    "make",
    "model",
    "engine_type",
    "engine_volume_l",
    "price_tier_min_rub",
]


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
    n = len(rows)
    if n < 500:
        errs.append(f"expected at least 500 rows (ГАРАНТ 2026 ~573 позиций), got {n}")
    tiers = {"10000000", "15000000"}
    for i, row in enumerate(rows, start=2):
        if row["price_tier_min_rub"] not in tiers:
            errs.append(f"line {i}: bad price_tier_min_rub {row['price_tier_min_rub']}")
        if not row["make"].strip():
            errs.append(f"line {i}: empty make")
        if not row["model"].strip():
            errs.append(f"line {i}: empty model")
    if errs:
        print("FAIL")
        for e in errs[:40]:
            print(" ", e)
        if len(errs) > 40:
            print(f" ... +{len(errs) - 40} more")
        return 1
    print(f"OK — luxury_car_list.csv ({n} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
