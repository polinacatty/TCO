"""Structural checks for ``transport_tax_rates.csv`` (Sprint 1, step 1.4)."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
SEED = REPO_ROOT / "ml" / "data" / "seed"
TAX_CSV = SEED / "transport_tax_rates.csv"
REGIONS = SEED / "regions.csv"

REQUIRED_RIDS = {0, 1, 2, 19, 20, 33, 36, 45, 48, 60, 63}
HP_ROWS = [
    (1, 100),
    (101, 150),
    (151, 200),
    (201, 250),
    (251, None),
]


def main() -> int:
    df = pd.read_csv(TAX_CSV, dtype={"region_id": "Int64"}, keep_default_na=True)
    df["hp_max"] = pd.to_numeric(df["hp_max"], errors="coerce")

    errs: list[str] = []

    need_cols = {
        "region_id",
        "hp_min",
        "hp_max",
        "rate_rub_per_hp",
    }
    if set(df.columns) != need_cols:
        errs.append(f"columns: expected {sorted(need_cols)}, got {list(df.columns)}")

    if len(df) != 55:
        errs.append(f"row count: expected 55, got {len(df)}")

    by = df.groupby("region_id", sort=True)
    for rid, g in by:
        if int(rid) not in REQUIRED_RIDS:
            errs.append(f"unexpected region_id {rid}")
        if len(g) != 5:
            errs.append(f"region {rid}: expected 5 power bands, got {len(g)}")

    for rid in REQUIRED_RIDS:
        g = df[df["region_id"] == rid].sort_values("hp_min")
        for i, ((hmin, hmax), r) in enumerate(zip(HP_ROWS, g.itertuples(), strict=True)):
            if int(r.hp_min) != hmin:
                errs.append(f"r{rid} row{i}: hp_min {r.hp_min} != {hmin}")
            if hmax is None and pd.notna(r.hp_max):
                errs.append(f"r{rid} last band: hp_max should be null")
            if hmax is not None and (pd.isna(r.hp_max) or int(r.hp_max) != hmax):
                errs.append(f"r{rid} row{i}: hp_max {r.hp_max} != {hmax}")

    reg = pd.read_csv(REGIONS)
    valid = set(reg["id"].tolist())
    for rid in REQUIRED_RIDS:
        if rid == 0:
            continue
        if rid not in valid:
            errs.append(f"region_id {rid} not in regions.csv")

    for _, r in df.iterrows():
        rate = float(r["rate_rub_per_hp"])
        if rate <= 0 or rate > 200:
            errs.append(f"rate out of (0,200] for region {r['region_id']} hp_min={r['hp_min']}: {rate}")
        rid = int(r["region_id"])
        if rid == 0 and rate not in (2.5, 3.5, 5.0, 7.5, 15.0):
            errs.append(f"unexpected federal (НК) rate {rate}")

    # non-decreasing rates within each region (TCO default bands)
    for rid in sorted(REQUIRED_RIDS):
        g = df[df["region_id"] == rid].sort_values("hp_min")
        rates = g["rate_rub_per_hp"].astype(float).tolist()
        if rates != sorted(rates):
            errs.append(f"region {rid}: rates not non-decreasing: {rates}")

    if errs:
        print("FAIL")
        for e in errs:
            print(" ", e)
        return 1
    print("OK — transport_tax_rates.csv (55 rows, 11 region blocks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
