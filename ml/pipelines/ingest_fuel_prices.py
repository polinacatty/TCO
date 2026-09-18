"""High-level ETL: download monthly retail fuel prices from fedstat / EMISS.

Pipeline overview
-----------------

::

    seed CSVs ──┐
                │   ┌─── GET indicator/31448 ──> IndicatorMeta (FGrid + CSRF)
                │   │
                ▼   ▼                         per requested year
       _bootstrap_fedstat_aliases.py   ───►   POST data.do?format=sdmx
       (run once, produces region/fuel        (85 regions × 4 fuels × 12 months)
        alias maps used here)                 │
                                              ▼
                                    raw SDMX 1.0 XML  (saved to disk)
                                              │
                                              ▼
                                    parse_sdmx_to_df  (long format)
                                              │
                                              ▼
                                  enrichment / normalisation
                                              │
                                              ▼
                                    5 data-quality checks
                                              │
                                              ▼
                                  fuel_prices.parquet

Why one POST per year (and not one giant POST for 12 years)?

* fedstat tends to truncate huge SDMX responses at the WAF level.  At
  ~4 K observations / year the response stays around 0.5 MB which is
  comfortably below any limit we have seen during reconnaissance.
* If a single year fails (network blip, fedstat 5xx), only that year's
  request is retried; the others stay cached.

Run::

    python ml\\pipelines\\ingest_fuel_prices.py --start-year 2024 --end-year 2024
    python ml\\pipelines\\ingest_fuel_prices.py --start-year 2014 --end-year 2025

Output:

* ``ml/data/raw/fedstat/<YYYY-MM-DD>/fuel_prices_31448_<year>.sdmx.xml``
* ``ml/data/processed/fuel_prices.parquet``
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

from _fedstat_client import (  # type: ignore[import-not-found]
    FedstatClient,
    IndicatorMeta,
    parse_sdmx_to_df,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
SEED_DIR = REPO_ROOT / "ml" / "data" / "seed"
RAW_BASE = REPO_ROOT / "ml" / "data" / "raw" / "fedstat"
PROCESSED_DIR = REPO_ROOT / "ml" / "data" / "processed"

INDICATOR_ID = "31448"
SOURCE_TAG = "rosstat_emiss"

# fedstat returns Russian month names verbatim in the PERIOD attribute.
MONTH_NAMES_RU = {
    "январь": 1,
    "февраль": 2,
    "март": 3,
    "апрель": 4,
    "май": 5,
    "июнь": 6,
    "июль": 7,
    "август": 8,
    "сентябрь": 9,
    "октябрь": 10,
    "ноябрь": 11,
    "декабрь": 12,
}

# Fuel label in our seed CSV → snake-case fuel_type used in data dictionary
# (and downstream DB schema).  Keep this map in one place so renames are
# atomic across the codebase.
FUEL_TYPE_FROM_LABEL = {
    "AI92": "ai92",
    "AI95": "ai95",
    "AI98": "ai98",
    "DIESEL": "diesel",
}


log = logging.getLogger("ingest_fuel_prices")


# ---------------------------------------------------------------------------
# Seed loading
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RegionAlias:
    region_id: int
    okato_code: str
    fgrid_value_id: str


@dataclass(frozen=True)
class FuelAlias:
    fuel_label: str
    grtov_code: str
    fgrid_value_id: str


def _load_region_aliases() -> list[RegionAlias]:
    path = SEED_DIR / "fedstat_region_aliases.csv"
    out: list[RegionAlias] = []
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            okato = row["okato_code"].strip()
            fgrid = row["fgrid_value_id"].strip()
            if not okato or not fgrid:
                raise RuntimeError(
                    f"row {row['region_id']!r} in {path.name} missing okato/fgrid; "
                    "rerun _bootstrap_fedstat_aliases.py"
                )
            out.append(
                RegionAlias(
                    region_id=int(row["region_id"]),
                    okato_code=okato,
                    fgrid_value_id=fgrid,
                )
            )
    if not out:
        raise RuntimeError(f"{path} is empty")
    return out


def _load_fuel_aliases() -> list[FuelAlias]:
    path = SEED_DIR / "fedstat_fuel_aliases.csv"
    out: list[FuelAlias] = []
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            grtov = row["grtov_code"].strip()
            fgrid = row["fgrid_value_id"].strip()
            if not grtov or not fgrid:
                raise RuntimeError(
                    f"row {row['fuel_label']!r} in {path.name} missing grtov/fgrid; "
                    "rerun _bootstrap_fedstat_aliases.py"
                )
            out.append(
                FuelAlias(
                    fuel_label=row["fuel_label"],
                    grtov_code=grtov,
                    fgrid_value_id=fgrid,
                )
            )
    if len(out) != 4:
        raise RuntimeError(f"{path} expected 4 fuel rows, got {len(out)}")
    return out


# ---------------------------------------------------------------------------
# Year-by-year download
# ---------------------------------------------------------------------------


def _resolve_period_ids(meta: IndicatorMeta) -> list[str]:
    """Return FGrid value_ids for all 12 months on field ``33560``.

    Robust to fedstat sneaking new entries onto that field (e.g. half-year
    aggregates) — we explicitly look up each Russian month name.
    """
    period_field = meta.fields["33560"]
    out: list[str] = []
    for ru_name in MONTH_NAMES_RU:
        ids = period_field.find_value_ids(ru_name)
        if not ids:
            raise RuntimeError(f"month {ru_name!r} not found in field 33560")
        # Picking the shortest matching name: e.g. for "май" we want exactly
        # "май", not "первое полугодие, май-июнь".
        ids.sort(key=lambda vid: len(period_field.values[vid]))
        out.append(ids[0])
    return out


def _post_year(
    fs: FedstatClient,
    meta: IndicatorMeta,
    year: int,
    region_fgrid_ids: list[str],
    fuel_fgrid_ids: list[str],
    period_fgrid_ids: list[str],
    raw_path: Path,
) -> bytes:
    """POST a single-year request, persist raw bytes and return them."""
    filters = {
        "3":     [str(year)],
        "33560": period_fgrid_ids,
        "57831": region_fgrid_ids,
        "58273": fuel_fgrid_ids,
        # 30611 = unit of measurement: keep all (we'll filter on EI=рубль later)
        "30611": "*",
    }
    raw = fs.post_filtered(INDICATOR_ID, meta, filters, fmt="sdmx")
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(raw)
    log.info("year %s: %d bytes -> %s", year, len(raw), raw_path)
    return raw


# ---------------------------------------------------------------------------
# Enrichment
# ---------------------------------------------------------------------------


def _enrich(
    df: pd.DataFrame,
    regions: list[RegionAlias],
    fuels: list[FuelAlias],
    *,
    ingested_at: pd.Timestamp,
) -> pd.DataFrame:
    """Convert fedstat long-format into the data-dictionary schema."""
    if df.empty:
        return pd.DataFrame(
            columns=[
                "region_id", "fuel_type", "price_month",
                "price_rub_per_l", "source", "ingested_at",
            ]
        )

    okato_to_region = {r.okato_code: r.region_id for r in regions}
    grtov_to_fuel_type = {
        f.grtov_code: FUEL_TYPE_FROM_LABEL[f.fuel_label] for f in fuels
    }

    out = pd.DataFrame()
    out["region_id"] = df["s_OKATO"].map(okato_to_region)
    out["fuel_type"] = df["s_grtov"].map(grtov_to_fuel_type)

    # Drop rows we cannot map (other regions/goods that fedstat may
    # accidentally include in the response).  Logged at WARNING so the
    # operator notices unexpected drift.
    unmapped_region = df["s_OKATO"][out["region_id"].isna()].unique()
    unmapped_fuel = df["s_grtov"][out["fuel_type"].isna()].unique()
    if len(unmapped_region):
        log.warning("dropping rows with unknown OKATO: %s", unmapped_region.tolist())
    if len(unmapped_fuel):
        log.warning("dropping rows with unknown grtov: %s", unmapped_fuel.tolist())

    period_str = df["PERIOD"].astype(str).str.strip().str.lower()
    month = period_str.map(MONTH_NAMES_RU)
    bad_period = period_str[month.isna()].unique()
    if len(bad_period):
        log.warning("dropping rows with unparseable PERIOD: %s", bad_period.tolist())

    year = pd.to_numeric(df["TIME_PERIOD"], errors="coerce")

    # Filter only ruble values.  fedstat for indicator 31448 always
    # returns "рубль" today, but we guard against future units (e.g. USD)
    # being mixed into the same indicator.
    ei = df["EI"].astype(str).str.strip().str.lower()
    is_rub = ei.str.contains("руб")

    out["price_rub_per_l"] = df["OBS_VALUE"].astype(float)

    out["price_month"] = pd.to_datetime(
        {"year": year, "month": month, "day": 1},
        errors="coerce",
    )

    out["source"] = SOURCE_TAG
    out["ingested_at"] = ingested_at

    keep = (
        out["region_id"].notna()
        & out["fuel_type"].notna()
        & out["price_month"].notna()
        & out["price_rub_per_l"].notna()
        & is_rub
    )
    dropped = (~keep).sum()
    if dropped:
        log.info("enrich: dropped %d/%d rows during normalisation", dropped, len(out))
    out = out[keep].copy()

    out["region_id"] = out["region_id"].astype("int32")
    out["fuel_type"] = out["fuel_type"].astype("string")
    out["price_rub_per_l"] = out["price_rub_per_l"].astype("float32")
    out["source"] = out["source"].astype("string")

    # Stable ordering — useful for diff-friendly parquet files in code review.
    out = out.sort_values(
        ["price_month", "region_id", "fuel_type"], kind="stable"
    ).reset_index(drop=True)
    return out


# ---------------------------------------------------------------------------
# Data quality checks (5)
# ---------------------------------------------------------------------------


class DataQualityError(RuntimeError):
    """Raised when a hard data-quality assertion fails."""


def _check_quality(df: pd.DataFrame, *, expected_year_range: tuple[int, int]) -> None:
    """Five hard / soft checks aligned with `02_data_dictionary.md`.

    Hard checks (raise) protect downstream consumers from obviously
    broken data; soft checks (warn) are coverage thresholds that may
    legitimately be missed for short windows.
    """
    n = len(df)
    if n == 0:
        raise DataQualityError("DQ-0: empty dataframe — nothing was ingested")

    # 1. Schema
    expected_cols = {
        "region_id", "fuel_type", "price_month",
        "price_rub_per_l", "source", "ingested_at",
    }
    missing = expected_cols - set(df.columns)
    extra = set(df.columns) - expected_cols
    if missing or extra:
        raise DataQualityError(
            f"DQ-1: schema mismatch (missing={missing}, extra={extra})"
        )

    # 2. Price plausibility (15..150 ₽/l, hard).
    price = df["price_rub_per_l"]
    bad_price = ((price < 15) | (price > 150)).sum()
    if bad_price:
        sample = df.loc[(price < 15) | (price > 150)].head(5).to_dict("records")
        raise DataQualityError(
            f"DQ-2: {bad_price}/{n} rows have price outside [15, 150] ₽/l; "
            f"sample={sample}"
        )

    # 3. Uniqueness on (region_id, fuel_type, price_month) (hard).
    dup_mask = df.duplicated(subset=["region_id", "fuel_type", "price_month"])
    n_dup = int(dup_mask.sum())
    if n_dup:
        sample = df.loc[dup_mask].head(5).to_dict("records")
        raise DataQualityError(
            f"DQ-3: {n_dup} duplicate (region_id, fuel_type, price_month) rows; "
            f"sample={sample}"
        )

    # 4. Coverage: distinct regions ≥ 70 (soft if window is narrow).
    regions = df["region_id"].nunique()
    if regions < 70:
        msg = f"DQ-4: only {regions} distinct regions covered (target ≥70)"
        # Always warn at minimum.
        log.warning("%s", msg)
        # In a long-window run we want a hard error.
        if expected_year_range[1] - expected_year_range[0] >= 5:
            raise DataQualityError(msg)

    # 5. Coverage: months × fuel types
    months = df["price_month"].nunique()
    fuels = df["fuel_type"].nunique()
    target_months = (expected_year_range[1] - expected_year_range[0] + 1) * 12
    if fuels < 4:
        raise DataQualityError(
            f"DQ-5: only {fuels} fuel types present (expected 4: ai92/ai95/ai98/diesel)"
        )
    if months < int(target_months * 0.7):
        msg = (
            f"DQ-5: only {months}/{target_months} months populated "
            f"(<70% coverage)"
        )
        log.warning("%s", msg)
        if expected_year_range[1] - expected_year_range[0] >= 5:
            raise DataQualityError(msg)

    log.info(
        "DQ OK: %d rows, %d regions, %d months, %d fuel types, "
        "price ∈ [%.2f, %.2f] ₽/l",
        n, regions, months, fuels, price.min(), price.max(),
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Download monthly retail fuel prices for all 85 RF subjects "
            "from fedstat indicator 31448 and write a tidy parquet."
        ),
    )
    p.add_argument("--start-year", type=int, default=2014,
                   help="First year to download (inclusive). Default: 2014")
    p.add_argument("--end-year", type=int, default=dt.date.today().year,
                   help="Last year to download (inclusive). "
                        "Default: current calendar year")
    p.add_argument("--out", type=Path,
                   default=PROCESSED_DIR / "fuel_prices.parquet",
                   help="Path for the output parquet file")
    p.add_argument("--raw-dir", type=Path, default=None,
                   help="Override directory for raw SDMX dumps. "
                        "Defaults to ml/data/raw/fedstat/<today>/")
    p.add_argument("-v", "--verbose", action="store_true",
                   help="Set log level to DEBUG")
    return p.parse_args(list(argv) if argv is not None else None)


def main(argv: Iterable[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s :: %(message)s",
    )

    if args.start_year > args.end_year:
        log.error("--start-year (%d) must be ≤ --end-year (%d)",
                  args.start_year, args.end_year)
        return 2

    today = dt.date.today().isoformat()
    raw_dir = args.raw_dir or (RAW_BASE / today)
    raw_dir.mkdir(parents=True, exist_ok=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)

    regions = _load_region_aliases()
    fuels = _load_fuel_aliases()
    log.info("seed loaded: %d regions, %d fuels", len(regions), len(fuels))

    region_fgrid_ids = [r.fgrid_value_id for r in regions]
    fuel_fgrid_ids = [f.fgrid_value_id for f in fuels]

    ingested_at = pd.Timestamp.utcnow().tz_convert("UTC")
    all_frames: list[pd.DataFrame] = []

    with FedstatClient() as fs:
        log.info("step 1: GET indicator %s", INDICATOR_ID)
        meta = fs.get_filter_ids(INDICATOR_ID)
        log.info("title=%r", meta.title)

        period_fgrid_ids = _resolve_period_ids(meta)
        log.info("resolved 12 month period ids")

        for year in range(args.start_year, args.end_year + 1):
            raw_path = raw_dir / f"fuel_prices_{INDICATOR_ID}_{year}.sdmx.xml"
            log.info("step 2.%d: POST data.do for year %d", year, year)
            raw = _post_year(
                fs, meta, year,
                region_fgrid_ids, fuel_fgrid_ids, period_fgrid_ids,
                raw_path,
            )
            df_year = parse_sdmx_to_df(raw)
            log.info("year %d: parsed %d SDMX rows", year, len(df_year))
            if df_year.empty:
                log.warning("year %d returned empty SDMX; skipping", year)
                continue
            df_year = _enrich(df_year, regions, fuels, ingested_at=ingested_at)
            log.info("year %d: %d rows after enrichment", year, len(df_year))
            all_frames.append(df_year)

    if not all_frames:
        log.error("no data collected for any year in range — aborting")
        return 3

    df = pd.concat(all_frames, ignore_index=True)
    log.info("combined: %d rows from %d years",
             len(df), len(all_frames))

    log.info("step 3: data quality checks")
    _check_quality(df, expected_year_range=(args.start_year, args.end_year))

    log.info("step 4: write %s", args.out)
    # Explicit pyarrow types via pandas' built-in mapping.  Parquet's
    # logical types are inferred from these dtypes.
    df.to_parquet(args.out, index=False, engine="pyarrow", compression="snappy")
    log.info("wrote %d rows to %s (size=%d bytes)",
             len(df), args.out, args.out.stat().st_size)

    return 0


if __name__ == "__main__":
    sys.exit(main())
