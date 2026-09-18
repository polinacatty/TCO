"""Validator for ml/data/seed/car_segment_defaults.csv.

Checks:
1. Schema (columns + dtypes).
2. Uniqueness on (segment, body_type).
3. Range checks on each numeric column.
4. Plausibility: city_factor > 1.0 (city worse), highway_factor < 1.0 (highway better),
   except EV (we don't store EV here — EV is handled separately at enrichment time).
5. Monotonic ordering across segments (J_SUV is heaviest, A is lightest, etc.).
6. Source_note non-empty.
"""

import sys
from pathlib import Path
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "data" / "seed"

EXPECTED_COLUMNS = [
    "segment",
    "body_type",
    "seats",
    "length_mm",
    "width_mm",
    "height_mm",
    "curb_weight_kg",
    "cargo_volume_l",
    "body_clearance_mm",
    "city_factor",
    "highway_factor",
    "source_note",
]
ALLOWED_SEGMENTS = {
    "A", "B", "C", "D", "E", "F",
    "J_CROSS", "J_SUV", "LCV", "M_MPV", "S_SPORT",
}
ALLOWED_BODY_TYPES = {
    "sedan", "hatchback", "liftback", "wagon",
    "crossover", "suv", "coupe", "cabriolet", "mpv", "pickup",
}

RANGES = {
    "seats":            (2, 9),
    "length_mm":        (3000, 5800),
    "width_mm":         (1500, 2050),
    "height_mm":        (1200, 1950),
    "curb_weight_kg":   (700, 2800),
    "cargo_volume_l":   (150, 2000),
    "body_clearance_mm":(100, 280),
    "city_factor":      (1.10, 1.40),
    "highway_factor":   (0.75, 0.95),
}


def fail(msg: str) -> None:
    print(f"  FAIL  {msg}")
    sys.exit(1)


def ok(msg: str) -> None:
    print(f"  OK    {msg}")


def main() -> None:
    print("=" * 70)
    print("car_segment_defaults.csv — VALIDATION")
    print("=" * 70)

    p = SEED / "car_segment_defaults.csv"
    if not p.exists():
        fail(f"file not found: {p}")

    df = pd.read_csv(p)
    print(f"  loaded: {len(df)} rows, {len(df.columns)} columns")

    if list(df.columns) != EXPECTED_COLUMNS:
        fail(f"unexpected columns. Got {list(df.columns)}, expected {EXPECTED_COLUMNS}")
    ok("schema columns match")

    bad_seg = df[~df["segment"].isin(ALLOWED_SEGMENTS)]
    if len(bad_seg) > 0:
        fail(f"unknown segments: {bad_seg['segment'].unique().tolist()}")
    ok(f"segment in {sorted(ALLOWED_SEGMENTS)}")

    bad_body = df[~df["body_type"].isin(ALLOWED_BODY_TYPES)]
    if len(bad_body) > 0:
        fail(f"unknown body_types: {bad_body['body_type'].unique().tolist()}")
    ok(f"body_type in {sorted(ALLOWED_BODY_TYPES)}")

    dup = df[df.duplicated(["segment", "body_type"], keep=False)]
    if len(dup) > 0:
        fail(
            f"duplicate (segment, body_type) pairs: "
            f"{dup[['segment', 'body_type']].drop_duplicates().values.tolist()}"
        )
    ok(f"uniqueness on (segment, body_type) for all {len(df)} rows")

    for col, (lo, hi) in RANGES.items():
        oor = df[(df[col] < lo) | (df[col] > hi)]
        if len(oor) > 0:
            fail(
                f"{col} out of [{lo}, {hi}] in {len(oor)} rows: "
                f"{oor[['segment', 'body_type', col]].values.tolist()}"
            )
    ok(f"all numeric columns within plausible ranges")

    bad_cf = df[df["city_factor"] <= 1.0]
    if len(bad_cf) > 0:
        fail(
            f"city_factor must be > 1.0 (city is worse than combined): "
            f"{bad_cf[['segment', 'body_type', 'city_factor']].values.tolist()}"
        )
    ok("city_factor > 1.0 for all rows")

    bad_hf = df[df["highway_factor"] >= 1.0]
    if len(bad_hf) > 0:
        fail(
            f"highway_factor must be < 1.0 (highway is better than combined): "
            f"{bad_hf[['segment', 'body_type', 'highway_factor']].values.tolist()}"
        )
    ok("highway_factor < 1.0 for all rows")

    sedans = df[df["body_type"] == "sedan"].sort_values("segment")
    seg_order = ["A", "B", "C", "D", "E", "F"]
    sedan_present = sedans[sedans["segment"].isin(seg_order)].set_index("segment")
    for i in range(len(seg_order) - 1):
        a, b = seg_order[i], seg_order[i + 1]
        if a in sedan_present.index and b in sedan_present.index:
            la, lb = sedan_present.loc[a, "length_mm"], sedan_present.loc[b, "length_mm"]
            if la >= lb:
                fail(
                    f"sedan length monotonicity violated: {a}({la}mm) >= {b}({lb}mm)"
                )
    ok("sedan length monotonic across A < B < C < D < E < F")

    if "J_SUV" in df["segment"].values and "A" in df["segment"].values:
        max_suv = df[df["segment"] == "J_SUV"]["curb_weight_kg"].max()
        max_a = df[df["segment"] == "A"]["curb_weight_kg"].max()
        if max_suv <= max_a:
            fail(f"J_SUV weight ({max_suv}) should exceed A weight ({max_a})")
        ok(f"J_SUV weight ({max_suv} kg) > A weight ({max_a} kg)")

    if "J_SUV" in df["segment"].values and "S_SPORT" in df["segment"].values:
        max_suv = df[df["segment"] == "J_SUV"]["body_clearance_mm"].max()
        max_sport = df[df["segment"] == "S_SPORT"]["body_clearance_mm"].max()
        if max_suv <= max_sport:
            fail(f"J_SUV clearance ({max_suv}) should exceed S_SPORT ({max_sport})")
        ok(f"J_SUV clearance ({max_suv} mm) > S_SPORT clearance ({max_sport} mm)")

    empty_note = df[df["source_note"].fillna("").str.strip() == ""]
    if len(empty_note) > 0:
        fail(f"empty source_note in {len(empty_note)} rows")
    ok("every row has non-empty source_note")

    print()
    print(f"  Stats:")
    print(f"    rows:            {len(df)}")
    print(f"    unique segments: {df['segment'].nunique()}")
    print(f"    unique body_types: {df['body_type'].nunique()}")
    print(f"    length range:    {df['length_mm'].min()}–{df['length_mm'].max()} mm")
    print(f"    weight range:    {df['curb_weight_kg'].min()}–{df['curb_weight_kg'].max()} kg")
    print(f"    cargo range:     {df['cargo_volume_l'].min()}–{df['cargo_volume_l'].max()} L")
    print(f"    clearance range: {df['body_clearance_mm'].min()}–{df['body_clearance_mm'].max()} mm")

    print()
    print("=" * 70)
    print("OK  car_segment_defaults.csv passed all checks")
    print("=" * 70)


if __name__ == "__main__":
    main()
