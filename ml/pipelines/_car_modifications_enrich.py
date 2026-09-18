"""S4.0: enrich car_modifications.parquet with msrp / reliability / segment defaults.

This is the second (post-build) stage of car_modifications pipeline.
The first stage (`_car_modifications_build.py`) produces base specifications
(power_hp, fuel_type, drive, transmission, ...) from segment defaults +
overrides. This script then fills in the market-driven NULL fields:

    1) msrp_new_rub          — from car_msrp_seed.csv + parametric fallback
    2) reliability_score     — from car_reliability_seed.csv (per-make + fallback)
    3) seats, length_mm, width_mm, height_mm, curb_weight_kg,
       cargo_volume_l, body_clearance_mm,
       fuel_consumption_city_l_100km, fuel_consumption_highway_l_100km
                              — from car_segment_defaults.csv

Audit columns (kept in parquet for reproducibility, dropped before DB load):
    msrp_source ∈ {'seed_exact', 'seed_interpolated', 'fallback_param'}
    reliability_source ∈ {'per_make', 'tier_country_fallback'}
    enriched_at — UTC timestamp

Methodology: see docs/04_ml_models/04_catalog_completion_methodology.md
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "data" / "seed"
PROC = ROOT / "data" / "processed"


TARGET_YEAR = 2024
INFLATION_RATE = 0.08
EV_PREMIUM = 1.50

BASE_MSRP_2024 = {
    ("A", "russian"):                 700_000,
    ("A", "mass"):                  1_400_000,
    ("A", "japanese_korean_mass"):  1_700_000,
    ("A", "chinese"):               1_500_000,
    ("B", "russian"):               1_000_000,
    ("B", "mass"):                  1_700_000,
    ("B", "japanese_korean_mass"):  2_000_000,
    ("B", "chinese"):               1_800_000,
    ("B", "premium"):               3_500_000,
    ("C", "russian"):               1_400_000,
    ("C", "mass"):                  2_200_000,
    ("C", "japanese_korean_mass"):  2_500_000,
    ("C", "chinese"):               2_300_000,
    ("C", "premium"):               4_500_000,
    ("D", "russian"):               1_800_000,
    ("D", "mass"):                  3_000_000,
    ("D", "japanese_korean_mass"):  3_500_000,
    ("D", "chinese"):               3_000_000,
    ("D", "premium"):               6_500_000,
    ("E", "mass"):                  3_800_000,
    ("E", "japanese_korean_mass"):  4_500_000,
    ("E", "chinese"):               4_500_000,
    ("E", "premium"):               9_000_000,
    ("F", "russian"):               4_500_000,
    ("F", "japanese_korean_mass"):  6_500_000,
    ("F", "chinese"):               7_000_000,
    ("F", "premium"):              14_000_000,
    ("J_CROSS", "russian"):         1_600_000,
    ("J_CROSS", "mass"):            2_800_000,
    ("J_CROSS", "japanese_korean_mass"): 3_000_000,
    ("J_CROSS", "chinese"):         2_500_000,
    ("J_CROSS", "premium"):         7_000_000,
    ("J_SUV", "russian"):           2_500_000,
    ("J_SUV", "mass"):              4_500_000,
    ("J_SUV", "japanese_korean_mass"): 5_500_000,
    ("J_SUV", "chinese"):           3_800_000,
    ("J_SUV", "premium"):          12_000_000,
    ("LCV", "russian"):             1_700_000,
    ("LCV", "mass"):                2_500_000,
    ("LCV", "japanese_korean_mass"): 2_800_000,
    ("LCV", "chinese"):             2_300_000,
    ("LCV", "premium"):             8_000_000,
    ("M_MPV", "russian"):           1_800_000,
    ("M_MPV", "mass"):              3_200_000,
    ("M_MPV", "japanese_korean_mass"): 3_800_000,
    ("M_MPV", "chinese"):           2_800_000,
    ("M_MPV", "premium"):           8_000_000,
    ("S_SPORT", "mass"):            4_500_000,
    ("S_SPORT", "japanese_korean_mass"): 5_500_000,
    ("S_SPORT", "premium"):        18_000_000,
}

COUNTRY_FACTOR = {
    "Russia":           1.00,
    "China":            1.00,
    "Japan":            1.05,
    "South Korea":      1.05,
    "Germany":          1.10,
    "United Kingdom":   1.10,
    "USA":              1.10,
    "Italy":            1.05,
    "France":           1.05,
    "Sweden":           1.05,
    "Czech Republic":   1.05,
    "Spain":            1.05,
    "Romania":          1.00,
}

DRIVE_PREMIUM = {
    "FWD":          1.00,
    "RWD":          1.05,
    "4WD_PARTTIME": 1.07,
    "AWD":          1.10,
}

TRANS_PREMIUM = {
    "MT":     0.92,
    "AT":     1.00,
    "CVT":    0.97,
    "DCT":    1.05,
    "DIRECT": 1.00,
}


def fail(msg: str) -> None:
    print(f"  FAIL  {msg}")
    sys.exit(1)


def ok(msg: str) -> None:
    print(f"  OK    {msg}")


def info(msg: str) -> None:
    print(f"  INFO  {msg}")


def load_inputs():
    print("=" * 70)
    print("Loading inputs")
    print("=" * 70)

    mods = pd.read_parquet(PROC / "car_modifications.parquet").rename(
        columns={"id": "modification_id"}
    )
    makes = pd.read_csv(SEED / "car_makes.csv").rename(
        columns={"id": "make_id", "name": "make_name"}
    )
    models = pd.read_csv(SEED / "car_models.csv").rename(
        columns={"id": "model_id", "name": "model_name"}
    )
    gens = pd.read_csv(SEED / "car_generations.csv").rename(
        columns={"id": "generation_id"}
    )
    msrp_seed = pd.read_csv(SEED / "car_msrp_seed.csv")
    rel_seed = pd.read_csv(SEED / "car_reliability_seed.csv")
    seg_defaults = pd.read_csv(SEED / "car_segment_defaults.csv")

    info(f"car_modifications:  {len(mods)} rows")
    info(f"car_makes:          {len(makes)} rows")
    info(f"car_models:         {len(models)} rows")
    info(f"car_generations:    {len(gens)} rows")
    info(f"car_msrp_seed:      {len(msrp_seed)} rows ({msrp_seed['generation_id'].nunique()} gens)")
    info(f"car_reliability:    {len(rel_seed)} rows")
    info(f"car_segment_defs:   {len(seg_defaults)} rows")

    return mods, makes, models, gens, msrp_seed, rel_seed, seg_defaults


def fallback_msrp(seg: str, tier: str, country: str, target_year: int) -> float:
    """Parametric fallback: BASE_MSRP_2024[seg, tier] * (1+infl)^(year-2024) * country_factor."""
    base = BASE_MSRP_2024.get((seg, tier))
    if base is None:
        return float("nan")
    infl = (1 + INFLATION_RATE) ** (target_year - 2024)
    cf = COUNTRY_FACTOR.get(country, 1.00)
    return base * infl * cf


def trim_factor(power_hp, base_power_hp, high_power_hp, base_msrp, high_msrp):
    """Linear interpolation by power_hp within [base, high]."""
    if pd.isna(power_hp) or pd.isna(base_power_hp) or pd.isna(high_power_hp):
        return 1.0
    if high_power_hp == base_power_hp:
        return 1.0
    alpha = (power_hp - base_power_hp) / (high_power_hp - base_power_hp)
    alpha = max(0.0, min(1.0, alpha))
    return 1.0 + alpha * (high_msrp / base_msrp - 1)


def enrich_msrp(df, msrp_seed, target_year):
    """Compute msrp_new_rub for each modification + audit column msrp_source."""
    print()
    print("=" * 70)
    print("Computing msrp_new_rub")
    print("=" * 70)

    pwr_per_gen = (
        df.groupby("generation_id")["power_hp"]
        .agg(["min", "max"])
        .rename(columns={"min": "gen_min_power", "max": "gen_max_power"})
        .reset_index()
    )
    df = df.merge(pwr_per_gen, on="generation_id", how="left")

    df["target_year"] = target_year

    seed_picks = []
    for gen_id, group in msrp_seed.groupby("generation_id"):
        diffs = (group["year"] - target_year).abs()
        pick_idx = diffs.idxmin()
        seed_picks.append(group.loc[pick_idx])
    closest_seed = pd.DataFrame(seed_picks)
    closest_seed = closest_seed[
        ["generation_id", "year", "msrp_base_rub", "trim_high_rub"]
    ].rename(columns={"year": "seed_year"})

    df = df.merge(closest_seed, on="generation_id", how="left")

    has_seed = df["msrp_base_rub"].notna()

    df["trim_factor"] = df.apply(
        lambda r: trim_factor(
            r["power_hp"], r["gen_min_power"], r["gen_max_power"],
            r["msrp_base_rub"], r["trim_high_rub"],
        ) if has_seed.loc[r.name] else 1.0,
        axis=1,
    )

    seed_msrp = df["msrp_base_rub"] * df["trim_factor"]

    fallback_msrp_arr = df.apply(
        lambda r: fallback_msrp(
            r["segment"], r["brand_tier"], r["country"], target_year
        ),
        axis=1,
    )

    drive_mult = df["drive"].map(DRIVE_PREMIUM).fillna(1.0)
    trans_mult = df["transmission"].map(TRANS_PREMIUM).fillna(1.0)
    fallback_msrp_arr = fallback_msrp_arr * drive_mult * trans_mult

    is_ev = df["fuel_type"] == "ELECTRIC"
    fallback_msrp_arr = fallback_msrp_arr * np.where(is_ev, EV_PREMIUM, 1.0)

    final = np.where(has_seed, seed_msrp, fallback_msrp_arr)

    same_year = df["seed_year"] == target_year
    msrp_source = np.select(
        [
            has_seed & same_year,
            has_seed & ~same_year,
            ~has_seed,
        ],
        ["seed_exact", "seed_interpolated", "fallback_param"],
        default="unknown",
    )

    df["msrp_new_rub"] = pd.Series(final).round(-3).astype("Int64")
    df["msrp_source"] = msrp_source

    df = df.drop(
        columns=[
            "msrp_base_rub", "trim_high_rub", "seed_year",
            "gen_min_power", "gen_max_power", "trim_factor", "target_year",
        ]
    )

    n_seed_exact = (msrp_source == "seed_exact").sum()
    n_seed_interp = (msrp_source == "seed_interpolated").sum()
    n_fallback = (msrp_source == "fallback_param").sum()
    n_unknown = df["msrp_new_rub"].isna().sum()

    info(f"msrp_source:")
    info(f"   seed_exact:        {n_seed_exact} ({n_seed_exact*100/len(df):.1f}%)")
    info(f"   seed_interpolated: {n_seed_interp} ({n_seed_interp*100/len(df):.1f}%)")
    info(f"   fallback_param:    {n_fallback} ({n_fallback*100/len(df):.1f}%)")
    info(f"   unresolved (NaN):  {n_unknown}")
    info(f"msrp range: {df['msrp_new_rub'].min():,} – {df['msrp_new_rub'].max():,} RUB")
    info(f"msrp median: {int(df['msrp_new_rub'].median()):,} RUB")

    if n_unknown > 0:
        unresolved = df[df["msrp_new_rub"].isna()]
        info(f"unresolved (segment, brand_tier, country) combinations:")
        for combo, n in unresolved.groupby(["segment", "brand_tier", "country"]).size().items():
            info(f"   {combo}: {n} mods")

    return df


def enrich_reliability(df, rel_seed):
    print()
    print("=" * 70)
    print("Computing reliability_score")
    print("=" * 70)

    per_make = rel_seed[rel_seed["lookup_type"] == "make"][
        ["make_name", "reliability_score"]
    ].rename(columns={"reliability_score": "rel_per_make"})

    fallback = rel_seed[rel_seed["lookup_type"] == "fallback"][
        ["brand_tier", "country", "reliability_score"]
    ].rename(columns={"reliability_score": "rel_fallback"})

    df = df.merge(per_make, on="make_name", how="left")
    df = df.merge(fallback, on=["brand_tier", "country"], how="left")

    df["reliability_score"] = df["rel_per_make"].combine_first(df["rel_fallback"])
    df["reliability_source"] = np.where(
        df["rel_per_make"].notna(), "per_make", "tier_country_fallback"
    )

    n_per_make = (df["reliability_source"] == "per_make").sum()
    n_fallback = (df["reliability_source"] == "tier_country_fallback").sum()
    n_null = df["reliability_score"].isna().sum()
    info(f"reliability_source:")
    info(f"   per_make:              {n_per_make} ({n_per_make*100/len(df):.1f}%)")
    info(f"   tier_country_fallback: {n_fallback} ({n_fallback*100/len(df):.1f}%)")
    info(f"   unresolved (NaN):      {n_null}")
    info(f"reliability range: [{df['reliability_score'].min():.2f}, {df['reliability_score'].max():.2f}]")

    df = df.drop(columns=["rel_per_make", "rel_fallback"])
    return df


def enrich_segment_defaults(df, seg_defaults):
    print()
    print("=" * 70)
    print("Filling segment defaults")
    print("=" * 70)

    df = df.merge(
        seg_defaults.drop(columns=["source_note"]),
        on=["segment", "body_type"],
        how="left",
        suffixes=("", "_default"),
    )

    no_match = df["seats_default"].isna()
    if no_match.any():
        info(f"WARN: {no_match.sum()} mods have (segment, body_type) without segment_defaults match")
        for combo, n in df[no_match].groupby(["segment", "body_type"]).size().items():
            info(f"   {combo}: {n} mods (will use segment-only median)")

        seg_only = (
            seg_defaults.groupby("segment").median(numeric_only=True).reset_index()
        )
        for col in ["seats", "length_mm", "width_mm", "height_mm",
                    "curb_weight_kg", "cargo_volume_l", "body_clearance_mm",
                    "city_factor", "highway_factor"]:
            seg_only_col = seg_only.set_index("segment")[col]
            target_col = f"{col}_default" if f"{col}_default" in df.columns else col
            df.loc[no_match, target_col] = df.loc[no_match, "segment"].map(seg_only_col)

    target_cols = [
        "seats", "length_mm", "width_mm", "height_mm",
        "curb_weight_kg", "cargo_volume_l", "body_clearance_mm",
    ]

    for col in target_cols:
        default_col = f"{col}_default"
        if default_col in df.columns:
            before_null = df[col].isna().sum()
            df[col] = df[col].fillna(df[default_col])
            after_null = df[col].isna().sum()
            info(f"  {col}: {before_null - after_null} NULLs filled, {after_null} remain")
        else:
            after_null = df[col].isna().sum() if col in df.columns else "n/a"
            info(f"  {col}: no _default suffix (col added by merge), {after_null} NULLs")

    base_combined = df["fuel_consumption_combined_l_100km"]

    is_ev = df["fuel_type"] == "ELECTRIC"
    city_factor_eff = np.where(is_ev, 0.85, df["city_factor"])
    highway_factor_eff = np.where(is_ev, 1.10, df["highway_factor"])

    df["fuel_consumption_city_l_100km"] = (
        df["fuel_consumption_city_l_100km"]
        .fillna((base_combined * pd.Series(city_factor_eff, index=df.index)).round(1))
    )
    df["fuel_consumption_highway_l_100km"] = (
        df["fuel_consumption_highway_l_100km"]
        .fillna((base_combined * pd.Series(highway_factor_eff, index=df.index)).round(1))
    )

    info(f"  fuel_consumption_city/highway: filled from combined × factors")

    drop_defaults = [c for c in df.columns if c.endswith("_default")]
    df = df.drop(columns=drop_defaults + ["city_factor", "highway_factor"])

    return df


def main():
    mods, makes, models, gens, msrp_seed, rel_seed, seg_defaults = load_inputs()

    df = (
        mods.merge(gens[["generation_id", "model_id"]], on="generation_id", how="left")
        .merge(
            models[["model_id", "make_id", "segment", "body_type"]],
            on="model_id",
            how="left",
        )
        .merge(
            makes[["make_id", "make_name", "brand_tier", "country"]],
            on="make_id",
            how="left",
        )
    )

    if df["segment"].isna().any():
        fail("some mods cannot resolve segment after JOIN — broken FKs")

    if "msrp_new_rub" in df.columns:
        df = df.drop(columns=["msrp_new_rub"])

    df = enrich_msrp(df, msrp_seed, TARGET_YEAR)
    df = enrich_reliability(df, rel_seed)
    df = enrich_segment_defaults(df, seg_defaults)

    df["enriched_at"] = datetime.now(timezone.utc).isoformat()

    base_columns = [
        "modification_id", "generation_id", "trim_name",
        "engine_volume_l", "power_hp", "torque_nm",
        "fuel_type", "transmission", "drive",
        "fuel_consumption_combined_l_100km",
        "fuel_consumption_city_l_100km",
        "fuel_consumption_highway_l_100km",
        "length_mm", "width_mm", "height_mm",
        "curb_weight_kg", "seats",
        "cargo_volume_l", "body_clearance_mm",
        "msrp_new_rub", "reliability_score",
        "msrp_source", "reliability_source", "enriched_at",
    ]
    final_cols = [c for c in base_columns if c in df.columns]
    df = df[final_cols].rename(columns={"modification_id": "id"})

    df["msrp_new_rub"] = df["msrp_new_rub"].astype("Int64")
    df["reliability_score"] = df["reliability_score"].astype("float64")
    for col in ["seats", "length_mm", "width_mm", "height_mm",
                "curb_weight_kg", "cargo_volume_l", "body_clearance_mm"]:
        if col in df.columns:
            df[col] = df[col].astype("Int64")

    out_path = PROC / "car_modifications.parquet"
    df.to_parquet(out_path, index=False)

    print()
    print("=" * 70)
    print("Final summary")
    print("=" * 70)
    info(f"wrote {out_path}: {len(df)} rows, {len(df.columns)} columns")
    info(f"NULL counts in final parquet:")
    null_counts = {c: df[c].isna().sum() for c in df.columns if df[c].isna().any()}
    if not null_counts:
        ok("0 NULLs in any column!")
    else:
        for c, n in null_counts.items():
            info(f"   {c}: {n}")

    print()
    print("=" * 70)
    print("OK  car_modifications.parquet enriched")
    print("=" * 70)


if __name__ == "__main__":
    main()
