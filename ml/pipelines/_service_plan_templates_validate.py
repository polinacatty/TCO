"""Checks for ``service_plan_templates.yaml`` (шаг 3.2).

Per план спринта 3 §S3.2: 6–10 шаблонов регламентов в YAML, маппинг по
``(segment × brand_tier)`` покрывает все 30 пар, каждый шаблон ссылается
на существующие ``code`` из ``service_operations.csv``.

Validates:
1. YAML loads, has required top-level keys (version, valid_from, templates).
2. ``version`` matches semver-ish pattern; ``valid_from`` ISO-8601.
3. Templates count in [6, 10].
4. Each template has required fields (description, applies_to, operations).
5. Each ``applies_to`` entry is {segment, brand_tier} from valid enums.
6. Cartesian completeness: all 30 (segment × brand_tier) pairs covered exactly once.
7. Each operation references a code from ``service_operations.csv``.
8. Each operation has at least one of (every_km, every_months).
9. Numeric ranges:
   - every_km ∈ [1_000, 200_000]
   - every_months ∈ [1, 120]
10. Each template has >= 5 operations (must include `oil_change_engine`
    OR explicit waiver for EV templates — none in v1.0).
11. Each template includes `oil_change_engine`, `brake_pads_front`,
    `wiper_blades_front` (basic safety/wear minimum).
"""

from __future__ import annotations

import csv
import re
import sys
from datetime import date
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
YAML_PATH = REPO / "ml" / "data" / "seed" / "service_plan_templates.yaml"
OPS_CSV_PATH = REPO / "ml" / "data" / "seed" / "service_operations.csv"

SEGMENTS = {"A_B", "C_D", "E_F", "J_SUV", "J_CROSS", "LCV"}
TIERS = {"russian", "mass", "japanese_korean_mass", "chinese", "premium"}
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
VERSION_RE = re.compile(r"^\d+\.\d+(\.\d+)?$")
MIN_OPS_PER_TEMPLATE = 5
MANDATORY_OPS = {"oil_change_engine", "brake_pads_front", "wiper_blades_front"}


def load_op_codes() -> set[str]:
    out: set[str] = set()
    with OPS_CSV_PATH.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            out.add(row["code"].strip())
    return out


def main() -> int:
    errs: list[str] = []

    if not YAML_PATH.is_file():
        print("FAIL: missing", YAML_PATH)
        return 1
    if not OPS_CSV_PATH.is_file():
        print("FAIL: missing", OPS_CSV_PATH)
        return 1

    try:
        with YAML_PATH.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        print(f"FAIL: YAML parse error: {e}")
        return 1

    if not isinstance(data, dict):
        print("FAIL: root is not a mapping")
        return 1

    for key in ("version", "valid_from", "templates"):
        if key not in data:
            errs.append(f"missing top-level key: {key!r}")

    if "version" in data and not VERSION_RE.match(str(data["version"])):
        errs.append(f"version {data['version']!r} not semver-ish")

    if "valid_from" in data:
        vf = str(data["valid_from"])
        if not ISO_DATE_RE.match(vf):
            errs.append(f"valid_from {vf!r} not ISO date")
        else:
            try:
                date.fromisoformat(vf)
            except ValueError:
                errs.append(f"valid_from {vf!r} not parseable")

    templates = data.get("templates", {}) or {}
    if not isinstance(templates, dict):
        print("FAIL: templates must be a mapping")
        return 1

    n = len(templates)
    if not (6 <= n <= 10):
        errs.append(f"templates count {n} not in [6, 10] (план §S3.2)")

    op_codes = load_op_codes()

    pair_to_template: dict[tuple[str, str], str] = {}
    op_count_per_template: dict[str, int] = {}

    for tname, tdata in templates.items():
        if not isinstance(tdata, dict):
            errs.append(f"template {tname!r}: not a mapping")
            continue

        for key in ("description", "applies_to", "operations"):
            if key not in tdata:
                errs.append(f"template {tname!r}: missing field {key!r}")

        applies_to = tdata.get("applies_to") or []
        if not isinstance(applies_to, list) or not applies_to:
            errs.append(f"template {tname!r}: applies_to must be non-empty list")
        else:
            for j, entry in enumerate(applies_to):
                if not isinstance(entry, dict):
                    errs.append(f"template {tname!r} applies_to[{j}]: not a mapping")
                    continue
                seg = entry.get("segment")
                tier = entry.get("brand_tier")
                if seg not in SEGMENTS:
                    errs.append(f"template {tname!r} applies_to[{j}]: bad segment {seg!r}")
                if tier not in TIERS:
                    errs.append(f"template {tname!r} applies_to[{j}]: bad brand_tier {tier!r}")
                if seg in SEGMENTS and tier in TIERS:
                    pair = (seg, tier)
                    if pair in pair_to_template:
                        errs.append(
                            f"pair {pair} covered by both {pair_to_template[pair]!r} "
                            f"and {tname!r} — must be unique"
                        )
                    else:
                        pair_to_template[pair] = tname

        operations = tdata.get("operations") or []
        if not isinstance(operations, list) or len(operations) < MIN_OPS_PER_TEMPLATE:
            errs.append(
                f"template {tname!r}: must have >= {MIN_OPS_PER_TEMPLATE} operations, "
                f"got {len(operations) if isinstance(operations, list) else 'invalid'}"
            )

        seen_codes: set[str] = set()
        for j, op in enumerate(operations):
            if not isinstance(op, dict):
                errs.append(f"template {tname!r} op[{j}]: not a mapping")
                continue
            code = op.get("code")
            if not code or not isinstance(code, str):
                errs.append(f"template {tname!r} op[{j}]: missing/invalid code")
                continue
            if code not in op_codes:
                errs.append(f"template {tname!r} op[{j}]: code {code!r} not in service_operations.csv")
            if code in seen_codes:
                errs.append(f"template {tname!r}: duplicate code {code!r} in operations")
            seen_codes.add(code)

            ekm = op.get("every_km")
            emo = op.get("every_months")

            if ekm is None and emo is None:
                errs.append(
                    f"template {tname!r} op[{j}] code={code!r}: "
                    f"at least one of (every_km, every_months) required"
                )

            if ekm is not None:
                if not isinstance(ekm, int) or not (1_000 <= ekm <= 200_000):
                    errs.append(f"template {tname!r} op[{j}] code={code!r}: every_km {ekm!r} out of [1k, 200k]")
            if emo is not None:
                if not isinstance(emo, int) or not (1 <= emo <= 120):
                    errs.append(f"template {tname!r} op[{j}] code={code!r}: every_months {emo!r} out of [1, 120]")

        missing_mandatory = MANDATORY_OPS - seen_codes
        if missing_mandatory:
            errs.append(f"template {tname!r}: missing mandatory codes {sorted(missing_mandatory)}")

        op_count_per_template[tname] = len(operations)

    expected_pairs = {(s, t) for s in SEGMENTS for t in TIERS}
    missing_pairs = expected_pairs - set(pair_to_template)
    if missing_pairs:
        errs.append(f"cartesian gap: missing {sorted(missing_pairs)}")

    if errs:
        print("FAIL")
        for e in errs[:30]:
            print(" ", e)
        return 1

    by_template = sorted(op_count_per_template.items())
    print(f"OK - service_plan_templates.yaml ({n} templates; 30/30 pairs covered)")
    print(f"     ops per template:")
    for tname, opc in by_template:
        n_pairs = sum(1 for p, t in pair_to_template.items() if t == tname)
        print(f"       {tname:<30} ops={opc:>2}  covers {n_pairs} pair(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
