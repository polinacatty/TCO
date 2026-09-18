"""Structural validator for OSAGO seed CSVs.

Runs after manual transcription of values from Bank of Russia Directive
7204-У of 09.10.2025 (sprint 1, step 1.3.3).  The script does **not**
verify individual numbers against the directive — that is done by hand
on a sample of cells, see ``docs/03_data_collection/04_osago_recon.md``,
section "Способ А".  Instead it verifies properties that, taken together,
catch the overwhelming majority of typos:

* schema (column names + dtypes per file),
* range of each numeric column (rules out copy-paste off-by-order-of-magnitude
  bugs such as ``4.6`` instead of ``0.46``),
* uniqueness of natural keys,
* coverage (e.g. all 85 regions from ``regions.csv`` have a KT row),
* monotonicity / "ladder" properties (KBM value strictly decreases with
  class; KBM transition matrix never moves a driver up after a claim),
* triangular shape of the KVS table (no impossible age × experience
  combinations),
* a small set of point-checks ("smoke tests") that pin specific cells
  against the directive: TB row 2.2 = 1399/8665, KBM-13 = 0.46,
  KT(Уфа) = 1.56, KT(Новосибирск) = 3.12, KO(физлицо/неогр.) = 3.16,
  KVS(35-39, 3-5) = 1.00.

Run::

    python ml\\pipelines\\_osago_validate.py
    python ml\\pipelines\\_osago_validate.py --strict   # warnings → errors

Exit code 0 ⇔ all checks pass (or only warnings if not strict).
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
SEED_DIR = REPO_ROOT / "ml" / "data" / "seed"

# KBM classes ordered from worst to best, used for monotonicity checks.
KBM_CLASS_ORDER = ["M", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13"]
_KBM_CLASS_INDEX = {cls: idx for idx, cls in enumerate(KBM_CLASS_ORDER)}


# ----------------------------------------------------------------------------
# Reporting primitives
# ----------------------------------------------------------------------------


@dataclass
class CheckResult:
    """Outcome of a single rule applied to a single file."""

    file: str
    rule: str
    status: str  # "PASS", "FAIL", "WARN"
    detail: str = ""

    def is_failure(self, strict: bool) -> bool:
        if self.status == "FAIL":
            return True
        if strict and self.status == "WARN":
            return True
        return False


@dataclass
class Report:
    results: list[CheckResult] = field(default_factory=list)

    def add(self, file: str, rule: str, status: str, detail: str = "") -> None:
        self.results.append(CheckResult(file=file, rule=rule, status=status, detail=detail))

    def add_pass(self, file: str, rule: str, detail: str = "") -> None:
        self.add(file, rule, "PASS", detail)

    def add_fail(self, file: str, rule: str, detail: str) -> None:
        self.add(file, rule, "FAIL", detail)

    def add_warn(self, file: str, rule: str, detail: str) -> None:
        self.add(file, rule, "WARN", detail)

    def print_summary(self) -> None:
        by_file: dict[str, list[CheckResult]] = {}
        for r in self.results:
            by_file.setdefault(r.file, []).append(r)
        for file, rows in by_file.items():
            print(f"\n=== {file} ===")
            for r in rows:
                tag = {"PASS": "  ok", "WARN": "WARN", "FAIL": "FAIL"}[r.status]
                line = f"  [{tag}] {r.rule}"
                if r.detail and r.status != "PASS":
                    line += f"  — {r.detail}"
                print(line)
        n_pass = sum(1 for r in self.results if r.status == "PASS")
        n_warn = sum(1 for r in self.results if r.status == "WARN")
        n_fail = sum(1 for r in self.results if r.status == "FAIL")
        print(f"\nTotal: {n_pass} ok, {n_warn} warn, {n_fail} fail")


# ----------------------------------------------------------------------------
# Schema & loaders
# ----------------------------------------------------------------------------


def _check_schema(rep: Report, file: str, df: pd.DataFrame, expected: list[str]) -> bool:
    actual = list(df.columns)
    if actual != expected:
        rep.add_fail(file, "schema", f"got {actual}, expected {expected}")
        return False
    rep.add_pass(file, "schema", f"{len(expected)} columns, {len(df)} rows")
    return True


def _coerce_numeric(rep: Report, file: str, df: pd.DataFrame, columns: list[str]) -> bool:
    ok = True
    for col in columns:
        try:
            df[col] = pd.to_numeric(df[col], errors="raise")
        except (ValueError, TypeError) as exc:
            rep.add_fail(file, f"dtype[{col}]", str(exc))
            ok = False
    return ok


def _check_range(
    rep: Report,
    file: str,
    series: pd.Series,
    rule: str,
    lo: float,
    hi: float,
) -> None:
    bad = series[(series < lo) | (series > hi)]
    if len(bad):
        rep.add_fail(
            file,
            f"range[{rule}]",
            f"{len(bad)} value(s) outside [{lo}; {hi}]: {bad.head(5).tolist()}",
        )
    else:
        rep.add_pass(file, f"range[{rule}]", f"all in [{lo}; {hi}]")


def _check_unique(rep: Report, file: str, df: pd.DataFrame, key_cols: list[str]) -> None:
    dupes = df[df.duplicated(subset=key_cols, keep=False)]
    if len(dupes):
        sample = dupes[key_cols].head(5).to_dict(orient="records")
        rep.add_fail(file, f"unique[{','.join(key_cols)}]", f"{len(dupes)} duplicate row(s): {sample}")
    else:
        rep.add_pass(file, f"unique[{','.join(key_cols)}]", "no duplicates")


def _check_smoke(rep: Report, file: str, condition: bool, rule: str, detail: str) -> None:
    if condition:
        rep.add_pass(file, f"smoke[{rule}]", detail)
    else:
        rep.add_fail(file, f"smoke[{rule}]", detail)


# ----------------------------------------------------------------------------
# Per-file validators
# ----------------------------------------------------------------------------


def validate_base_tariffs(rep: Report) -> None:
    file = "osago_base_tariffs.csv"
    df = pd.read_csv(SEED_DIR / file, dtype=str)
    if not _check_schema(
        rep,
        file,
        df,
        ["category_id", "category_label", "vehicle_categories", "owner_type", "tb_min_rub", "tb_max_rub"],
    ):
        return
    if not _coerce_numeric(rep, file, df, ["tb_min_rub", "tb_max_rub"]):
        return

    _check_range(rep, file, df["tb_min_rub"], "tb_min_rub", 100, 5000)
    _check_range(rep, file, df["tb_max_rub"], "tb_max_rub", 3000, 20000)
    _check_unique(rep, file, df, ["category_id"])

    bad = df[df["tb_min_rub"] >= df["tb_max_rub"]]
    if len(bad):
        rep.add_fail(file, "min<max", f"{len(bad)} rows with tb_min >= tb_max")
    else:
        rep.add_pass(file, "min<max", f"{len(df)} rows ok")

    if len(df) != 12:
        rep.add_fail(file, "row_count", f"got {len(df)} rows, expected 12 (categories from Annex 1)")
    else:
        rep.add_pass(file, "row_count", "12 rows = all 12 categories from Annex 1")

    row22 = df[df["category_id"] == "2.2"]
    _check_smoke(
        rep,
        file,
        len(row22) == 1 and int(row22.iloc[0]["tb_min_rub"]) == 1399 and int(row22.iloc[0]["tb_max_rub"]) == 8665,
        "row_2.2",
        "TB(B/BE, физлицо) = 1399 / 8665 (the row used for our MVP)",
    )


def validate_kbm(rep: Report) -> None:
    file = "osago_kbm.csv"
    df = pd.read_csv(SEED_DIR / file, dtype=str)
    if not _check_schema(
        rep,
        file,
        df,
        [
            "kbm_class",
            "kbm_value",
            "class_after_no_claim",
            "class_after_1_claim",
            "class_after_2_claims",
            "class_after_3_claims",
            "class_after_more_than_3_claims",
        ],
    ):
        return
    if not _coerce_numeric(rep, file, df, ["kbm_value"]):
        return

    classes = df["kbm_class"].tolist()
    if classes != KBM_CLASS_ORDER:
        rep.add_fail(file, "class_order", f"got {classes}, expected {KBM_CLASS_ORDER}")
    else:
        rep.add_pass(file, "class_order", "M, 0..13 in canonical order")

    _check_range(rep, file, df["kbm_value"], "kbm_value", 0.46, 3.92)

    diffs = df["kbm_value"].diff().dropna()
    if (diffs >= 0).any():
        bad = df.loc[diffs[diffs >= 0].index, ["kbm_class", "kbm_value"]]
        rep.add_fail(file, "monotonic", f"KBM should strictly decrease as class grows; offending rows: {bad.to_dict(orient='records')}")
    else:
        rep.add_pass(file, "monotonic", "KBM strictly decreases M → 13")

    transition_cols = [
        "class_after_no_claim",
        "class_after_1_claim",
        "class_after_2_claims",
        "class_after_3_claims",
        "class_after_more_than_3_claims",
    ]
    bad_values: list[tuple[str, str, str]] = []
    for col in transition_cols:
        for cls, after in zip(df["kbm_class"], df[col]):
            if after not in _KBM_CLASS_INDEX:
                bad_values.append((cls, col, after))
    if bad_values:
        rep.add_fail(file, "transition_values", f"{len(bad_values)} unknown class(es): {bad_values[:5]}")
    else:
        rep.add_pass(file, "transition_values", "all 75 transition cells point to a known class")

    bad_ladder: list[tuple[str, list[str]]] = []
    for _, row in df.iterrows():
        seq = [row[c] for c in transition_cols]
        rank = [_KBM_CLASS_INDEX.get(s, -1) for s in seq]
        if any(rank[i] < rank[i + 1] for i in range(len(rank) - 1)):
            bad_ladder.append((row["kbm_class"], seq))
    if bad_ladder:
        rep.add_fail(file, "transition_ladder", f"more claims must never improve class; offenders: {bad_ladder[:5]}")
    else:
        rep.add_pass(file, "transition_ladder", "more claims never improves class")

    bad_more = df[df["class_after_more_than_3_claims"] != "M"]
    if len(bad_more):
        rep.add_fail(file, "ladder_more3=M", f">3 claims must always drop to class M; offenders: {bad_more['kbm_class'].tolist()}")
    else:
        rep.add_pass(file, "ladder_more3=M", "all 15 classes drop to M after >3 claims")

    cls13 = df[df["kbm_class"] == "13"].iloc[0]
    _check_smoke(rep, file, float(cls13["kbm_value"]) == 0.46, "class_13", "KBM(13) = 0.46 (the deepest discount)")
    cls4 = df[df["kbm_class"] == "4"].iloc[0]
    _check_smoke(rep, file, float(cls4["kbm_value"]) == 1.00, "class_4", "KBM(4) = 1.00 (the neutral class for new drivers)")
    clsM = df[df["kbm_class"] == "M"].iloc[0]
    _check_smoke(rep, file, float(clsM["kbm_value"]) == 3.92, "class_M", "KBM(M) = 3.92 (the worst-case multiplier)")


def validate_power(rep: Report) -> None:
    file = "osago_power.csv"
    df = pd.read_csv(SEED_DIR / file, dtype=str)
    if not _check_schema(
        rep,
        file,
        df,
        ["vehicle_family", "power_min_hp_excl", "power_max_hp_incl", "km_value"],
    ):
        return
    if not _coerce_numeric(rep, file, df, ["power_min_hp_excl", "power_max_hp_incl", "km_value"]):
        return

    families = set(df["vehicle_family"])
    if families != {"B_BE", "A_M_A1_B1"}:
        rep.add_fail(file, "families", f"got {families}, expected {{B_BE, A_M_A1_B1}}")
    else:
        rep.add_pass(file, "families", "B_BE + A_M_A1_B1")

    for fam, expected_cnt in [("B_BE", 6), ("A_M_A1_B1", 6)]:
        n = (df["vehicle_family"] == fam).sum()
        if n != expected_cnt:
            rep.add_fail(file, f"row_count[{fam}]", f"got {n}, expected {expected_cnt}")
        else:
            rep.add_pass(file, f"row_count[{fam}]", f"{n} bands")

    _check_range(rep, file, df["km_value"], "km_value", 0.6, 1.66)
    _check_unique(rep, file, df, ["vehicle_family", "power_min_hp_excl"])

    bad = df[df["power_min_hp_excl"] >= df["power_max_hp_incl"]]
    if len(bad):
        rep.add_fail(file, "min<max", f"{len(bad)} rows with min >= max")
    else:
        rep.add_pass(file, "min<max", "every band has min < max")

    for fam in ["B_BE", "A_M_A1_B1"]:
        sub = df[df["vehicle_family"] == fam].sort_values("power_min_hp_excl").reset_index(drop=True)
        gaps = []
        for i in range(len(sub) - 1):
            if float(sub.loc[i, "power_max_hp_incl"]) != float(sub.loc[i + 1, "power_min_hp_excl"]):
                gaps.append((fam, sub.loc[i].to_dict(), sub.loc[i + 1].to_dict()))
        if gaps:
            rep.add_fail(file, f"contiguous[{fam}]", f"{len(gaps)} gap(s) in power bands: {gaps[:2]}")
        else:
            rep.add_pass(file, f"contiguous[{fam}]", "bands are contiguous, cover the whole range")

    bbe_top = df[(df["vehicle_family"] == "B_BE") & (df["power_min_hp_excl"] == 150)]
    _check_smoke(
        rep,
        file,
        len(bbe_top) == 1 and float(bbe_top.iloc[0]["km_value"]) == 1.6,
        "B_BE_>150",
        "KM(B/BE, >150 hp) = 1.6 (most expensive power band for cars)",
    )


def validate_drivers(rep: Report) -> None:
    file = "osago_drivers.csv"
    df = pd.read_csv(SEED_DIR / file, dtype=str)
    if not _check_schema(rep, file, df, ["restricted", "owner_type", "ko_value"]):
        return
    if not _coerce_numeric(rep, file, df, ["ko_value"]):
        return

    if set(df["restricted"]) != {"true", "false"}:
        rep.add_fail(file, "restricted_values", f"got {set(df['restricted'])}, expected {{true, false}}")
    else:
        rep.add_pass(file, "restricted_values", "true/false")

    if set(df["owner_type"]) != {"physical", "legal"}:
        rep.add_fail(file, "owner_type_values", f"got {set(df['owner_type'])}, expected {{physical, legal}}")
    else:
        rep.add_pass(file, "owner_type_values", "physical/legal")

    _check_unique(rep, file, df, ["restricted", "owner_type"])
    _check_range(rep, file, df["ko_value"], "ko_value", 1.0, 3.5)

    if len(df) != 4:
        rep.add_fail(file, "row_count", f"got {len(df)} rows, expected 4 (2×2 grid)")
    else:
        rep.add_pass(file, "row_count", "4 rows = 2×2 grid")

    restricted_rows = df[df["restricted"] == "true"]
    if not (restricted_rows["ko_value"] == 1.0).all():
        rep.add_fail(file, "restricted=true -> KO=1", "ограниченный список всегда даёт КО=1")
    else:
        rep.add_pass(file, "restricted=true -> KO=1", "the discount for limited list is exactly 1.0")

    phys_unl = df[(df["restricted"] == "false") & (df["owner_type"] == "physical")].iloc[0]
    legal_unl = df[(df["restricted"] == "false") & (df["owner_type"] == "legal")].iloc[0]
    _check_smoke(rep, file, float(phys_unl["ko_value"]) == 3.16, "phys_unrestricted", "KO(физлицо, неогр.) = 3.16")
    _check_smoke(rep, file, float(legal_unl["ko_value"]) == 1.97, "legal_unrestricted", "KO(юрлицо, неогр.) = 1.97")


def validate_seasonal(rep: Report) -> None:
    file = "osago_seasonal.csv"
    df = pd.read_csv(SEED_DIR / file, dtype=str)
    if not _check_schema(
        rep,
        file,
        df,
        ["period_min_months_excl", "period_max_months_incl", "ks_value"],
    ):
        return
    if not _coerce_numeric(rep, file, df, ["period_min_months_excl", "period_max_months_incl", "ks_value"]):
        return

    if len(df) != 8:
        rep.add_fail(file, "row_count", f"got {len(df)} rows, expected 8 bands")
    else:
        rep.add_pass(file, "row_count", "8 period bands")

    _check_range(rep, file, df["ks_value"], "ks_value", 0.5, 1.0)
    _check_unique(rep, file, df, ["period_min_months_excl"])

    sub = df.sort_values("period_min_months_excl").reset_index(drop=True)
    diffs = sub["ks_value"].diff().dropna()
    if (diffs < 0).any():
        rep.add_fail(file, "monotonic", "KS should be non-decreasing as period grows")
    else:
        rep.add_pass(file, "monotonic", "KS non-decreasing 3 mo → 12 mo")

    gaps = []
    for i in range(len(sub) - 1):
        if float(sub.loc[i, "period_max_months_incl"]) != float(sub.loc[i + 1, "period_min_months_excl"]):
            gaps.append(i)
    if gaps:
        rep.add_fail(file, "contiguous", f"{len(gaps)} gap(s) at row(s) {gaps}")
    else:
        rep.add_pass(file, "contiguous", "bands are contiguous 0 → 12 months")

    full_year = df[(df["period_min_months_excl"] == 9) & (df["period_max_months_incl"] == 12)]
    _check_smoke(rep, file, len(full_year) == 1 and float(full_year.iloc[0]["ks_value"]) == 1.0, "full_year", "KS(>9 mo) = 1.0")


def validate_age_exp(rep: Report) -> None:
    file = "osago_age_exp.csv"
    df = pd.read_csv(SEED_DIR / file, dtype=str)
    if not _check_schema(
        rep,
        file,
        df,
        ["vehicle_family", "age_min_incl", "age_max_incl", "exp_min_years_incl", "exp_max_years_excl", "kvs_value"],
    ):
        return
    if not _coerce_numeric(rep, file, df, ["age_min_incl", "age_max_incl", "exp_min_years_incl", "exp_max_years_excl", "kvs_value"]):
        return

    families = set(df["vehicle_family"])
    if families != {"B_BE_other", "A_M_A1_B1"}:
        rep.add_fail(file, "families", f"got {families}, expected {{B_BE_other, A_M_A1_B1}}")
    else:
        rep.add_pass(file, "families", "B_BE_other + A_M_A1_B1")

    _check_range(rep, file, df["kvs_value"], "kvs_value", 0.7, 2.5)
    _check_unique(rep, file, df, ["vehicle_family", "age_min_incl", "exp_min_years_incl"])

    bad_age = df[df["age_min_incl"] > df["age_max_incl"]]
    if len(bad_age):
        rep.add_fail(file, "age_min<=max", f"{len(bad_age)} rows with age_min > age_max")
    else:
        rep.add_pass(file, "age_min<=max", "every age band ok")

    bad_exp = df[df["exp_min_years_incl"] >= df["exp_max_years_excl"]]
    if len(bad_exp):
        rep.add_fail(file, "exp_min<max", f"{len(bad_exp)} rows with exp_min >= exp_max")
    else:
        rep.add_pass(file, "exp_min<max", "every exp band ok")

    expected_age_bands = {
        "B_BE_other": [(18, 21), (22, 24), (25, 29), (30, 34), (35, 39), (40, 49), (50, 59), (60, 999)],
        "A_M_A1_B1": [(16, 21), (22, 24), (25, 29), (30, 34), (35, 39), (40, 49), (50, 59), (60, 999)],
    }
    for fam, bands in expected_age_bands.items():
        sub = df[df["vehicle_family"] == fam]
        actual = sorted(set(zip(sub["age_min_incl"], sub["age_max_incl"])))
        if actual != sorted(bands):
            rep.add_fail(file, f"age_bands[{fam}]", f"got {actual}, expected {sorted(bands)}")
        else:
            rep.add_pass(file, f"age_bands[{fam}]", f"{len(bands)} canonical age bands")

    expected_exp_cells_per_age = {
        18: 5, 16: 5, 22: 6, 25: 7, 30: 8, 35: 8, 40: 8, 50: 8, 60: 8,
    }
    for fam in ("B_BE_other", "A_M_A1_B1"):
        sub = df[df["vehicle_family"] == fam]
        violations = []
        for age_min, expected_n in expected_exp_cells_per_age.items():
            n = (sub["age_min_incl"] == age_min).sum()
            if n == 0:
                continue
            if n != expected_n:
                violations.append((age_min, n, expected_n))
        if violations:
            rep.add_fail(file, f"triangular[{fam}]", f"per-age cell counts off: {violations}")
        else:
            rep.add_pass(file, f"triangular[{fam}]", "expected number of cells per age band (5/6/7/8/8/8/8/8)")

    n_bbe = (df["vehicle_family"] == "B_BE_other").sum()
    n_amo = (df["vehicle_family"] == "A_M_A1_B1").sum()
    if n_bbe != 58 or n_amo != 58:
        rep.add_fail(file, "row_count", f"B_BE_other={n_bbe} (expected 58), A_M_A1_B1={n_amo} (expected 58)")
    else:
        rep.add_pass(file, "row_count", "58 + 58 = 116 cells")

    eth = df[(df["vehicle_family"] == "B_BE_other") & (df["age_min_incl"] == 35) & (df["exp_min_years_incl"] == 3)]
    _check_smoke(rep, file, len(eth) == 1 and float(eth.iloc[0]["kvs_value"]) == 1.00, "B_BE_35-39_3-5", "KVS(B/BE, 35-39, 3-5 yrs) = 1.00 (the neutral cell)")
    young = df[(df["vehicle_family"] == "B_BE_other") & (df["age_min_incl"] == 18) & (df["exp_min_years_incl"] == 0)]
    _check_smoke(rep, file, len(young) == 1 and float(young.iloc[0]["kvs_value"]) == 2.27, "B_BE_18-21_<1", "KVS(B/BE, 18-21, <1 yr) = 2.27 (the most expensive cell)")
    senior = df[(df["vehicle_family"] == "B_BE_other") & (df["age_min_incl"] == 60) & (df["exp_min_years_incl"] == 15)]
    _check_smoke(rep, file, len(senior) == 1 and float(senior.iloc[0]["kvs_value"]) == 0.83, "B_BE_60+_15+", "KVS(B/BE, >59, ≥15 yrs) = 0.83 (the cheapest cell)")


def validate_territory(rep: Report) -> None:
    file = "osago_territory_coefs.csv"
    df = pd.read_csv(SEED_DIR / file, dtype=str)
    if not _check_schema(
        rep,
        file,
        df,
        ["region_id", "region_name", "kt_capital_city", "kt_general", "kt_special", "source_ref"],
    ):
        return
    if not _coerce_numeric(rep, file, df, ["region_id", "kt_general", "kt_special"]):
        return

    if len(df) != 85:
        rep.add_fail(file, "row_count", f"got {len(df)} rows, expected 85 RF subjects")
    else:
        rep.add_pass(file, "row_count", "85 RF subjects")

    expected_ids = set(range(1, 86))
    actual_ids = set(int(x) for x in df["region_id"])
    if actual_ids != expected_ids:
        missing = expected_ids - actual_ids
        extra = actual_ids - expected_ids
        rep.add_fail(file, "region_id_coverage", f"missing={sorted(missing)}, extra={sorted(extra)}")
    else:
        rep.add_pass(file, "region_id_coverage", "region_id covers 1..85")

    regions_df = pd.read_csv(SEED_DIR / "regions.csv", dtype=str)
    seed_names = dict(zip(regions_df["id"].astype(int), regions_df["name"]))
    name_violations = []
    for _, row in df.iterrows():
        rid = int(row["region_id"])
        if seed_names.get(rid) != row["region_name"]:
            name_violations.append((rid, row["region_name"], seed_names.get(rid)))
    if name_violations:
        rep.add_fail(file, "region_name_match_regions.csv", f"{len(name_violations)} mismatch(es): {name_violations[:3]}")
    else:
        rep.add_pass(file, "region_name_match_regions.csv", "all 85 names match regions.csv")

    _check_range(rep, file, df["kt_general"], "kt_general", 0.5, 3.5)
    _check_range(rep, file, df["kt_special"], "kt_special", 0.5, 2.5)
    _check_unique(rep, file, df, ["region_id"])

    bad_special = df[df["kt_special"] > df["kt_general"] + 1e-9]
    if len(bad_special):
        offenders = bad_special[["region_name", "kt_general", "kt_special"]].head(5).to_dict(orient="records")
        rep.add_warn(file, "kt_special<=kt_general", f"{len(bad_special)} region(s) have kt_special > kt_general: {offenders}")
    else:
        rep.add_pass(file, "kt_special<=kt_general", "kt_special never exceeds kt_general")

    moscow = df[df["region_name"] == "Москва"].iloc[0]
    _check_smoke(rep, file, float(moscow["kt_general"]) == 1.80, "Москва", "KT(Москва) = 1.80")
    ufa = df[df["region_name"] == "Республика Башкортостан"].iloc[0]
    _check_smoke(rep, file, float(ufa["kt_general"]) == 1.56, "Уфа", "KT(Уфа = столица Башкортостана) = 1.56")
    nsk = df[df["region_name"] == "Новосибирская область"].iloc[0]
    _check_smoke(rep, file, float(nsk["kt_general"]) == 3.12, "Новосибирск", "KT(Новосибирск) = 3.12 (new max after 7204-У)")
    sev = df[df["region_name"] == "Севастополь"].iloc[0]
    _check_smoke(rep, file, float(sev["kt_general"]) == 0.82, "Севастополь", "KT(Севастополь) = 0.82 (single value for the federal city)")


# ----------------------------------------------------------------------------
# CLI entry point
# ----------------------------------------------------------------------------


VALIDATORS: list[Callable[[Report], None]] = [
    validate_base_tariffs,
    validate_kbm,
    validate_power,
    validate_drivers,
    validate_seasonal,
    validate_age_exp,
    validate_territory,
]


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--strict", action="store_true", help="treat warnings as failures")
    args = parser.parse_args()

    rep = Report()
    for fn in VALIDATORS:
        fn(rep)
    rep.print_summary()

    n_fail = sum(1 for r in rep.results if r.is_failure(strict=args.strict))
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
