"""Checks for ``ml/data/processed/car_modifications.parquet`` (шаг 2.4).

Validates:
1. Schema — all required columns are present with the right pandas dtype.
2. Monotonic INT id starting at 1.
3. Every ``generation_id`` resolves to a row in ``car_generations.csv``.
4. Every generation has at least one modification (FK coverage).
5. Enum membership for ``fuel_type``, ``transmission``, ``drive``.
6. Range checks per schema (``04_database_schema.md`` §4.3.2):
   - ``engine_volume_l`` in [0.0, 8.5]; for EV/EREV exactly 0.0.
   - ``power_hp`` in [30, 900].
   - ``fuel_consumption_combined_l_100km`` in [3.0, 25.0] for ICE,
     exactly 0.0 for pure electrics, in [4.0, 12.0] for hybrids
     (EREV-style) with ``engine_volume_l == 0``.
7. Cross-rules: ``ELECTRIC`` ↔ ``engine_volume_l == 0`` and ``fc == 0``.
   ``HYBRID`` may have ``engine_volume_l == 0`` (EREV) but fc > 0.
8. Row count: in [200, 2000] (план §S2.4 §«план Б»: ≥200, верх — sanity).
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
GENS_CSV = REPO / "ml" / "data" / "seed" / "car_generations.csv"
PARQUET = REPO / "ml" / "data" / "processed" / "car_modifications.parquet"

REQUIRED_COLS = {
    "id", "generation_id", "trim_name",
    "engine_volume_l", "power_hp", "torque_nm",
    "fuel_type", "transmission", "drive",
    "fuel_consumption_combined_l_100km",
    "fuel_consumption_city_l_100km",
    "fuel_consumption_highway_l_100km",
    "length_mm", "width_mm", "height_mm",
    "curb_weight_kg", "seats", "msrp_new_rub",
}
FUELS = {"AI92", "AI95", "AI98", "AI100", "DIESEL", "LPG", "CNG", "ELECTRIC", "HYBRID"}
TRANS = {"MT", "AT", "CVT", "AMT", "DCT", "DIRECT"}
DRIVES = {"FWD", "RWD", "AWD", "4WD_PARTTIME"}


def main() -> int:
    errs: list[str] = []

    if not PARQUET.is_file():
        print("FAIL: missing", PARQUET)
        return 1
    if not GENS_CSV.is_file():
        print("FAIL: missing", GENS_CSV)
        return 1

    gen_ids: set[int] = set()
    with GENS_CSV.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            gen_ids.add(int(row["id"]))

    df = pd.read_parquet(PARQUET)
    n = len(df)

    missing = REQUIRED_COLS - set(df.columns)
    if missing:
        errs.append(f"missing columns: {sorted(missing)}")
    if not (200 <= n <= 2000):
        errs.append(f"row count: expected [200,2000], got {n}")

    ids = df["id"].tolist()
    expected = list(range(1, n + 1))
    if ids != expected:
        errs.append("id is not monotonic 1..n")

    gens_in_df = set(int(x) for x in df["generation_id"].tolist())
    unknown = gens_in_df - gen_ids
    if unknown:
        errs.append(f"unknown generation_id refs: {sorted(unknown)[:5]}...")
    uncovered = gen_ids - gens_in_df
    if uncovered:
        errs.append(
            f"generations without any modification: {sorted(uncovered)[:5]}... "
            f"(+{max(0, len(uncovered) - 5)} more)"
        )

    bad_fuel = sorted(set(df["fuel_type"]) - FUELS)
    if bad_fuel:
        errs.append(f"fuel_type values out of enum: {bad_fuel}")
    bad_tr = sorted(set(df["transmission"]) - TRANS)
    if bad_tr:
        errs.append(f"transmission values out of enum: {bad_tr}")
    bad_dr = sorted(set(df["drive"]) - DRIVES)
    if bad_dr:
        errs.append(f"drive values out of enum: {bad_dr}")

    for i, r in df.iterrows():
        line = i + 2
        ev = float(r["engine_volume_l"])
        hp = int(r["power_hp"])
        fc = float(r["fuel_consumption_combined_l_100km"])
        ft = r["fuel_type"]

        if not (0.0 <= ev <= 8.5):
            errs.append(f"row {line}: engine_volume_l {ev} out of [0,8.5]")
        if not (30 <= hp <= 900):
            errs.append(f"row {line}: power_hp {hp} out of [30,900]")

        if ft == "ELECTRIC":
            if ev != 0.0:
                errs.append(f"row {line}: ELECTRIC must have engine_volume_l=0, got {ev}")
            if fc != 0.0:
                errs.append(f"row {line}: ELECTRIC must have fc=0, got {fc}")
        elif ft == "HYBRID":
            if not (0.0 <= ev <= 6.5):
                errs.append(f"row {line}: HYBRID engine_volume_l {ev} out of [0,6.5]")
            if not (0.0 <= fc <= 12.0):
                errs.append(f"row {line}: HYBRID fc {fc} out of [0,12]")
        else:
            if not (0.6 <= ev <= 8.5):
                errs.append(f"row {line}: ICE engine_volume_l {ev} out of [0.6,8.5]")
            if not (3.0 <= fc <= 25.0):
                errs.append(f"row {line}: ICE fc {fc} out of [3,25]")

    if errs:
        print("FAIL")
        for e in errs[:40]:
            print(" ", e)
        if len(errs) > 40:
            print(f" ... +{len(errs) - 40} more")
        return 1

    fuel_counts: dict[str, int] = defaultdict(int)
    trans_counts: dict[str, int] = defaultdict(int)
    drive_counts: dict[str, int] = defaultdict(int)
    for ft in df["fuel_type"]:
        fuel_counts[ft] += 1
    for tr in df["transmission"]:
        trans_counts[tr] += 1
    for dr in df["drive"]:
        drive_counts[dr] += 1

    fc_summary = ", ".join(f"{k}:{v}" for k, v in sorted(fuel_counts.items()))
    tr_summary = ", ".join(f"{k}:{v}" for k, v in sorted(trans_counts.items()))
    dr_summary = ", ".join(f"{k}:{v}" for k, v in sorted(drive_counts.items()))

    print(
        f"OK — car_modifications.parquet ({n} rows; "
        f"{len(gens_in_df)}/{len(gen_ids)} generations covered)"
    )
    print(f"     fuel_type:    {fc_summary}")
    print(f"     transmission: {tr_summary}")
    print(f"     drive:        {dr_summary}")
    print(
        f"     hp range:     [{int(df['power_hp'].min())}..{int(df['power_hp'].max())}], "
        f"median={int(df['power_hp'].median())}"
    )
    print(
        f"     fc range:     [{df['fuel_consumption_combined_l_100km'].min():.1f}.."
        f"{df['fuel_consumption_combined_l_100km'].max():.1f}], "
        f"median={df['fuel_consumption_combined_l_100km'].median():.1f}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
