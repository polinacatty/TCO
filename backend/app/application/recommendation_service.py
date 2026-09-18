"""Application services for `/api/tco/recommend` and `/api/tco/compare`."""

from __future__ import annotations

from datetime import UTC, datetime

from app.api.schemas.recommendation import (
    CompareComponentDelta,
    CompareItem,
    CompareRequest,
    CompareResponse,
    CriterionContributionRead,
    RecommendItem,
    RecommendMetrics,
    RecommendRequest,
    RecommendResponse,
)
from app.api.schemas.tco import ComponentCode
from app.application.catalog_service import _to_modification_read
from app.core.exceptions import NotFoundError
from app.core.metrics import metrics_registry
from app.domain.ports import CatalogRepository
from app.domain.profile import CarSelection, StoType, UserProfile
from app.domain.recommendation.candidate import Candidate
from app.domain.recommendation.explainer import build_explanation
from app.domain.recommendation.filters import RecommendationFilters
from app.domain.recommendation.metrics import (
    coverage_ratio,
    diversity_at_k,
    ndcg_at_k,
    stability_at_k,
)
from app.domain.recommendation.result import RankedCar
from app.domain.recommendation.topsis import ParetoExtractor, TopsisRanker
from app.domain.recommendation.weights import RankingWeights, resolve_weights
from app.domain.tco.calculator import TcoCalculator
from app.application.tco_service import _allocate_yearly
from app.repositories.context_builder import CarNotFoundError, TcoContextBuilder


class RecommendationService:
    """Orchestrates recommendation and comparison use cases."""

    def __init__(
        self,
        catalog: CatalogRepository,
        context_builder: TcoContextBuilder,
        calculator: TcoCalculator,
    ) -> None:
        self._catalog = catalog
        self._builder = context_builder
        self._calculator = calculator
        self._ranker = TopsisRanker()
        self._pareto = ParetoExtractor()

    async def recommend(
        self, request: RecommendRequest, *, now: datetime | None = None
    ) -> RecommendResponse:
        started = datetime.now(UTC)
        success = False
        try:
            profile = _to_user_profile(
                request.profile,
                horizon_years=request.horizon_years,
                include_kasko=request.include_kasko,
            )
            filters = _to_filters(request)
            mods = await self._catalog.list_modifications_filtered(filters, limit=800)

            candidates: list[Candidate] = []
            for mod in mods:
                selection = CarSelection(modification_id=mod.id)
                try:
                    context = await self._builder.build(profile, selection, now=now)
                except CarNotFoundError:
                    continue
                tco = self._calculator.compute(profile, selection, context)
                price = float(mod.msrp_new_rub)
                depreciation_pct = (float(tco.depreciation) / price * 100.0) if price > 0 else 100.0
                candidates.append(
                    Candidate(
                        modification_id=mod.id,
                        make=mod.make_name,
                        model=mod.model_name,
                        generation=mod.generation_name,
                        body_type=mod.body_type,
                        segment=mod.segment,
                        fuel_type=mod.fuel_type,
                        drive=mod.drive,
                        transmission=mod.transmission,
                        tco_5y_rub=float(tco.total),
                        purchase_price_rub=price,
                        reliability_score=float(mod.reliability_score or 0.5),
                        depreciation_5y_pct=depreciation_pct,
                        power_hp=float(mod.power_hp),
                        cargo_volume_l=float(mod.cargo_volume_l or 0),
                    )
                )

            if not candidates:
                raise NotFoundError("no candidates after filters")

            weights = _resolve_weights(request)
            scores, decompositions = self._ranker.rank(candidates, weights)
            order = sorted(range(len(candidates)), key=lambda i: float(scores[i]), reverse=True)
            pareto_ids = set(self._pareto.extract(candidates))

            ranked: list[RankedCar] = []
            for rank, idx in enumerate(order[: request.top_n], start=1):
                c = candidates[idx]
                ranked.append(
                    RankedCar(
                        candidate=c,
                        rank=rank,
                        score=float(scores[idx]),
                        decomposition=decompositions[idx],
                        explanation_ru=build_explanation(c, decompositions[idx], candidates),
                    )
                )

            items: list[RecommendItem] = []
            for rc in ranked:
                mod_details = await self._catalog.get_modification_details(
                    rc.candidate.modification_id
                )
                if mod_details is None:
                    continue
                items.append(
                    RecommendItem(
                        rank=rc.rank,
                        score=round(rc.score, 6),
                        is_pareto_optimal=rc.candidate.modification_id in pareto_ids,
                        modification=_to_modification_read(mod_details),
                        tco_total_rub=int(rc.candidate.tco_5y_rub),
                        decomposition={
                            code: CriterionContributionRead(
                                value=val.value,
                                normalized=val.normalized,
                                contribution=val.contribution,
                            )
                            for code, val in rc.decomposition.items()
                        },
                        explanation_ru=rc.explanation_ru,
                    )
                )

            top_candidates = [rc.candidate for rc in ranked]
            metrics = RecommendMetrics(
                ndcg_at_k=(
                    round(ndcg_at_k(top_candidates, request.relevance_labels, k=request.top_n), 4)
                    if request.relevance_labels
                    else None
                ),
                diversity_at_k=diversity_at_k(top_candidates, k=request.top_n),
                coverage_ratio=round(
                    coverage_ratio(top_candidates, candidates, k=request.top_n),
                    4,
                ),
                stability_at_k=round(stability_at_k(candidates, weights, k=request.top_n), 4),
            )

            response = RecommendResponse(
                items=items,
                total_candidates=len(candidates),
                weights=weights.as_dict(),
                metrics=metrics,
                computed_at=now or datetime.now(UTC),
            )
            success = True
            return response
        finally:
            metrics_registry.observe_service(
                operation="recommendation.recommend",
                success=success,
                duration_ms=(datetime.now(UTC) - started).total_seconds() * 1000.0,
            )

    async def compare(
        self, request: CompareRequest, *, now: datetime | None = None
    ) -> CompareResponse:
        started = datetime.now(UTC)
        success = False
        try:
            profile = _to_user_profile(
                request.profile,
                horizon_years=request.horizon_years,
                include_kasko=request.include_kasko,
            )

            rows: list[tuple[CompareItem, int]] = []
            for mod_id in request.modification_ids:
                details = await self._catalog.get_modification_details(mod_id)
                if details is None:
                    raise NotFoundError(f"modification {mod_id} not found")
                selection = CarSelection(modification_id=mod_id)
                context = await self._builder.build(profile, selection, now=now)
                result = self._calculator.compute(profile, selection, context)
                components = {code: int(getattr(result, code)) for code in _COMPONENT_CODES}
                rows.append(
                    (
                        CompareItem(
                            modification=_to_modification_read(details),
                            total_tco_rub=result.total,
                            components_rub=components,
                            yearly=_allocate_yearly(result, request.horizon_years),
                            delta_total_rub_vs_first=0,
                            delta_components_vs_first=[],
                        ),
                        result.total,
                    )
                )

            baseline = rows[0][0]
            out: list[CompareItem] = []
            for item, _total in rows:
                deltas = [
                    CompareComponentDelta(
                        component=code,
                        delta_rub_vs_first=item.components_rub[code] - baseline.components_rub[code],
                    )
                    for code in _COMPONENT_CODES
                ]
                out.append(
                    item.model_copy(
                        update={
                            "delta_total_rub_vs_first": item.total_tco_rub - baseline.total_tco_rub,
                            "delta_components_vs_first": deltas,
                        }
                    )
                )
            response = CompareResponse(items=out, computed_at=now or datetime.now(UTC))
            success = True
            return response
        finally:
            metrics_registry.observe_service(
                operation="recommendation.compare",
                success=success,
                duration_ms=(datetime.now(UTC) - started).total_seconds() * 1000.0,
            )


