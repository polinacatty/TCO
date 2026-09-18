"""Checks for ``car_generations.csv`` — поколения моделей автомобилей.

Validates:
1. Schema (column names match exactly).
2. Monotonic INT id starting at 1.
3. Every ``model_id`` resolves to a row in ``car_models.csv``.
4. Uniqueness of ``(model_id, name, restyling)`` per schema PK.
5. ``year_from`` in plausible range [1965, current_year + 1] (1965 = UAZ 3909).
6. ``year_to`` is either empty or >= ``year_from``.
7. ``restyling`` is integer >= 0 and <= 5.
8. ``name`` is non-empty (typically a roman numeral I..VIII or codename).
9. Row count: ровно столько же, сколько моделей в ``car_models.csv``.
   MVP-стратегия — одно поколение на модель (см. _car_generations_build.py).
"""

from __future__ import annotations

import csv
import datetime as dt
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MODELS_CSV = REPO / "ml" / "data" / "seed" / "car_models.csv"
GENS_CSV = REPO / "ml" / "data" / "seed" / "car_generations.csv"

REQUIRED_COLS = ["id", "model_id", "name", "year_from", "year_to", "restyling"]
MIN_YEAR = 1965
MAX_YEAR = dt.date.today().year + 1


def main() -> int:
    errs: list[str] = []

    if not GENS_CSV.is_file():
        print("FAIL: missing", GENS_CSV)
        return 1
    if not MODELS_CSV.is_file():
        print("FAIL: missing", MODELS_CSV)
        return 1

    model_ids: set[int] = set()
    with MODELS_CSV.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            model_ids.add(int(row["id"]))

    with GENS_CSV.open(encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        if r.fieldnames != REQUIRED_COLS:
            errs.append(f"columns: got {r.fieldnames}")
        rows = list(r)

    n = len(rows)
    if n != len(model_ids):
        errs.append(f"row count: expected {len(model_ids)} (= car_models rows), got {n}")

    seen_id: set[int] = set()
    seen_pk: set[tuple[int, str, int]] = set()
    covered_models: set[int] = set()

    for i, row in enumerate(rows, start=2):
        idx = i - 1
        try:
            rid = int(row["id"])
        except ValueError:
            errs.append(f"line {i}: id must be int, got {row['id']!r}")
            continue
        if rid != idx:
            errs.append(f"line {i}: expected id={idx}, got {rid}")
        if rid in seen_id:
            errs.append(f"line {i}: duplicate id {rid}")
        seen_id.add(rid)

        try:
            mid = int(row["model_id"])
        except ValueError:
            errs.append(f"line {i}: model_id must be int, got {row['model_id']!r}")
            continue
        if mid not in model_ids:
            errs.append(f"line {i}: unknown model_id {mid}")
            continue
        covered_models.add(mid)

        name = row["name"].strip()
        if not name:
            errs.append(f"line {i}: empty name")

        try:
            restyling = int(row["restyling"])
        except ValueError:
            errs.append(f"line {i}: restyling must be int, got {row['restyling']!r}")
            continue
        if not (0 <= restyling <= 5):
            errs.append(f"line {i}: restyling {restyling} out of [0,5]")

        pk = (mid, name, restyling)
        if pk in seen_pk:
            errs.append(f"line {i}: duplicate PK (model_id={mid}, name={name!r}, restyling={restyling})")
        seen_pk.add(pk)

        try:
            yf = int(row["year_from"])
        except ValueError:
            errs.append(f"line {i}: year_from must be int, got {row['year_from']!r}")
            continue
        if not (MIN_YEAR <= yf <= MAX_YEAR):
            errs.append(f"line {i}: year_from {yf} out of [{MIN_YEAR},{MAX_YEAR}]")

        yt_raw = row["year_to"].strip()
        if yt_raw:
            try:
                yt = int(yt_raw)
            except ValueError:
                errs.append(f"line {i}: year_to must be int or empty, got {yt_raw!r}")
                continue
            if yt < yf:
                errs.append(f"line {i}: year_to {yt} < year_from {yf}")
            if yt > MAX_YEAR:
                errs.append(f"line {i}: year_to {yt} > {MAX_YEAR}")

    uncovered = sorted(model_ids - covered_models)
    if uncovered:
        errs.append(f"models without any generation: {uncovered[:10]} (+{max(0, len(uncovered) - 10)} more)")

    if errs:
        print("FAIL")
        for e in errs[:40]:
            print(" ", e)
        if len(errs) > 40:
            print(f" ... +{len(errs) - 40} more")
        return 1

    years = [int(r["year_from"]) for r in rows]
    print(
        f"OK — car_generations.csv ({n} rows; {len(covered_models)}/{len(model_ids)} models covered; "
        f"year_from min={min(years)}, max={max(years)}, median={sorted(years)[len(years)//2]})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
