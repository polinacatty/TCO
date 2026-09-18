"""Checks for ``mileage_penalties.csv`` (шаг 2.8, ADR-0001).

Validates:
1. Schema (column names match exactly).
2. Row count ровно 3 (по ADR-0001: пороги 100/150/200 тыс. км).
3. Точное содержимое: пороги {100000, 150000, 200000} с штрафами {3.00, 5.00, 7.00}.
4. ``mileage_threshold_km`` is INT > 0.
5. ``extra_depreciation_pct`` is float in (0, 20].
6. Monotonicity — пороги отсортированы по возрастанию, штрафы тоже растут.
7. ``valid_from`` is ISO date.
8. ``source_note`` non-empty.
"""

from __future__ import annotations

import csv
import re
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CSV_PATH = REPO / "ml" / "data" / "seed" / "mileage_penalties.csv"

REQUIRED_COLS = ["mileage_threshold_km", "extra_depreciation_pct", "source_note", "valid_from"]
EXPECTED_THRESHOLDS = (100_000, 150_000, 200_000)
EXPECTED_PCTS = (3.00, 5.00, 7.00)
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def main() -> int:
    errs: list[str] = []

    if not CSV_PATH.is_file():
        print("FAIL: missing", CSV_PATH)
        return 1

    with CSV_PATH.open(encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        if r.fieldnames != REQUIRED_COLS:
            errs.append(f"columns: got {r.fieldnames}")
        rows = list(r)

    if len(rows) != 3:
        errs.append(f"expected 3 rows (ADR-0001), got {len(rows)}")

    thresholds: list[int] = []
    pcts: list[float] = []

    for i, row in enumerate(rows, start=2):
        try:
            threshold = int(row["mileage_threshold_km"])
        except ValueError:
            errs.append(f"line {i}: mileage_threshold_km must be int, got {row['mileage_threshold_km']!r}")
            continue
        if threshold <= 0:
            errs.append(f"line {i}: mileage_threshold_km {threshold} must be > 0")
        thresholds.append(threshold)

        try:
            pct = float(row["extra_depreciation_pct"])
        except ValueError:
            errs.append(f"line {i}: extra_depreciation_pct must be float, got {row['extra_depreciation_pct']!r}")
            continue
        if not (0 < pct <= 20):
            errs.append(f"line {i}: extra_depreciation_pct {pct} out of (0,20]")
        pcts.append(pct)

        valid_from = row["valid_from"].strip()
        if not ISO_DATE_RE.match(valid_from):
            errs.append(f"line {i}: valid_from {valid_from!r} is not ISO date")
        else:
            try:
                date.fromisoformat(valid_from)
            except ValueError:
                errs.append(f"line {i}: valid_from {valid_from!r} not parseable")

        if not row["source_note"].strip():
            errs.append(f"line {i}: empty source_note")

    if tuple(thresholds) != EXPECTED_THRESHOLDS:
        errs.append(f"thresholds {thresholds} != ADR-0001 expected {list(EXPECTED_THRESHOLDS)}")
    if tuple(pcts) != EXPECTED_PCTS:
        errs.append(f"pcts {pcts} != ADR-0001 expected {list(EXPECTED_PCTS)}")

    for k in range(1, len(thresholds)):
        if thresholds[k] <= thresholds[k - 1]:
            errs.append(f"thresholds not strictly increasing at index {k}")
    for k in range(1, len(pcts)):
        if pcts[k] <= pcts[k - 1]:
            errs.append(f"pcts not strictly increasing at index {k}")

    if errs:
        print("FAIL")
        for e in errs[:20]:
            print(" ", e)
        return 1

    print(f"OK - mileage_penalties.csv ({len(rows)} rows)")
    for t, p in zip(thresholds, pcts):
        print(f"     >= {t:>7,} km -> +{p:.2f} pp")
    return 0


if __name__ == "__main__":
    sys.exit(main())
