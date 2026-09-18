"""RecommendationService — оркестратор pipeline.

    catalog → filters → compute dynamic criteria (TCO, deprec_pct) → strategy.rank → top-K → decompose
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import reduce
from typing import Any, Optional

import pandas as pd

from .criteria import CriterionSpec, DEFAULT_CRITERIA
from .decomposition import decompose
from .filters import Filter, build_filters_from_profile
from .profile import UserProfile
from .strategies import RankingStrategy, TopsisStrategy
from .tco_calc import TCOCalculator, SEGMENT_11_TO_6


@dataclass
class RecommendationResult:
    top: pd.DataFrame
    decompositions: list[dict[str, Any]]
    total_candidates: int
    n_after_filters: int
    strategy_name: str
    profile_summary: dict[str, Any]
    reason: Optional[str] = None

    @classmethod
    def empty(cls, total_candidates: int, reason: str, profile_summary: dict[str, Any]) -> "RecommendationResult":
        return cls(
            top=pd.DataFrame(),
            decompositions=[],
            total_candidates=total_candidates,
            n_after_filters=0,
            strategy_name="",
            profile_summary=profile_summary,
            reason=reason,
        )


class RecommendationService:
    """End-to-end recommendation pipeline."""

    def __init__(
        self,
        tco_calc: TCOCalculator,
        strategy: Optional[RankingStrategy] = None,
        criteria: Optional[list[CriterionSpec]] = None,
    ):
        self.tco_calc = tco_calc
        self.strategy = strategy or TopsisStrategy()
        self.criteria = criteria or DEFAULT_CRITERIA

    def _augment_catalog(self, catalog: pd.DataFrame) -> pd.DataFrame:
        """Resolve make_id, model_id, segment, body_type, brand_name, model_name
        by joining with car_generations / car_models / car_makes; also exposes
        purchase_price = msrp_new_rub.
        """
        df = catalog.copy()

        if "modification_id" not in df.columns and "id" in df.columns:
            df["modification_id"] = df["id"]

        gens = self.tco_calc.seed["generations"][["id", "model_id", "year_from", "year_to"]].rename(
            columns={"id": "generation_id"}
        )
        if "model_id" not in df.columns:
            df = df.merge(gens, on="generation_id", how="left")

        models = self.tco_calc.seed["models"][["id", "make_id", "name", "segment", "body_type"]].rename(
            columns={"id": "model_id", "name": "model_name"}
        )
        if "segment" not in df.columns or "make_id" not in df.columns:
            df = df.merge(models, on="model_id", how="left", suffixes=("", "_m"))
            for c in ("make_id", "segment", "body_type", "model_name"):
                alt = f"{c}_m"
                if alt in df.columns and c in df.columns:
                    df[c] = df[c].fillna(df[alt])
                    df = df.drop(columns=[alt])

        makes = self.tco_calc.seed["makes"][["id", "name", "brand_tier", "country"]].rename(
            columns={"id": "make_id", "name": "make_name"}
        )
        if "make_name" not in df.columns:
            df = df.merge(makes, on="make_id", how="left", suffixes=("", "_mk"))
            for c in ("make_name", "brand_tier", "country"):
                alt = f"{c}_mk"
                if alt in df.columns and c in df.columns:
                    df[c] = df[c].fillna(df[alt])
                    df = df.drop(columns=[alt])

        if "purchase_price" not in df.columns:
            df["purchase_price"] = df["msrp_new_rub"]

        return df

    def _apply_filters(self, df: pd.DataFrame, filters: list[Filter]) -> pd.DataFrame:
        if not filters:
            return df
        return reduce(lambda d, f: f.apply(d), filters, df)

    def _compute_dynamic_criteria(
        self, candidates: pd.DataFrame, profile: UserProfile,
    ) -> pd.DataFrame:
        """Add tco_5y and depreciation_5y_pct columns (computed under this profile)."""
        if len(candidates) == 0:
            for col in ("tco_5y", "depreciation_5y_pct"):
                if col not in candidates.columns:
                    candidates = candidates.copy()
                    candidates[col] = []
            return candidates

        tco_values = []
        deprec_pcts = []
        for _, row in candidates.iterrows():
            seg_raw = row.get("segment")
            tco = self.tco_calc.compute(row, profile, car_model_segment=seg_raw)
            tco_values.append(tco.total)
            deprec_pcts.append(
                self.tco_calc.compute_depreciation_pct(
                    row,
                    horizon_years=profile.horizon_years,
                    mileage_per_year_km=profile.mileage_per_year_km,
                    car_model_segment=seg_raw,
                )
            )
        result = candidates.copy()
        result["tco_5y"] = tco_values
        result["depreciation_5y_pct"] = deprec_pcts
        return result

    def recommend(
        self,
        catalog: pd.DataFrame,
        profile: UserProfile,
        filters: Optional[list[Filter]] = None,
        top_k: int = 10,
    ) -> RecommendationResult:
        profile_summary = {
            "budget_rub": profile.budget_rub,
            "region_id": profile.region_id,
            "mileage_per_year_km": profile.mileage_per_year_km,
            "horizon_years": profile.horizon_years,
            "weights": profile.resolve_weights(),
        }

        catalog = self._augment_catalog(catalog)

        filt = filters if filters is not None else build_filters_from_profile(profile)
        filtered = self._apply_filters(catalog, filt)

        if len(filtered) == 0:
            return RecommendationResult.empty(
                total_candidates=len(catalog),
                reason=(
                    f"no candidates after filters (catalog={len(catalog)}, "
                    f"applied={len(filt)} filters)"
                ),
                profile_summary=profile_summary,
            )

        with_criteria = self._compute_dynamic_criteria(filtered, profile)

        weights = profile.resolve_weights()

        ranked = self.strategy.rank(with_criteria, weights, self.criteria)

        top = ranked.head(top_k).copy()

        decompositions = decompose(top, weights, self.criteria, strategy_name=self.strategy.name)

        return RecommendationResult(
            top=top,
            decompositions=decompositions,
            total_candidates=len(catalog),
            n_after_filters=len(filtered),
            strategy_name=self.strategy.name,
            profile_summary=profile_summary,
        )
