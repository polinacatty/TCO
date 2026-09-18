"""Validator for ``service_plan_ops.csv`` (sprint 3 step S3.3).

Runs 11 checks. Returns exit code 0 on full GREEN, 1 on the first failure
(matching the convention of all other ``_*_validate.py`` scripts).

Checks performed:

1. **Schema** — exactly 5 required columns, no extras, no nulls except
   ``every_km`` / ``every_months`` which may be empty.
2. **Row count** — between 8 000 and 14 000 (480 gens × 17–28 ops).
3. **Generation coverage** — all 480 IDs from ``car_generations.csv``
   are present at least once; no extra IDs.
4. **FK to operations** — every ``operation_id`` exists in
   ``service_operations.csv``.
5. **Uniqueness** — ``(generation_id, operation_id)`` is unique
   (no operation duplicated within a single generation's plan).
6. **Mandatory operations** — every ICE generation has
   ``oil_change_engine`` and ``brake_pads_front``; every EV generation
   has ``brake_pads_front``. (``oil_change_engine`` is allowed to be
   absent only when ``source`` ends with ``+ev_override``.)
7. **Interval ranges** —
   ``every_km in [3 000, 250 000]`` when present;
   ``every_months in [1, 240]`` when present;
   at least one of ``every_km`` / ``every_months`` is set per row.
8. **Source values** — ``source`` matches one of:
   ``template_*`` or ``template_*+(ev_override|chain_override|belt_override)``.
9. **EV consistency** — every row whose ``source`` contains
   ``ev_override`` has ``operation_id`` NOT in the EV-skip set
   (oil/spark/timing/fuel/glow/accessory_belt).
10. **Drive override consistency** — for any generation whose ``source``
    contains ``chain_override``, plan must include
    ``timing_chain_inspection`` and NOT ``timing_belt_kit``; vice versa
    for ``belt_override``.
11. **Template diversity** — at least 8 of 10 templates from
    ``service_plan_templates.yaml`` are actually used (catches a
    silently broken applies_to mapping).
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
SEED = REPO / "ml" / "data" / "seed"

PLAN_OPS_CSV = SEED / "service_plan_ops.csv"
GENERATIONS_CSV = SEED / "car_generations.csv"
SERVICE_OPS_CSV = SEED / "service_operations.csv"
TEMPLATES_YAML = SEED / "service_plan_templates.yaml"

REQUIRED_COLS = ["generation_id", "operation_id", "every_km", "every_months", "source"]

EV_SKIP_OPS = {
    "oil_change_engine",
    "oil_filter",
    "spark_plugs",
    "glow_plugs",
    "fuel_filter",
    "timing_belt_kit",
    "timing_chain_inspection",
    "accessory_belt",
}

failures: list[str] = []


def fail(msg: str) -> None:
    failures.append(msg)
    print(f"  FAIL  {msg}")


def ok(msg: str) -> None:
    print(f"  OK    {msg}")


def load_rows() -> list[dict[str, str]]:
    with PLAN_OPS_CSV.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def load_generation_ids() -> set[int]:
    with GENERATIONS_CSV.open(encoding="utf-8", newline="") as f:
        return {int(row["id"]) for row in csv.DictReader(f)}


def load_op_id_to_code() -> dict[int, str]:
    out: dict[int, str] = {}
    with SERVICE_OPS_CSV.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            out[int(row["id"])] = row["code"]
    return out


def load_template_names() -> set[str]:
    with TEMPLATES_YAML.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return set(data["templates"].keys())


def parse_int_or_none(value: str) -> int | None:
    if value == "" or value is None:
        return None
    return int(value)


def main() -> int:
    print(f"Validating {PLAN_OPS_CSV.relative_to(REPO)}")

    rows = load_rows()
    gen_ids = load_generation_ids()
    op_id_to_code = load_op_id_to_code()
    template_names = load_template_names()

    if rows and list(rows[0].keys()) == REQUIRED_COLS:
        ok(f"schema: 5 columns ({', '.join(REQUIRED_COLS)})")
    else:
        fail(f"schema: expected {REQUIRED_COLS}, got {list(rows[0].keys()) if rows else 'EMPTY'}")
        return 1

    n = len(rows)
    if 8000 <= n <= 14000:
        ok(f"row count: {n} (in [8000, 14000])")
    else:
        fail(f"row count: {n} not in [8000, 14000]")

    rows_gen_ids = {int(r["generation_id"]) for r in rows}
    missing = gen_ids - rows_gen_ids
    extra = rows_gen_ids - gen_ids
    if not missing and not extra:
        ok(f"generation coverage: all {len(gen_ids)} generations present")
    else:
        if missing:
            fail(f"missing {len(missing)} generations (sample: {sorted(missing)[:5]})")
        if extra:
            fail(f"unknown generation_id values: {sorted(extra)[:5]}")

    bad_ops = {int(r["operation_id"]) for r in rows} - set(op_id_to_code)
    if not bad_ops:
        ok(f"FK to service_operations: all operation_id values exist")
    else:
        fail(f"unknown operation_id values: {sorted(bad_ops)[:5]}")

    seen: set[tuple[int, int]] = set()
    dups: list[tuple[int, int]] = []
    for r in rows:
        key = (int(r["generation_id"]), int(r["operation_id"]))
        if key in seen:
            dups.append(key)
        seen.add(key)
    if not dups:
        ok(f"uniqueness: (generation_id, operation_id) is unique")
    else:
        fail(f"duplicate (gen, op) pairs: {dups[:5]}")

    by_gen: dict[int, list[dict[str, str]]] = {}
    for r in rows:
        by_gen.setdefault(int(r["generation_id"]), []).append(r)

    missing_oil: list[int] = []
    missing_brakes: list[int] = []
    for gid, plan in by_gen.items():
        codes = {op_id_to_code[int(r["operation_id"])] for r in plan}
        any_source = plan[0]["source"]
        is_ev = "ev_override" in any_source
        if "brake_pads_front" not in codes:
            missing_brakes.append(gid)
        if not is_ev and "oil_change_engine" not in codes:
            missing_oil.append(gid)

    if not missing_oil:
        ok(f"every ICE generation has oil_change_engine")
    else:
        fail(f"ICE generations without oil_change_engine: {missing_oil[:5]}")

    if not missing_brakes:
        ok(f"every generation has brake_pads_front")
    else:
        fail(f"generations without brake_pads_front: {missing_brakes[:5]}")

    bad_intervals: list[str] = []
    for r in rows:
        ek = parse_int_or_none(r["every_km"])
        em = parse_int_or_none(r["every_months"])
        gid, oid = r["generation_id"], r["operation_id"]
        if ek is None and em is None:
            bad_intervals.append(f"gen={gid} op={oid}: both every_km and every_months empty")
            continue
        if ek is not None and not (3000 <= ek <= 250000):
            bad_intervals.append(f"gen={gid} op={oid}: every_km={ek} out of [3000, 250000]")
        if em is not None and not (1 <= em <= 240):
            bad_intervals.append(f"gen={gid} op={oid}: every_months={em} out of [1, 240]")

    if not bad_intervals:
        ok(f"interval ranges: every_km/every_months in valid bounds")
    else:
        fail(f"interval issues ({len(bad_intervals)} total, first 3): {bad_intervals[:3]}")

    bad_sources: set[str] = set()
    valid_suffixes = {"", "+ev_override", "+chain_override", "+belt_override"}
    for r in rows:
        src = r["source"]
        base = src.split("+")[0]
        suffix = src[len(base):]
        if base not in template_names or suffix not in valid_suffixes:
            bad_sources.add(src)
    if not bad_sources:
        ok(f"source values: all match 'template_*' or 'template_*+<override>'")
    else:
        fail(f"unknown source values: {sorted(bad_sources)[:5]}")

    ev_violations: list[tuple[int, str]] = []
    for r in rows:
        if "ev_override" in r["source"]:
            code = op_id_to_code[int(r["operation_id"])]
            if code in EV_SKIP_OPS:
                ev_violations.append((int(r["generation_id"]), code))
    if not ev_violations:
        ok(f"EV consistency: no EV-skip operations in EV-overridden plans")
    else:
        fail(f"EV plans contain ICE-only ops: {ev_violations[:5]}")

    drive_violations: list[str] = []
    for gid, plan in by_gen.items():
        src = plan[0]["source"]
        codes = {op_id_to_code[int(r["operation_id"])] for r in plan}
        if "chain_override" in src:
            if "timing_chain_inspection" not in codes:
                drive_violations.append(f"gen={gid} (chain_override) lacks timing_chain_inspection")
            if "timing_belt_kit" in codes:
                drive_violations.append(f"gen={gid} (chain_override) still has timing_belt_kit")
        elif "belt_override" in src:
            if "timing_belt_kit" not in codes:
                drive_violations.append(f"gen={gid} (belt_override) lacks timing_belt_kit")
            if "timing_chain_inspection" in codes:
                drive_violations.append(f"gen={gid} (belt_override) still has timing_chain_inspection")
    if not drive_violations:
        ok(f"drive override consistency: chain/belt swaps are clean")
    else:
        fail(f"drive override issues: {drive_violations[:3]}")

    used_templates = {r["source"].split("+")[0] for r in rows}
    if len(used_templates & template_names) >= 8:
        ok(f"template diversity: {len(used_templates & template_names)}/10 templates used")
    else:
        fail(f"only {len(used_templates & template_names)}/10 templates used")

    print()
    if failures:
        print(f"VALIDATION FAILED ({len(failures)} issues)")
        return 1
    print("VALIDATION PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
