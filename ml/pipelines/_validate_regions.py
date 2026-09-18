"""Sanity checks for ml/data/seed/regions.csv."""

from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path


VALID_DISTRICTS = {
    "Центральный",
    "Северо-Западный",
    "Южный",
    "Северо-Кавказский",
    "Приволжский",
    "Уральский",
    "Сибирский",
    "Дальневосточный",
}
VALID_CLIMATES = {"south", "central", "north"}


def main() -> int:
    path = Path(__file__).resolve().parents[1] / "data" / "seed" / "regions.csv"
    with path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    errors: list[str] = []

    if len(rows) != 85:
        errors.append(f"expected 85 rows, got {len(rows)}")

    ids = [r["id"] for r in rows]
    if len(set(ids)) != len(ids):
        dup = [i for i, c in Counter(ids).items() if c > 1]
        errors.append(f"duplicate ids: {dup}")

    expected_ids = [str(i) for i in range(1, 86)]
    if ids != expected_ids:
        errors.append("ids are not a contiguous 1..85 sequence")

    iso_codes = [r["iso_code"] for r in rows]
    if len(set(iso_codes)) != len(iso_codes):
        dup = [i for i, c in Counter(iso_codes).items() if c > 1]
        errors.append(f"duplicate iso_codes: {dup}")

    names = [r["name"] for r in rows]
    if len(set(names)) != len(names):
        dup = [n for n, c in Counter(names).items() if c > 1]
        errors.append(f"duplicate names: {dup}")

    bad_districts = {r["federal_district"] for r in rows} - VALID_DISTRICTS
    if bad_districts:
        errors.append(f"unexpected federal districts: {bad_districts}")

    bad_climates = {r["climate_zone"] for r in rows} - VALID_CLIMATES
    if bad_climates:
        errors.append(f"unexpected climate zones: {bad_climates}")

    for r in rows:
        try:
            pop = int(r["population_thousands"])
        except ValueError:
            errors.append(f"id={r['id']}: population_thousands not int")
            continue
        if not (1 <= pop <= 20000):
            errors.append(f"id={r['id']}: population {pop} out of range")

    distr_counter = Counter(r["federal_district"] for r in rows)
    expected_distr = {
        "Центральный": 18,
        "Северо-Западный": 11,
        "Южный": 8,
        "Северо-Кавказский": 7,
        "Приволжский": 14,
        "Уральский": 6,
        "Сибирский": 10,
        "Дальневосточный": 11,
    }
    for d, want in expected_distr.items():
        got = distr_counter.get(d, 0)
        if got != want:
            errors.append(f"district '{d}': expected {want}, got {got}")

    climate_counter = Counter(r["climate_zone"] for r in rows)

    print(f"rows: {len(rows)}")
    print(f"unique ids: {len(set(ids))}")
    print(f"unique iso_codes: {len(set(iso_codes))}")
    print(f"federal districts: {dict(distr_counter)}")
    print(f"climate zones: {dict(climate_counter)}")

    if errors:
        print("\nERRORS:")
        for e in errors:
            print(f"  - {e}")
        return 1

    print("\nOK: all invariants hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