def _to_filters(request: RecommendRequest) -> RecommendationFilters:
    f = request.filters
    return RecommendationFilters(
        purchase_price_min_rub=f.purchase_price_min_rub,
        purchase_price_max_rub=f.purchase_price_max_rub,
        body_types=tuple(f.body_types),
        drives=tuple(f.drives),
        fuel_types=tuple(f.fuel_types),
        transmissions=tuple(f.transmissions),
        segments=tuple(f.segments),
        year_min=f.year_min,
        year_max=f.year_max,
        power_min_hp=f.power_min_hp,
        power_max_hp=f.power_max_hp,
        cargo_min_l=f.cargo_min_l,
        seats_min=f.seats_min,
        body_clearance_min_mm=f.body_clearance_min_mm,
    )


def _resolve_weights(request: RecommendRequest) -> RankingWeights:
    explicit = request.weights.model_dump() if request.weights else None
    return resolve_weights(request.weights_preset, explicit)


def _to_user_profile(
    profile: object, horizon_years: int, include_kasko: bool | None
) -> UserProfile:
    from app.api.schemas.tco import ProfileInput

    if not isinstance(profile, ProfileInput):
        raise ValueError("profile must be ProfileInput")
    driver_age = profile.driver_age
    driver_experience_years = profile.driver_experience_years

    if driver_age is None and driver_experience_years is None:
        driver_age = 35
        driver_experience_years = 10
    elif driver_age is None and driver_experience_years is not None:
        # Keep experience from profile and infer a compatible age.
        driver_age = min(max(driver_experience_years + 16, 18), 99)
    elif driver_age is not None and driver_experience_years is None:
        # Keep age from profile and infer a compatible experience.
        driver_experience_years = min(10, max(driver_age - 16, 0))

    driver_age = min(max(driver_age, 18), 99)
    driver_experience_years = min(max(driver_experience_years, 0), 80)
    driver_experience_years = min(driver_experience_years, max(driver_age - 16, 0))

    return UserProfile(
        horizon_years=horizon_years,
        mileage_per_year_km=profile.annual_mileage_km,
        region_id=profile.region_id,
        sto_type=StoType.DEALER if profile.use_dealer_service else StoType.INDEPENDENT,
        include_kasko=include_kasko if include_kasko is not None else profile.include_kasko,
        driver_age=driver_age,
        driver_experience_years=driver_experience_years,
        osago_unlimited_drivers=profile.osago_unlimited_drivers,
    )


_COMPONENT_CODES: tuple[ComponentCode, ...] = (
    "depreciation",
    "fuel",
    "osago",
    "kasko",
    "transport_tax",
    "maintenance",
    "tyres",
)


__all__ = ["RecommendationService"]
