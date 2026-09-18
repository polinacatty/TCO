"""Checks for ``car_models.csv`` — каталог моделей автомобилей.

Validates:
1. Schema (column names match exactly).
2. Monotonic INT id starting at 1.
3. Every ``make_id`` resolves to a row in ``car_makes.csv``.
4. Uniqueness of ``(make_id, name)`` and ``(make_id, name_normalized)``.
5. ``name_normalized`` matches ``[a-z0-9]+`` and equals normalize(name).
6. ``segment`` and ``body_type`` are from the schema enums.
7. Row count in [200, 600] (sprint 2 plan §S2.2 + safe upper bound).
8. Each make in ``car_makes.csv`` has at least one model (otherwise — warning,
   never error: business decision is to keep "long tail" makes for FK integrity).
"""

from __future__ import annotations

import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MAKES_CSV = REPO / "ml" / "data" / "seed" / "car_makes.csv"
MODELS_CSV = REPO / "ml" / "data" / "seed" / "car_models.csv"

REQUIRED_COLS = ["id", "make_id", "name", "name_normalized", "segment", "body_type"]
SEGMENTS = {
    "A", "B", "C", "D", "E", "F",
    "J_SUV", "J_CROSS", "M_MPV", "S_SPORT", "LCV", "OTHER",
}
BODY_TYPES = {
    "sedan", "hatchback", "wagon", "liftback",
    "coupe", "cabriolet", "suv", "crossover", "pickup", "mpv",
}
NORM_RE = re.compile(r"^[a-z0-9]+$")


def _normalize(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def main() -> int:
    errs: list[str] = []
    warns: list[str] = []

    if not MODELS_CSV.is_file():
        print("FAIL: missing", MODELS_CSV)
        return 1
    if not MAKES_CSV.is_file():
        print("FAIL: missing", MAKES_CSV)
        return 1

    make_ids: set[int] = set()
    make_name_by_id: dict[int, str] = {}
    with MAKES_CSV.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            mid = int(row["id"])
            make_ids.add(mid)
            make_name_by_id[mid] = row["name"]

    with MODELS_CSV.open(encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        if r.fieldnames != REQUIRED_COLS:
            errs.append(f"columns: got {r.fieldnames}")
        rows = list(r)

    n = len(rows)
    if not (200 <= n <= 600):
        errs.append(f"row count: expected [200,600], got {n}")

    seen_id: set[int] = set()
    seen_pair_name: set[tuple[int, str]] = set()
    seen_pair_norm: set[tuple[int, str]] = set()
    models_per_make: dict[int, int] = defaultdict(int)

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
            mid = int(row["make_id"])
        except ValueError:
            errs.append(f"line {i}: make_id must be int, got {row['make_id']!r}")
            continue
        if mid not in make_ids:
            errs.append(f"line {i}: unknown make_id {mid}")
            continue
        models_per_make[mid] += 1

        name = row["name"].strip()
        norm = row["name_normalized"].strip()
        segment = row["segment"].strip()
        body = row["body_type"].strip()

        if not name:
            errs.append(f"line {i}: empty name")
        pair = (mid, name)
        if pair in seen_pair_name:
            errs.append(f"line {i}: duplicate (make_id={mid}, name={name!r})")
        seen_pair_name.add(pair)

        if not NORM_RE.match(norm):
            errs.append(f"line {i}: name_normalized {norm!r} must be [a-z0-9]+")
        pair_n = (mid, norm)
        if pair_n in seen_pair_norm:
            errs.append(f"line {i}: duplicate (make_id={mid}, name_normalized={norm!r})")
        seen_pair_norm.add(pair_n)

        expected_norm = _normalize(name)
        if norm != expected_norm:
            errs.append(
                f"line {i}: name_normalized {norm!r} != normalize({name!r})={expected_norm!r}"
            )

        if segment not in SEGMENTS:
            errs.append(f"line {i}: segment {segment!r} not in {sorted(SEGMENTS)}")
        if body not in BODY_TYPES:
            errs.append(f"line {i}: body_type {body!r} not in {sorted(BODY_TYPES)}")

    empty_makes = sorted(
        make_name_by_id[mid] for mid in make_ids if mid not in models_per_make
    )
    if empty_makes:
        warns.append("makes without any model (informational): " + ", ".join(empty_makes))

    if errs:
        print("FAIL")
        for e in errs[:40]:
            print(" ", e)
        if len(errs) > 40:
            print(f" ... +{len(errs) - 40} more")
        return 1

    seg_counts: dict[str, int] = defaultdict(int)
    body_counts: dict[str, int] = defaultdict(int)
    for row in rows:
        seg_counts[row["segment"]] += 1
        body_counts[row["body_type"]] += 1
    seg_summary = ", ".join(f"{s}:{seg_counts[s]}" for s in sorted(seg_counts))
    body_summary = ", ".join(f"{b}:{body_counts[b]}" for b in sorted(body_counts))

    print(f"OK — car_models.csv ({n} rows; {len(models_per_make)}/100 makes covered)")
    print(f"     segments: {seg_summary}")
    print(f"     bodies:   {body_summary}")
    for w in warns:
        print(f"WARN: {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
