"""Checks for ``car_makes.csv`` (брендов в каталоге сервиса).

Validates:
1. Schema (column names match exactly).
2. Monotonic INT id starting at 1.
3. Uniqueness of ``name`` and ``name_normalized``.
4. ``brand_tier`` is one of the enum values used by ADR-0001.
5. ``name_normalized`` is lowercase, no spaces, no hyphens, no dots.
6. Row count in [80, 120] (sprint 2 plan §S2.1).
7. Cross-check: every ``make`` in ``luxury_car_list.csv`` resolves to some
   row in ``car_makes.csv`` via ``name_normalized``.
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MAKES_CSV = REPO / "ml" / "data" / "seed" / "car_makes.csv"
LUXURY_CSV = REPO / "ml" / "data" / "seed" / "luxury_car_list.csv"

REQUIRED_COLS = ["id", "name", "name_normalized", "country", "brand_tier"]
TIERS = {"russian", "mass", "japanese_korean_mass", "chinese", "premium"}
NORM_RE = re.compile(r"^[a-z0-9]+$")


def _normalize(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def main() -> int:
    errs: list[str] = []
    if not MAKES_CSV.is_file():
        print("FAIL: missing", MAKES_CSV)
        return 1

    with MAKES_CSV.open(encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        if r.fieldnames != REQUIRED_COLS:
            errs.append(f"columns: got {r.fieldnames}")
        rows = list(r)

    n = len(rows)
    if not (80 <= n <= 120):
        errs.append(f"row count: expected [80,120], got {n}")

    seen_id: set[int] = set()
    seen_name: set[str] = set()
    seen_norm: set[str] = set()
    norm_to_name: dict[str, str] = {}

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

        name = row["name"].strip()
        norm = row["name_normalized"].strip()
        country = row["country"].strip()
        tier = row["brand_tier"].strip()

        if not name:
            errs.append(f"line {i}: empty name")
        if name in seen_name:
            errs.append(f"line {i}: duplicate name {name!r}")
        seen_name.add(name)

        if not NORM_RE.match(norm):
            errs.append(f"line {i}: name_normalized {norm!r} must be [a-z0-9]+")
        if norm in seen_norm:
            errs.append(f"line {i}: duplicate name_normalized {norm!r}")
        seen_norm.add(norm)
        norm_to_name[norm] = name

        expected_norm = _normalize(name)
        if norm != expected_norm:
            errs.append(
                f"line {i}: name_normalized {norm!r} != normalize({name!r})={expected_norm!r}"
            )

        if not country:
            errs.append(f"line {i}: empty country")

        if tier not in TIERS:
            errs.append(f"line {i}: brand_tier {tier!r} not in {sorted(TIERS)}")

    # Cross-check: every make in luxury list must map to a row here
    if LUXURY_CSV.is_file():
        with LUXURY_CSV.open(encoding="utf-8", newline="") as f:
            lr = csv.DictReader(f)
            luxury_makes = {row["make"].strip() for row in lr}
        unresolved = sorted(
            m for m in luxury_makes if _normalize(m) not in norm_to_name
        )
        if unresolved:
            errs.append(
                "luxury_car_list.csv has makes not present in car_makes.csv: "
                + ", ".join(unresolved)
            )
    else:
        errs.append(f"missing cross-check source: {LUXURY_CSV}")

    if errs:
        print("FAIL")
        for e in errs[:40]:
            print(" ", e)
        if len(errs) > 40:
            print(f" ... +{len(errs) - 40} more")
        return 1

    tier_counts: dict[str, int] = {}
    for row in rows:
        t = row["brand_tier"]
        tier_counts[t] = tier_counts.get(t, 0) + 1
    tier_summary = ", ".join(f"{t}:{tier_counts[t]}" for t in sorted(tier_counts))
    print(f"OK — car_makes.csv ({n} rows; {tier_summary})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
