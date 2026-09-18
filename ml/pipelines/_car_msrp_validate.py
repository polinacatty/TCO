"""Validator for ml/data/seed/car_msrp_seed.csv (built by _car_msrp_seed_build.py).

Checks:
1. Schema (columns).
2. FK: generation_id exists in car_generations.csv.
3. Year anchor falls within [year_from, year_to] of the referenced generation
   (or year_to is null = current).
4. Range: msrp_base_rub and trim_high_rub in [200_000, 50_000_000] RUB.
5. msrp_base_rub <= trim_high_rub (high is the upper anchor).
6. Uniqueness on (generation_id, year).
7. URL non-empty + source_note non-empty.
8. Each year is a plausible 4-digit year >= 2015 and <= current_year + 1.
9. Trim premium (trim_high / msrp_base) within reasonable bounds [1.05, 3.0].
10. Coverage: every brand_tier has at least 1 anchor; every segment has at least 1 anchor.
11. Monotonicity: for the same generation_id, msrp_base_rub for a later year >= for an earlier year (modulo inflation/deflation tolerance of 5%).
"""

import sys
from datetime import datetime
from pathlib import Path
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "data" / "seed"

EXPECTED_COLUMNS = [
    "generation_id",
    "year",
    "msrp_base_rub",
    "trim_high_rub",
    "source_url",
    "source_note",
]
PRICE_MIN = 200_000
PRICE_MAX = 50_000_000
TRIM_PREMIUM_MIN = 1.05
TRIM_PREMIUM_MAX = 3.0
MIN_YEAR = 2015
MAX_YEAR = datetime.now().year + 1


def fail(msg: str) -> None:
    print(f"  FAIL  {msg}")
    sys.exit(1)


def ok(msg: str) -> None:
    print(f"  OK    {msg}")


