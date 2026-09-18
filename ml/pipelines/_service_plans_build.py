"""Build ``service_plan_ops.csv`` for sprint 3 step S3.3.

Fans out 10 templates from ``service_plan_templates.yaml`` to all 480
generations of ``car_generations.csv``. The mapping is keyed by
``(segment_6, brand_tier)`` derived from joining
car_generations -> car_models -> car_makes:

- ``segment_6`` is obtained by mapping ``car_models.segment`` (12 values)
  to the 6 buckets used in ``depreciation_rates.csv``
  (rule from 06_catalog_methodology.md §7.5).
- ``brand_tier`` is read directly from ``car_makes.csv``.

Two override layers are then applied on top of the template:

1. **EV override (automatic)** — if every modification of a generation in
   ``car_modifications.parquet`` has ``fuel_type == "ELECTRIC"``, the
   following ICE-only operations are dropped from the plan:
   ``oil_change_engine``, ``oil_filter``, ``spark_plugs``, ``glow_plugs``,
   ``fuel_filter``, ``timing_belt_kit``, ``timing_chain_inspection``,
   ``accessory_belt``. HYBRID modifications are NOT EV-only (they still
   have ICE), so they keep the full template.

2. **Drive-type override (whitelist)** — for generations whose actual
   timing drive type does not match the template default (mass = belt,
   chinese/premium = chain), an explicit override flips
   ``timing_belt_kit`` <-> ``timing_chain_inspection``. Currently
   covers 12 popular ICE generations (Camry, RAV4, Solaris, Tucson,
   Rio, K5, Qashqai, CX-5, Outlander, Forester, Outback, Duster).

Output schema (flat, easy to migrate to ``service_plans``+``service_plan_ops``
in Postgres later):

    generation_id, operation_id, every_km, every_months, source

Idempotent: rebuild gives byte-identical CSV.

Run from repo root::

    python ml/pipelines/_service_plans_build.py
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

REPO = Path(__file__).resolve().parents[2]
SEED = REPO / "ml" / "data" / "seed"
PROCESSED = REPO / "ml" / "data" / "processed"

CAR_MAKES_CSV = SEED / "car_makes.csv"
CAR_MODELS_CSV = SEED / "car_models.csv"
CAR_GENERATIONS_CSV = SEED / "car_generations.csv"
SERVICE_OPS_CSV = SEED / "service_operations.csv"
TEMPLATES_YAML = SEED / "service_plan_templates.yaml"
MODIFICATIONS_PARQUET = PROCESSED / "car_modifications.parquet"

OUT_CSV = SEED / "service_plan_ops.csv"

# Per 06_catalog_methodology.md §7.5: 12 model segments -> 6 depreciation segments.
SEGMENT_12_TO_6: dict[str, str] = {
    "A": "A_B",
    "B": "A_B",
    "C": "C_D",
    "D": "C_D",
    "OTHER": "C_D",
    "E": "E_F",
    "F": "E_F",
    "S_SPORT": "E_F",
    "J_SUV": "J_SUV",
    "J_CROSS": "J_CROSS",
    "M_MPV": "J_CROSS",
    "LCV": "LCV",
}

# Operations skipped for EV-only generations (no ICE = no oil/spark/timing/fuel).
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

# Drive-type override for ICE generations whose actual timing drive
# differs from template default (template default: mass=belt,
# chinese/premium=chain). Keys are (make_normalized, model_normalized).
# Values: "chain" or "belt".
#
# Sources: drive2.ru bortovye journals + Wikipedia per engine code.
DRIVE_OVERRIDES: dict[tuple[str, str], str] = {
    # mass / jp_kr_mass actually using a chain (override default belt)
    ("toyota", "camry"): "chain",          # 2AR-FE / 2GR-FE — chain
    ("toyota", "rav4"): "chain",           # 2AR-FE — chain
    ("toyota", "corolla"): "chain",        # 2ZR-FE — chain
    ("hyundai", "solaris"): "chain",       # G4FA / G4FC — chain
    ("hyundai", "tucson"): "chain",        # Theta II 2.0 — chain
    ("kia", "rio"): "chain",               # G4FA — chain
    ("kia", "k5"): "chain",                # Theta III — chain
    ("nissan", "qashqai"): "chain",        # MR20DE — chain
    ("mazda", "cx5"): "chain",             # SkyActiv-G — chain
    ("mitsubishi", "outlander"): "chain",  # 4B11 / 4B12 — chain
    ("subaru", "forester"): "chain",       # FB20 — chain
    ("subaru", "outback"): "chain",        # FB25 — chain
}


def load_makes() -> dict[int, dict[str, str]]:
    out: dict[int, dict[str, str]] = {}
    with CAR_MAKES_CSV.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            out[int(row["id"])] = {
                "name_normalized": row["name_normalized"],
                "brand_tier": row["brand_tier"],
            }
    return out


def load_models() -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    with CAR_MODELS_CSV.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            out[int(row["id"])] = {
                "make_id": int(row["make_id"]),
                "name_normalized": row["name_normalized"],
                "segment": row["segment"],
            }
    return out


def load_generations() -> list[dict[str, int]]:
    out: list[dict[str, int]] = []
    with CAR_GENERATIONS_CSV.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            out.append({
                "id": int(row["id"]),
                "model_id": int(row["model_id"]),
            })
    return out


def load_op_codes() -> dict[str, int]:
    out: dict[str, int] = {}
    with SERVICE_OPS_CSV.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            out[row["code"]] = int(row["id"])
    return out


def load_templates() -> tuple[dict[str, list[dict[str, Any]]], dict[tuple[str, str], str]]:
    """Return (template_name -> [op]) and ((segment_6, tier) -> template_name)."""
    with TEMPLATES_YAML.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)

    templates_ops: dict[str, list[dict[str, Any]]] = {}
    pair_to_template: dict[tuple[str, str], str] = {}

    for tname, tdata in data["templates"].items():
        templates_ops[tname] = list(tdata["operations"])
        for entry in tdata["applies_to"]:
            pair_to_template[(entry["segment"], entry["brand_tier"])] = tname

    return templates_ops, pair_to_template


def load_ev_only_generation_ids() -> set[int]:
    """Return set of generation IDs where ALL modifications have fuel_type=ELECTRIC."""
    df = pd.read_parquet(MODIFICATIONS_PARQUET)
    grouped = df.groupby("generation_id")["fuel_type"].agg(set)
    return {int(gid) for gid, fuels in grouped.items() if fuels == {"ELECTRIC"}}


def apply_drive_override(ops: list[dict[str, Any]], desired: str) -> tuple[list[dict[str, Any]], bool]:
    """Replace timing_belt_kit <-> timing_chain_inspection. Returns (new_ops, applied?)."""
    applied = False
    out: list[dict[str, Any]] = []
    for op in ops:
        code = op["code"]
        if desired == "chain" and code == "timing_belt_kit":
            new_op = {"code": "timing_chain_inspection", "every_km": 60000}
            out.append(new_op)
            applied = True
            continue
        if desired == "belt" and code == "timing_chain_inspection":
            new_op = {
                "code": "timing_belt_kit",
                "every_km": 90000,
                "every_months": 72,
            }
            out.append(new_op)
            applied = True
            continue
        out.append(op)
    return out, applied


def main() -> int:
    makes = load_makes()
    models = load_models()
    generations = load_generations()
    op_code_to_id = load_op_codes()
    templates_ops, pair_to_template = load_templates()
    ev_only_gens = load_ev_only_generation_ids()

    rows: list[dict[str, Any]] = []
    template_usage: dict[str, int] = {}
    ev_count = 0
    chain_override_count = 0
    belt_override_count = 0

    for gen in generations:
        gen_id = gen["id"]
        model = models[gen["model_id"]]
        make = makes[model["make_id"]]
        segment_12 = model["segment"]
        segment_6 = SEGMENT_12_TO_6[segment_12]
        tier = make["brand_tier"]

        template_name = pair_to_template[(segment_6, tier)]
        template_usage[template_name] = template_usage.get(template_name, 0) + 1
        ops = list(templates_ops[template_name])
        source = template_name

        if gen_id in ev_only_gens:
            ops = [op for op in ops if op["code"] not in EV_SKIP_OPS]
            source = f"{template_name}+ev_override"
            ev_count += 1
        else:
            override = DRIVE_OVERRIDES.get((make["name_normalized"], model["name_normalized"]))
            if override == "chain":
                ops, applied = apply_drive_override(ops, "chain")
                if applied:
                    source = f"{template_name}+chain_override"
                    chain_override_count += 1
            elif override == "belt":
                ops, applied = apply_drive_override(ops, "belt")
                if applied:
                    source = f"{template_name}+belt_override"
                    belt_override_count += 1

        for op in ops:
            code = op["code"]
            if code not in op_code_to_id:
                raise RuntimeError(f"Unknown operation code {code!r} in template {template_name!r}")
            rows.append({
                "generation_id": gen_id,
                "operation_id": op_code_to_id[code],
                "every_km": op.get("every_km") or "",
                "every_months": op.get("every_months") or "",
                "source": source,
            })

    rows.sort(key=lambda r: (r["generation_id"], r["operation_id"]))

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["generation_id", "operation_id", "every_km", "every_months", "source"],
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    print(f"Wrote {OUT_CSV.relative_to(REPO)} ({len(rows)} rows; {len(generations)} generations covered)")
    print(f"  EV override applied to        {ev_count:>3} generations")
    print(f"  Chain override applied to     {chain_override_count:>3} generations")
    print(f"  Belt override applied to      {belt_override_count:>3} generations")
    print("  Template usage:")
    for tname, cnt in sorted(template_usage.items(), key=lambda x: -x[1]):
        print(f"    {tname:<30} {cnt:>3} generations")
    return 0


if __name__ == "__main__":
    sys.exit(main())
