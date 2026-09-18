"""Checks for ``tire_size_prices.csv`` (шаг 2.6).

Validates:
1. Schema (column names match exactly).
2. ``size_code`` matches `WWW/AA RDD` regex.
3. ``season`` is ``summer`` / ``winter``.
4. ``avg_set_price_rub`` is integer in [8 000, 250 000] (комплект 4 шин).
5. PK uniqueness — ``(size_code, season)``.
6. Coverage — каждый ``size_code`` из ``tire_sizes.csv`` представлен и
   в ``summer``, и в ``winter``.
7. Sanity: для одного и того же размера ``winter > summer``.
"""

from __future__ import annotations

import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TIRES_CSV = REPO / "ml" / "data" / "seed" / "tire_sizes.csv"
PRICES_CSV = REPO / "ml" / "data" / "seed" / "tire_size_prices.csv"

REQUIRED_COLS = ["size_code", "season", "avg_set_price_rub"]
SEASONS = {"summer", "winter"}
SIZE_RE = re.compile(r"^\d{3}/\d{2}\sR\d{2}$")


def main() -> int:
    errs: list[str] = []

    if not PRICES_CSV.is_file():
        print("FAIL: missing", PRICES_CSV)
        return 1
    if not TIRES_CSV.is_file():
        print("FAIL: missing", TIRES_CSV)
        return 1

    sizes_in_use: set[str] = set()
    with TIRES_CSV.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            sizes_in_use.add(row["size_code"])

    with PRICES_CSV.open(encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        if r.fieldnames != REQUIRED_COLS:
            errs.append(f"columns: got {r.fieldnames}")
        rows = list(r)

    n = len(rows)
    expected_min = 2 * len(sizes_in_use)
    if n < expected_min:
        errs.append(f"row count {n} < 2*{len(sizes_in_use)} (every size needs summer+winter)")

    seen_pk: set[tuple[str, str]] = set()
    seasons_per_size: dict[str, set[str]] = defaultdict(set)
    price_per_size_season: dict[tuple[str, str], int] = {}

    for i, row in enumerate(rows, start=2):
        size = row["size_code"].strip()
        season = row["season"].strip()

        if not SIZE_RE.match(size):
            errs.append(f"line {i}: size_code {size!r} doesn't match WWW/AA RDD")
            continue

        if size not in sizes_in_use:
            errs.append(f"line {i}: size_code {size!r} not present in tire_sizes.csv")

        if season not in SEASONS:
            errs.append(f"line {i}: season {season!r} not in {sorted(SEASONS)}")

        try:
            price = int(row["avg_set_price_rub"])
        except ValueError:
            errs.append(f"line {i}: avg_set_price_rub must be int, got {row['avg_set_price_rub']!r}")
            continue
        if not (8_000 <= price <= 250_000):
            errs.append(f"line {i}: avg_set_price_rub {price} out of [8000,250000]")

        pk = (size, season)
        if pk in seen_pk:
            errs.append(f"line {i}: duplicate PK {pk}")
        seen_pk.add(pk)

        seasons_per_size[size].add(season)
        price_per_size_season[(size, season)] = price

    missing_pairs = sorted(s for s in sizes_in_use if seasons_per_size.get(s) != SEASONS)
    if missing_pairs:
        errs.append(
            "sizes missing summer/winter pair: "
            + ", ".join(missing_pairs[:5])
            + (f" (+{len(missing_pairs) - 5} more)" if len(missing_pairs) > 5 else "")
        )

    for size in sizes_in_use:
        s_price = price_per_size_season.get((size, "summer"))
        w_price = price_per_size_season.get((size, "winter"))
        if s_price is not None and w_price is not None:
            if w_price <= s_price:
                errs.append(
                    f"size {size}: winter ({w_price}) must be > summer ({s_price})"
                )

    if errs:
        print("FAIL")
        for e in errs[:40]:
            print(" ", e)
        if len(errs) > 40:
            print(f" ... +{len(errs) - 40} more")
        return 1

    summer_prices = [v for (_, s), v in price_per_size_season.items() if s == "summer"]
    winter_prices = [v for (_, s), v in price_per_size_season.items() if s == "winter"]
    print(f"OK - tire_size_prices.csv ({n} rows; {len(seasons_per_size)} sizes x 2 seasons)")
    print(
        f"     summer RUB: min={min(summer_prices):,}, "
        f"median={sorted(summer_prices)[len(summer_prices)//2]:,}, "
        f"max={max(summer_prices):,}"
    )
    print(
        f"     winter RUB: min={min(winter_prices):,}, "
        f"median={sorted(winter_prices)[len(winter_prices)//2]:,}, "
        f"max={max(winter_prices):,}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
