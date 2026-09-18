"""Validator for ml/data/seed/car_reliability_seed.csv.

Checks:
1. Schema (columns + dtypes).
2. Range: reliability_score in [0.0, 1.0].
3. Uniqueness: per-make rows unique on make_name; fallback rows unique on (brand_tier, country).
4. FK: every per-make row references an existing make_name in car_makes.csv.
5. Coverage: every (brand_tier, country) pair appearing in car_makes.csv must be either
   - covered by per-make for ALL marks of that pair, OR
   - have a fallback row.
6. Lookup_type values consistency: 'make' rows have non-null make_name, 'fallback' rows have non-null brand_tier+country.
7. source_note non-empty (every row must be defensible).
"""

import sys
from pathlib import Path
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "data" / "seed"

EXPECTED_COLUMNS = [
    "lookup_type",
    "make_name",
    "brand_tier",
    "country",
    "reliability_score",
    "source_note",
    "notes",
]
ALLOWED_LOOKUP_TYPES = {"make", "fallback"}
ALLOWED_BRAND_TIERS = {"russian", "mass", "japanese_korean_mass", "chinese", "premium"}
SCORE_MIN = 0.0
SCORE_MAX = 1.0


def fail(msg: str) -> None:
    print(f"  FAIL  {msg}")
    sys.exit(1)


def ok(msg: str) -> None:
    print(f"  OK    {msg}")


def main() -> None:
    print("=" * 70)
    print("car_reliability_seed.csv — VALIDATION")
    print("=" * 70)

    rel_path = SEED / "car_reliability_seed.csv"
    if not rel_path.exists():
        fail(f"file not found: {rel_path}")

    df = pd.read_csv(rel_path)
    makes = pd.read_csv(SEED / "car_makes.csv")
    print(f"  loaded: {len(df)} rows, {len(df.columns)} columns")

    # 1. Schema
    if list(df.columns) != EXPECTED_COLUMNS:
        fail(
            f"unexpected columns. Got {list(df.columns)}, expected {EXPECTED_COLUMNS}"
        )
    ok("schema columns match")

    # 2. Range
    out_of_range = df[
        (df["reliability_score"] < SCORE_MIN) | (df["reliability_score"] > SCORE_MAX)
    ]
    if len(out_of_range) > 0:
        fail(
            f"reliability_score out of [{SCORE_MIN}, {SCORE_MAX}] in {len(out_of_range)} rows"
        )
    ok(f"reliability_score in [{SCORE_MIN}, {SCORE_MAX}] for all rows")

    # 3. Lookup_type consistency
    bad_lt = df[~df["lookup_type"].isin(ALLOWED_LOOKUP_TYPES)]
    if len(bad_lt) > 0:
        fail(f"unknown lookup_type values: {bad_lt['lookup_type'].unique().tolist()}")
    ok(f"lookup_type values in {ALLOWED_LOOKUP_TYPES}")

    per_make = df[df["lookup_type"] == "make"]
    fallback = df[df["lookup_type"] == "fallback"]

    if per_make["make_name"].isna().any():
        fail("per-make rows have NULL make_name")
    if per_make[["brand_tier", "country"]].notna().any().any():
        fail("per-make rows must have NULL brand_tier and country")
    ok(
        f"per-make rows ({len(per_make)}): make_name set, brand_tier/country empty"
    )

    if fallback[["brand_tier", "country"]].isna().any().any():
        fail("fallback rows have NULL brand_tier or country")
    if fallback["make_name"].notna().any():
        fail("fallback rows must have NULL make_name")
    ok(f"fallback rows ({len(fallback)}): brand_tier+country set, make_name empty")

    bad_tiers = fallback[~fallback["brand_tier"].isin(ALLOWED_BRAND_TIERS)]
    if len(bad_tiers) > 0:
        fail(f"unknown brand_tier values: {bad_tiers['brand_tier'].unique().tolist()}")
    ok(f"fallback brand_tier in {ALLOWED_BRAND_TIERS}")

    # 4. Uniqueness
    dup_makes = per_make[per_make.duplicated("make_name", keep=False)]
    if len(dup_makes) > 0:
        fail(
            f"duplicate per-make: {dup_makes['make_name'].unique().tolist()}"
        )
    ok(f"per-make uniqueness ({per_make['make_name'].nunique()} unique marks)")

    dup_fallback = fallback[
        fallback.duplicated(["brand_tier", "country"], keep=False)
    ]
    if len(dup_fallback) > 0:
        fail(
            f"duplicate fallback (brand_tier, country): "
            f"{dup_fallback[['brand_tier', 'country']].drop_duplicates().values.tolist()}"
        )
    ok(
        f"fallback uniqueness ({len(fallback)} unique (brand_tier, country) pairs)"
    )

    # 5. FK: per-make refers to existing make_name
    makes_set = set(makes["name"].tolist())
    bad_fk = per_make[~per_make["make_name"].isin(makes_set)]
    if len(bad_fk) > 0:
        fail(
            f"per-make refers to unknown make_name: {bad_fk['make_name'].tolist()}"
        )
    ok(f"per-make FK to car_makes.name verified ({len(per_make)} rows)")

    # 6. Coverage check: each (brand_tier, country) pair in car_makes must be
    #    either fully covered by per-make rows OR have a fallback row.
    pair_to_makes = (
        makes.groupby(["brand_tier", "country"])["name"].apply(set).to_dict()
    )
    covered_makes = set(per_make["make_name"].tolist())
    fallback_pairs = {
        (row["brand_tier"], row["country"]) for _, row in fallback.iterrows()
    }

    uncovered = []
    for (tier, country), marks in pair_to_makes.items():
        marks_uncovered = marks - covered_makes
        if marks_uncovered and (tier, country) not in fallback_pairs:
            uncovered.append((tier, country, sorted(marks_uncovered)))

    if uncovered:
        msg = "; ".join(
            f"{t}/{c}: missing fallback for {marks}" for t, c, marks in uncovered
        )
        fail(f"coverage gaps (no per-make + no fallback): {msg}")
    ok(
        f"coverage complete: every (brand_tier, country) is covered by per-make or fallback"
    )

    # 7. source_note non-empty
    empty_note = df[df["source_note"].fillna("").str.strip() == ""]
    if len(empty_note) > 0:
        fail(f"empty source_note in {len(empty_note)} rows")
    ok("every row has non-empty source_note")

    # Summary statistics
    print()
    print(f"  Stats:")
    print(f"    per-make rows:  {len(per_make)} (covers {per_make['make_name'].nunique()} marks)")
    print(f"    fallback rows:  {len(fallback)} (covers {len(fallback)} (tier, country) pairs)")
    print(f"    score range:    [{df['reliability_score'].min():.2f}, {df['reliability_score'].max():.2f}]")
    print(f"    score mean:     {df['reliability_score'].mean():.3f}")
    print(f"    score median:   {df['reliability_score'].median():.3f}")
    print()

    # Coverage report
    total_makes = len(makes)
    direct_covered = per_make["make_name"].nunique()
    fallback_covered = total_makes - direct_covered
    print(
        f"  Caverage: {direct_covered}/{total_makes} marks via per-make ({direct_covered/total_makes*100:.1f}%), "
        f"{fallback_covered} via fallback ({fallback_covered/total_makes*100:.1f}%)"
    )

    print()
    print("=" * 70)
    print("OK  car_reliability_seed.csv passed all checks")
    print("=" * 70)


if __name__ == "__main__":
    main()
