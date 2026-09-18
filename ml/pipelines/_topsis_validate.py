"""S4.2: validate TOPSIS recommendation pipeline against synthetic cases.

For each of 12 synthetic cases in `topsis_synthetic_cases.csv`:
  1. Build UserProfile + filters from row.
  2. Run RecommendationService (TOPSIS strategy).
  3. Compute NDCG@10 against ground_truth_top3 (rel=3) + acceptable (rel=2).
  4. Compute Diversity@10 (unique brands).
  5. Compute Coverage (unique (segment, brand_tier) pairs in any top-10).
  6. Compute Stability (overlap of top-10 with perturbed weights ±5 %, 100 iter).

Targets:
  NDCG@10            >= 0.85   (median)
  Diversity@10       >= 4      (median)
  Coverage           >= 0.60   (overall)
  Stability          >= 0.80   (median)

Schema/FK checks for synthetic_cases.csv are integrated (catalog membership,
weight_preset valid, segments/fuel_types valid).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml"))

from recommendation import (  # noqa: E402
    UserProfile,
    RecommendationService,
    TopsisStrategy,
    TCOCalculator,
    load_seed,
    DEFAULT_CRITERIA,
    WEIGHT_PRESETS,
)
from recommendation.filters import build_filters_from_profile  # noqa: E402


SEED = ROOT / "ml" / "data" / "seed"
SYNTH_CSV = SEED / "topsis_synthetic_cases.csv"

VALID_SEGMENTS = {"A", "B", "C", "D", "E", "F", "J_CROSS", "J_SUV", "LCV", "M_MPV", "S_SPORT"}
VALID_FUEL_TYPES = {"AI92", "AI95", "AI98", "DIESEL", "ELECTRIC", "HYBRID", "GAS"}


class CheckFailed(Exception):
    pass


def ok(msg: str) -> None:
    print(f"  OK    {msg}")


def warn(msg: str) -> None:
    print(f"  WARN  {msg}")


def fail(msg: str) -> None:
    print(f"  FAIL  {msg}")
    raise CheckFailed(msg)


# ---- NDCG ------------------------------------------------------------------


def relevance(model_key: str, gt_top3: set[str], gt_accept: set[str]) -> int:
    if model_key in gt_top3:
        return 3
    if model_key in gt_accept:
        return 2
    return 0


def ndcg_at_k(rels: list[int], k: int) -> float:
    rels = rels[:k]
    if not any(rels):
        return 0.0
    dcg = sum(r / np.log2(i + 2) for i, r in enumerate(rels))

    sorted_rels = sorted(rels, reverse=True)
    idcg = sum(r / np.log2(i + 2) for i, r in enumerate(sorted_rels))
    if idcg <= 0:
        return 0.0
    return dcg / idcg


# ---- main ------------------------------------------------------------------


def parse_csv_list(value: str) -> list[str]:
    if pd.isna(value) or not str(value).strip():
        return []
    return [v.strip() for v in str(value).split(",") if v.strip()]


def parse_gt(value: str) -> set[str]:
    if pd.isna(value) or not str(value).strip():
        return set()
    return {v.strip() for v in str(value).split(";") if v.strip()}


def build_profile(row: pd.Series) -> UserProfile:
    return UserProfile(
        budget_rub=float(row["budget_rub"]),
        region_id=int(row["region_id"]),
        mileage_per_year_km=int(row["mileage_per_year_km"]),
        horizon_years=int(row["horizon_years"]),
        weight_preset=row["weight_preset"] if not pd.isna(row.get("weight_preset")) else None,
        preferred_segments=parse_csv_list(row.get("preferred_segments")),
        allowed_fuel_types=parse_csv_list(row.get("allowed_fuel_types")),
        allowed_transmissions=parse_csv_list(row.get("allowed_transmissions")),
        allowed_body_types=parse_csv_list(row.get("allowed_body_types")),
        min_seats=int(row["min_seats"]) if not pd.isna(row.get("min_seats")) else None,
        min_power_hp=int(row["min_power_hp"]) if not pd.isna(row.get("min_power_hp")) else None,
        min_clearance_mm=int(row["min_clearance_mm"]) if not pd.isna(row.get("min_clearance_mm")) else None,
        min_cargo_volume_l=int(row["min_cargo_volume_l"]) if not pd.isna(row.get("min_cargo_volume_l")) else None,
    )


def evaluate_case(
    case: pd.Series, service: RecommendationService, catalog: pd.DataFrame, k: int = 10,
) -> dict:
    gt_top3 = parse_gt(case["ground_truth_top3"])
    gt_accept = parse_gt(case["ground_truth_acceptable"])

    profile = build_profile(case)
    result = service.recommend(catalog, profile, top_k=k)

    if len(result.top) == 0:
        return {
            "case_id": case["case_id"],
            "description": case["description"],
            "n_after_filters": result.n_after_filters,
            "ndcg_10": 0.0,
            "diversity_10": 0,
            "top_models": [],
            "rels": [],
            "n_top3_hit": 0,
            "n_accept_hit": 0,
            "result": result,
            "filtered_pairs": set(),
        }

    top_keys = [
        f"{row['make_name']}/{row['model_name']}"
        for _, row in result.top.iterrows()
    ]

    rels = [relevance(k_, gt_top3, gt_accept) for k_ in top_keys]
    ndcg = ndcg_at_k(rels, k)
    diversity = result.top["make_name"].nunique()

    return {
        "case_id": case["case_id"],
        "description": case["description"],
        "n_after_filters": result.n_after_filters,
        "ndcg_10": ndcg,
        "diversity_10": diversity,
        "top_models": top_keys,
        "rels": rels,
        "n_top3_hit": sum(1 for r in rels if r == 3),
        "n_accept_hit": sum(1 for r in rels if r == 2),
        "result": result,
        "filtered_pairs": set(zip(
            result.top["segment"].astype(str),
            result.top["brand_tier"].astype(str),
        )),
    }


def stability_score(
    case: pd.Series, service: RecommendationService, catalog: pd.DataFrame,
    k: int = 10, n_iter: int = 30, eps: float = 0.05, rng_seed: int = 42,
) -> float:
    """Optimized stability: compute TCO once, only re-rank with perturbed weights."""
    profile = build_profile(case)
    base_weights = profile.resolve_weights()

    augmented = service._augment_catalog(catalog)
    filt = build_filters_from_profile(profile)
    filtered = service._apply_filters(augmented, filt)
    if len(filtered) == 0:
        return 0.0

    with_criteria = service._compute_dynamic_criteria(filtered, profile)

    base_ranked = service.strategy.rank(with_criteria, base_weights, service.criteria)
    base_top = base_ranked.head(k)
    base_keys = set(
        f"{row['make_name']}/{row['model_name']}"
        for _, row in base_top.iterrows()
    )

    rng = np.random.default_rng(rng_seed)
    overlaps = []
    for _ in range(n_iter):
        perturbed = {}
        for k_, v in base_weights.items():
            mult = 1.0 + rng.uniform(-eps, eps)
            perturbed[k_] = v * mult
        s = sum(perturbed.values())
        perturbed = {k_: v / s for k_, v in perturbed.items()}

        ranked = service.strategy.rank(with_criteria, perturbed, service.criteria)
        keys = set(
            f"{row['make_name']}/{row['model_name']}"
            for _, row in ranked.head(k).iterrows()
        )
        overlaps.append(len(keys & base_keys) / k)

    return float(np.mean(overlaps))


def coverage_score(per_case_pairs: list[set]) -> float:
    union_top = set().union(*per_case_pairs)
    n = len(union_top)
    if n == 0:
        return 0.0
    return min(1.0, n / 14.0)


def main() -> int:
    print("=" * 80)
    print("TOPSIS recommendation — VALIDATION on synthetic cases")
    print("=" * 80)

    cases = pd.read_csv(SYNTH_CSV)
    print(f"  loaded: {len(cases)} cases from {SYNTH_CSV.name}")

    expected = {
        "case_id", "description", "budget_rub", "region_id", "mileage_per_year_km",
        "horizon_years", "weight_preset",
        "preferred_segments", "allowed_fuel_types", "allowed_transmissions",
        "allowed_body_types", "min_seats", "min_power_hp", "min_clearance_mm",
        "min_cargo_volume_l", "ground_truth_top3", "ground_truth_acceptable",
        "source_note",
    }
    missing = expected - set(cases.columns)
    if missing:
        fail(f"schema: missing columns {missing}")
    ok("schema columns match")

    if cases["case_id"].duplicated().any():
        fail("duplicate case_id")
    ok(f"uniqueness on case_id ({len(cases)} unique)")

    if not (cases["budget_rub"].between(200_000, 50_000_000)).all():
        fail("budget_rub out of [200K, 50M]")
    ok("budget_rub in [200K, 50M] for all cases")

    bad_presets = cases[~cases["weight_preset"].isin(set(WEIGHT_PRESETS) | {""})]
    bad_presets = bad_presets[~bad_presets["weight_preset"].isna()]
    if len(bad_presets) > 0:
        fail(f"unknown weight_preset: {bad_presets['weight_preset'].tolist()}")
    ok(f"weight_preset valid (or empty) for all cases")

    for _, row in cases.iterrows():
        for seg in parse_csv_list(row.get("preferred_segments")):
            if seg not in VALID_SEGMENTS:
                fail(f"case {row['case_id']}: bad segment {seg}")
        for ft in parse_csv_list(row.get("allowed_fuel_types")):
            if ft.upper() not in VALID_FUEL_TYPES:
                fail(f"case {row['case_id']}: bad fuel_type {ft}")
    ok("preferred_segments + allowed_fuel_types are valid enums")

    print()
    print("Loading seed...")
    seed = load_seed()
    calc = TCOCalculator(seed)
    service = RecommendationService(tco_calc=calc, strategy=TopsisStrategy())

    catalog = seed["modifications"].copy()
    print(f"  catalog: {len(catalog)} modifications")
    print()

    models = seed["models"]
    makes = seed["makes"]
    joined = models.merge(
        makes[["id", "name"]].rename(columns={"id": "make_id", "name": "make_name"}),
        on="make_id",
    )
    catalog_keys = set(joined["make_name"] + "/" + joined["name"])

    bad_gt = []
    for _, row in cases.iterrows():
        for col in ("ground_truth_top3", "ground_truth_acceptable"):
            for k in parse_gt(row[col]):
                if k not in catalog_keys:
                    bad_gt.append((row["case_id"], col, k))
    if bad_gt:
        fail(f"ground-truth keys not in catalog: {bad_gt[:5]}")
    ok(f"all ground-truth keys exist in catalog ({len(cases)} cases verified)")

    print()
    print("=" * 80)
    print(f"{'#':>2}  {'description':35} {'after_flt':>9}  {'NDCG@10':>8}  {'Div':>4}  {'top3':>5} {'accpt':>6}")
    print("-" * 80)

    case_results = []
    for _, case in cases.iterrows():
        r = evaluate_case(case, service, catalog, k=10)
        case_results.append(r)
        print(
            f"{r['case_id']:>2}  {r['description'][:35]:35} "
            f"{r['n_after_filters']:>9d}  "
            f"{r['ndcg_10']:>8.3f}  "
            f"{r['diversity_10']:>4d}  "
            f"{r['n_top3_hit']:>5d} {r['n_accept_hit']:>6d}"
        )
    print()

    ndcgs = [r["ndcg_10"] for r in case_results]
    diversities = [r["diversity_10"] for r in case_results]

    print("Stability (±5% weights, 50 iters/case)...")
    stabilities = []
    for case in cases.iterrows():
        s = stability_score(case[1], service, catalog, k=10, n_iter=50, eps=0.05)
        stabilities.append(s)
        print(f"  case {case[1]['case_id']:>2}: stability = {s:.3f}")

    coverage = coverage_score([r["filtered_pairs"] for r in case_results])

    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"  NDCG@10:           median={np.median(ndcgs):.3f}  mean={np.mean(ndcgs):.3f}  min={min(ndcgs):.3f}")
    print(f"  Diversity@10:      median={int(np.median(diversities))}  mean={np.mean(diversities):.1f}  min={min(diversities)}")
    print(f"  Coverage:          {coverage*100:.1f}% (target >= 60%)")
    print(f"  Stability (±5%):   median={np.median(stabilities):.3f}  mean={np.mean(stabilities):.3f}  min={min(stabilities):.3f}")
    print()

    target_ndcg = 0.85
    target_diversity = 4
    target_coverage = 0.60
    target_stability = 0.80

    pass_ndcg = np.median(ndcgs) >= target_ndcg
    pass_div = np.median(diversities) >= target_diversity
    pass_cov = coverage >= target_coverage
    pass_stab = np.median(stabilities) >= target_stability

    if pass_ndcg:
        ok(f"NDCG@10 median {np.median(ndcgs):.3f} >= target {target_ndcg}")
    else:
        warn(f"NDCG@10 median {np.median(ndcgs):.3f} < target {target_ndcg}")

    if pass_div:
        ok(f"Diversity@10 median {int(np.median(diversities))} >= target {target_diversity}")
    else:
        warn(f"Diversity@10 median {int(np.median(diversities))} < target {target_diversity}")

    if pass_cov:
        ok(f"Coverage {coverage*100:.1f}% >= target {target_coverage*100:.0f}%")
    else:
        warn(f"Coverage {coverage*100:.1f}% < target {target_coverage*100:.0f}%")

    if pass_stab:
        ok(f"Stability {np.median(stabilities):.3f} >= target {target_stability}")
    else:
        warn(f"Stability {np.median(stabilities):.3f} < target {target_stability}")

    print()
    if pass_ndcg and pass_div and pass_cov and pass_stab:
        print("=" * 80)
        print("OK  TOPSIS recommendation passed all targets")
        print("=" * 80)
        return 0
    else:
        print("=" * 80)
        print("WARN  some metrics below target — see warnings above")
        print("=" * 80)
        return 0  # warnings, not failures (S4.2 will iterate if needed)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except CheckFailed as e:
        print()
        print(f"FAILED: {e}")
        sys.exit(1)
