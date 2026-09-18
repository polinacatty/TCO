"""Checks for ``tire_sizes.csv`` (шаг 2.5).

Validates:
1. Schema (column names match exactly).
2. ``axle`` is one of ``front`` / ``rear`` / ``both``.
3. ``is_default`` is ``true`` / ``false`` (string lowercase).
4. ``size_code`` matches `WWW/AA RDD` regex; W in [125,355], aspect in
   [25,80], rim diameter in [13,24].
5. Every ``modification_id`` resolves to a row in
   ``car_modifications.parquet``.
6. Every modification is covered by at least one row.
7. PK uniqueness — ``(modification_id, axle, size_code)``.
8. Staggered rule — if a modification has ``axle == 'both'``, it must NOT
   also have ``axle == 'front'`` or ``axle == 'rear'`` (mutually exclusive).
9. Per-modification: at least one ``is_default == 'true'`` row.
"""

from __future__ import annotations

import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
MODS_PARQ = REPO / "ml" / "data" / "processed" / "car_modifications.parquet"
TIRES_CSV = REPO / "ml" / "data" / "seed" / "tire_sizes.csv"

REQUIRED_COLS = ["modification_id", "axle", "size_code", "is_default"]
AXLES = {"front", "rear", "both"}
BOOLS = {"true", "false"}
SIZE_RE = re.compile(r"^(\d{3})/(\d{2})\sR(\d{2})$")


def main() -> int:
    errs: list[str] = []

    if not TIRES_CSV.is_file():
        print("FAIL: missing", TIRES_CSV)
        return 1
    if not MODS_PARQ.is_file():
        print("FAIL: missing", MODS_PARQ)
        return 1

    mod_ids: set[int] = set(int(x) for x in pd.read_parquet(MODS_PARQ)["id"].tolist())

    with TIRES_CSV.open(encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        if r.fieldnames != REQUIRED_COLS:
            errs.append(f"columns: got {r.fieldnames}")
        rows = list(r)

    n = len(rows)
    if not (mod_ids and n >= len(mod_ids)):
        errs.append(f"row count {n} < modifications {len(mod_ids)} (every mod must have ≥1 row)")

    seen_pk: set[tuple[int, str, str]] = set()
    axles_per_mod: dict[int, set[str]] = defaultdict(set)
    defaults_per_mod: dict[int, int] = defaultdict(int)

    for i, row in enumerate(rows, start=2):
        try:
            mid = int(row["modification_id"])
        except ValueError:
            errs.append(f"line {i}: modification_id must be int, got {row['modification_id']!r}")
            continue
        if mid not in mod_ids:
            errs.append(f"line {i}: unknown modification_id {mid}")
            continue

        axle = row["axle"].strip()
        size = row["size_code"].strip()
        is_def = row["is_default"].strip()

        if axle not in AXLES:
            errs.append(f"line {i}: axle {axle!r} not in {sorted(AXLES)}")
        if is_def not in BOOLS:
            errs.append(f"line {i}: is_default {is_def!r} must be true/false")

        m = SIZE_RE.match(size)
        if not m:
            errs.append(f"line {i}: size_code {size!r} doesn't match WWW/AA RDD")
        else:
            w, aspect, rim = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if not (125 <= w <= 355):
                errs.append(f"line {i}: width {w} out of [125,355]")
            if not (25 <= aspect <= 80):
                errs.append(f"line {i}: aspect {aspect} out of [25,80]")
            if not (13 <= rim <= 24):
                errs.append(f"line {i}: rim {rim} out of [13,24]")

        pk = (mid, axle, size)
        if pk in seen_pk:
            errs.append(f"line {i}: duplicate PK (mod={mid}, axle={axle}, size={size})")
        seen_pk.add(pk)

        axles_per_mod[mid].add(axle)
        if is_def == "true":
            defaults_per_mod[mid] += 1

    for mid, axles in axles_per_mod.items():
        if "both" in axles and (axles & {"front", "rear"}):
            errs.append(f"modification_id {mid}: 'both' must be exclusive with front/rear")

    uncovered = sorted(mod_ids - set(axles_per_mod))
    if uncovered:
        errs.append(
            f"modifications without any tire row: {uncovered[:5]}"
            f" (+{max(0, len(uncovered) - 5)} more)"
        )

    no_defaults = sorted(mid for mid in axles_per_mod if defaults_per_mod[mid] == 0)
    if no_defaults:
        errs.append(
            f"modifications without a default tire: {no_defaults[:5]}"
            f" (+{max(0, len(no_defaults) - 5)} more)"
        )

    if errs:
        print("FAIL")
        for e in errs[:40]:
            print(" ", e)
        if len(errs) > 40:
            print(f" ... +{len(errs) - 40} more")
        return 1

    axle_counts: dict[str, int] = defaultdict(int)
    rim_counts: dict[int, int] = defaultdict(int)
    unique_sizes: set[str] = set()
    for row in rows:
        axle_counts[row["axle"]] += 1
        unique_sizes.add(row["size_code"])
        m = SIZE_RE.match(row["size_code"])
        if m:
            rim_counts[int(m.group(3))] += 1

    axle_summary = ", ".join(f"{k}:{v}" for k, v in sorted(axle_counts.items()))
    rim_summary = ", ".join(f"R{k}:{v}" for k, v in sorted(rim_counts.items()))

    print(f"OK — tire_sizes.csv ({n} rows; {len(axles_per_mod)}/{len(mod_ids)} modifications covered)")
    print(f"     axle:        {axle_summary}")
    print(f"     rim sizes:   {rim_summary}")
    print(f"     distinct size_codes: {len(unique_sizes)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