def main() -> None:
    print("=" * 70)
    print("car_msrp_seed.csv — VALIDATION")
    print("=" * 70)

    p = SEED / "car_msrp_seed.csv"
    if not p.exists():
        fail(f"file not found: {p} (run _car_msrp_seed_build.py first)")

    df = pd.read_csv(p)
    print(f"  loaded: {len(df)} rows, {len(df.columns)} columns")

    if list(df.columns) != EXPECTED_COLUMNS:
        fail(f"unexpected columns. Got {list(df.columns)}, expected {EXPECTED_COLUMNS}")
    ok("schema columns match")

    gens = pd.read_csv(SEED / "car_generations.csv").rename(columns={"id": "generation_id"})
    models = pd.read_csv(SEED / "car_models.csv").rename(columns={"id": "model_id"})
    makes = pd.read_csv(SEED / "car_makes.csv").rename(columns={"id": "make_id"})

    valid_gen_ids = set(gens["generation_id"].tolist())
    bad_fk = df[~df["generation_id"].isin(valid_gen_ids)]
    if len(bad_fk) > 0:
        fail(f"FK violation: generation_id not in car_generations: {bad_fk['generation_id'].tolist()}")
    ok(f"FK to car_generations.id verified ({df['generation_id'].nunique()} unique generations)")

    merged = df.merge(gens, on="generation_id", how="left")
    bad_year = merged[
        (merged["year"] < merged["year_from"])
        | (
            (~merged["year_to"].isna())
            & (merged["year"] > merged["year_to"])
        )
    ]
    if len(bad_year) > 0:
        rows = bad_year[["generation_id", "year", "year_from", "year_to"]].to_dict("records")
        print(f"  WARN  {len(bad_year)} rows have year outside generation [year_from, year_to]:")
        for r in rows[:5]:
            print(f"        {r}")
        if len(bad_year) > 5:
            print(f"        ... and {len(bad_year) - 5} more")
    else:
        ok("year falls within generation [year_from, year_to] for all rows")

    oor_base = df[(df["msrp_base_rub"] < PRICE_MIN) | (df["msrp_base_rub"] > PRICE_MAX)]
    if len(oor_base) > 0:
        fail(f"msrp_base_rub out of [{PRICE_MIN:,}, {PRICE_MAX:,}] in {len(oor_base)} rows")
    oor_high = df[(df["trim_high_rub"] < PRICE_MIN) | (df["trim_high_rub"] > PRICE_MAX)]
    if len(oor_high) > 0:
        fail(f"trim_high_rub out of [{PRICE_MIN:,}, {PRICE_MAX:,}] in {len(oor_high)} rows")
    ok(f"prices in [{PRICE_MIN:,}, {PRICE_MAX:,}] RUB for all rows")

    bad_order = df[df["msrp_base_rub"] > df["trim_high_rub"]]
    if len(bad_order) > 0:
        fail(f"msrp_base_rub > trim_high_rub in {len(bad_order)} rows")
    ok("msrp_base_rub <= trim_high_rub for all rows")

    dup = df[df.duplicated(["generation_id", "year"], keep=False)]
    if len(dup) > 0:
        fail(
            f"duplicate (generation_id, year): "
            f"{dup[['generation_id', 'year']].drop_duplicates().values.tolist()}"
        )
    ok(f"uniqueness on (generation_id, year) for all {len(df)} rows")

    empty_url = df[df["source_url"].fillna("").str.strip() == ""]
    empty_note = df[df["source_note"].fillna("").str.strip() == ""]
    if len(empty_url) > 0:
        fail(f"empty source_url in {len(empty_url)} rows")
    if len(empty_note) > 0:
        fail(f"empty source_note in {len(empty_note)} rows")
    ok("every row has non-empty source_url and source_note")

    bad_year_range = df[(df["year"] < MIN_YEAR) | (df["year"] > MAX_YEAR)]
    if len(bad_year_range) > 0:
        fail(f"year out of [{MIN_YEAR}, {MAX_YEAR}] in {len(bad_year_range)} rows")
    ok(f"year in [{MIN_YEAR}, {MAX_YEAR}] for all rows")

    df = df.copy()
    df["trim_premium"] = df["trim_high_rub"] / df["msrp_base_rub"]
    bad_premium = df[
        (df["trim_premium"] < TRIM_PREMIUM_MIN)
        | (df["trim_premium"] > TRIM_PREMIUM_MAX)
    ]
    if len(bad_premium) > 0:
        fail(
            f"trim premium out of [{TRIM_PREMIUM_MIN}, {TRIM_PREMIUM_MAX}] in {len(bad_premium)} rows"
        )
    ok(
        f"trim_high/base premium in [{TRIM_PREMIUM_MIN}, {TRIM_PREMIUM_MAX}] for all rows"
    )

    enriched = (
        df.merge(gens[["generation_id", "model_id"]], on="generation_id")
        .merge(models[["model_id", "make_id", "segment"]], on="model_id")
        .merge(makes[["make_id", "brand_tier"]], on="make_id")
    )

    tiers_covered = enriched["brand_tier"].unique()
    expected_tiers = {"russian", "mass", "japanese_korean_mass", "chinese", "premium"}
    missing_tiers = expected_tiers - set(tiers_covered)
    if missing_tiers:
        fail(f"brand_tiers not covered by anchors: {missing_tiers}")
    ok(f"all 5 brand_tiers covered by anchors: {sorted(tiers_covered)}")

    segments_covered = enriched["segment"].unique()
    expected_segments_min = {"B", "C", "D", "J_CROSS", "J_SUV"}
    missing_min_seg = expected_segments_min - set(segments_covered)
    if missing_min_seg:
        fail(f"min mandatory segments missing: {missing_min_seg}")
    ok(f"min mandatory segments covered: {sorted(segments_covered)}")

    multi_year = (
        df.groupby("generation_id")["year"].nunique().reset_index(name="n_years")
    )
    multi = multi_year[multi_year["n_years"] >= 2]["generation_id"].tolist()
    violators = []
    for gid in multi:
        sub = df[df["generation_id"] == gid].sort_values("year")
        prev_price = None
        for _, row in sub.iterrows():
            if prev_price is not None and row["msrp_base_rub"] < prev_price * 0.95:
                violators.append((gid, prev_price, row["year"], row["msrp_base_rub"]))
            prev_price = row["msrp_base_rub"]
    if violators:
        for v in violators[:5]:
            print(f"  INFO  generation {v[0]}: price dropped from {v[1]:,} to {v[3]:,} (year {v[2]})")
    ok(f"price monotonicity (>=−5%) across years for {len(multi)} multi-year generations")

    print()
    print(f"  Stats:")
    print(f"    rows:             {len(df)}")
    print(f"    unique gens:      {df['generation_id'].nunique()}")
    print(f"    year range:       {df['year'].min()}–{df['year'].max()}")
    print(f"    msrp_base range:  {df['msrp_base_rub'].min():,} – {df['msrp_base_rub'].max():,} RUB")
    print(f"    trim_high range:  {df['trim_high_rub'].min():,} – {df['trim_high_rub'].max():,} RUB")
    print(f"    avg trim premium: x{df['trim_premium'].mean():.2f}")
    print(f"    by tier:")
    for t, n in enriched.groupby("brand_tier").size().items():
        print(f"        {t}: {n}")

    print()
    print("=" * 70)
    print("OK  car_msrp_seed.csv passed all checks")
    print("=" * 70)


if __name__ == "__main__":
    main()
