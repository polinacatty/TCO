"""TcoService — orchestrates TCO calculation for POST /api/tco/calculate.

Responsibilities:

1. Map the *external* :class:`ProfileInput` schema to the *internal*
   :class:`app.domain.profile.UserProfile` (and ``CarSelection``).
2. Call :class:`TcoContextBuilder` to materialise a :class:`TcoContext`.
3. Run :class:`TcoCalculator`.
4. Map the resulting :class:`TcoResult` to the :class:`TcoCalculateResponse`
   API DTO, distributing components into year-by-year aggregates.
5. Attach the methodology disclaimer text (``meta.scope_disclaimer_ru`` +
   ``meta.excluded_items_ru`` / ``included_items_ru``) — single source of
   truth for the UI footer "Что не учтено".

The service knows nothing about HTTP — translation of
:class:`CarNotFoundError` to ``404`` happens in the router via the global
``AppError`` handler.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict
from datetime import UTC, datetime

from app.api.schemas.tco import (
    ComponentCode,
    ComponentResult,
    ProfileInput,
    TcoCalculateRequest,
    TcoCalculateResponse,
    TcoMeta,
    TcoYearly,
)
from app.application.disclaimer import (
    EXCLUDED_ITEMS_RU,
    INCLUDED_ITEMS_RU,
    SCOPE_DISCLAIMER_RU,
)
from app.core.exceptions import NotFoundError
from app.core.metrics import metrics_registry
from app.domain.profile import CarSelection, StoType, UserProfile
from app.domain.tco.calculator import TcoCalculator
from app.domain.tco.result import TcoResult
from app.repositories.context_builder import CarNotFoundError, TcoContextBuilder


class TcoService:
    """Orchestrates the full POST /api/tco/calculate use case."""

    def __init__(
        self,
        context_builder: TcoContextBuilder,
        calculator: TcoCalculator,
    ) -> None:
        self._builder = context_builder
        self._calculator = calculator

    async def calculate(
        self, request: TcoCalculateRequest, *, now: datetime | None = None
    ) -> TcoCalculateResponse:
        """Run the full calculation; raise :class:`NotFoundError` on bad id."""
        started = datetime.now(UTC)
        success = False
        try:
            profile = _to_user_profile(
                request.profile,
                request.horizon_years,
                request.options.include_kasko,
            )
            selection = CarSelection(
                modification_id=request.modification_id,
                msrp_override_rub=request.purchase_price_rub,
                year_of_manufacture=request.year_of_manufacture,
            )
            try:
                context = await self._builder.build(profile, selection, now=now)
            except CarNotFoundError as exc:
                raise NotFoundError(str(exc)) from exc

            result = self._calculator.compute(profile, selection, context)

            purchase_price = (
                request.purchase_price_rub
                if request.purchase_price_rub is not None
                else context.car.msrp_new_rub
            )
            response = _to_response(
                request=request,
                profile=profile,
                purchase_price_rub=purchase_price,
                result=result,
                computed_at=now or datetime.now(UTC),
            )
            success = True
            return response
        finally:
            metrics_registry.observe_service(
                operation="tco.calculate",
                success=success,
                duration_ms=(datetime.now(UTC) - started).total_seconds() * 1000.0,
            )


# --------------------------------------------------------------------------- #
# Mapping helpers                                                              #
# --------------------------------------------------------------------------- #


def _to_user_profile(
    profile: ProfileInput,
    horizon_years: int,
    options_kasko: bool | None,
) -> UserProfile:
    """Convert the external :class:`ProfileInput` into the domain :class:`UserProfile`.

    Defaults applied here:

    * ``driver_age`` defaults to 35 if absent (balanced preset).
    * ``driver_experience_years`` defaults to 10.
    * ``sto_type`` derived from ``use_dealer_service``.
    """
    include_kasko = options_kasko if options_kasko is not None else profile.include_kasko
    sto_type = StoType.DEALER if profile.use_dealer_service else StoType.INDEPENDENT
    return UserProfile(
        horizon_years=horizon_years,
        mileage_per_year_km=profile.annual_mileage_km,
        region_id=profile.region_id,
        sto_type=sto_type,
        include_kasko=include_kasko,
        driver_age=profile.driver_age if profile.driver_age is not None else 35,
        driver_experience_years=(
            profile.driver_experience_years
            if profile.driver_experience_years is not None
            else 10
        ),
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


def _component_amount(result: TcoResult, code: ComponentCode) -> int:
    return int(getattr(result, code))


def _profile_hash(profile: UserProfile, modification_id: int) -> str:
    """Stable SHA-1 fingerprint for caching / audit."""
    profile_payload = asdict(profile)
    profile_payload["sto_type"] = profile.sto_type.value
    payload: dict[str, object] = {
        "profile": profile_payload,
        "modification_id": modification_id,
    }
    blob = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha1(blob, usedforsecurity=False).hexdigest()[:16]


def _allocate_yearly(
    result: TcoResult, horizon_years: int
) -> list[TcoYearly]:
    """Split each component into per-year amounts.

    Rules:

    * ``transport_tax`` / ``osago`` / ``kasko`` — use the per-year vector
      from their breakdowns when available, else uniform.
    * ``fuel`` — use real 12-month buckets from the monthly forecast.
    * ``tyres`` — use real purchase years emitted by the component.
    * ``maintenance`` — uniform distribution in the current MVP.
    * ``depreciation`` — front-loaded uses the explicit ``annual_pcts``
      array to compute per-year residuals.
    """
    by_component_per_year: dict[ComponentCode, list[int]] = {}

    # transport_tax: yearly amounts surfaced by the component breakdown.
    tax_details = result.breakdowns["transport_tax"].details
    by_component_per_year["transport_tax"] = _safe_yearly_list(
        tax_details.get("yearly_amounts_rub"), horizon_years, result.transport_tax
    )

    # KASKO yearly amounts; if disabled, all zeros.
    kasko_details = result.breakdowns["kasko"].details
    by_component_per_year["kasko"] = _safe_yearly_list(
        kasko_details.get("yearly_amounts_rub"), horizon_years, result.kasko
    )

    # OSAGO — annual_premium × N
    osago_annual = result.breakdowns["osago"].details.get("annual_premium_rub")
    if isinstance(osago_annual, int):
        by_component_per_year["osago"] = [osago_annual] * horizon_years
    else:
        by_component_per_year["osago"] = _uniform(result.osago, horizon_years)

    # Maintenance — uniform allocation in MVP.
    by_component_per_year["maintenance"] = _uniform(result.maintenance, horizon_years)

    # Tyres — use purchase events from the component (e.g. first winter set in year 1).
    tyres_details = result.breakdowns["tyres"].details
    by_component_per_year["tyres"] = _safe_yearly_list(
        tyres_details.get("yearly_amounts_rub"), horizon_years, result.tyres
    )

    # Fuel — use the real year buckets emitted by the monthly forecast component.
    fuel_details = result.breakdowns["fuel"].details
    by_component_per_year["fuel"] = _safe_yearly_list(
        fuel_details.get("yearly_amounts_rub"), horizon_years, result.fuel
    )

    # Depreciation — derive per-year drop using the geometric rate vector.
    dep_details = result.breakdowns["depreciation"].details
    by_component_per_year["depreciation"] = _depreciation_yearly(
        dep_details, horizon_years, result.depreciation
    )

    yearly: list[TcoYearly] = []
    cumulative = 0
    for y in range(horizon_years):
        per: dict[ComponentCode, int] = {}
        year_total = 0
        for code in _COMPONENT_CODES:
            amount = by_component_per_year[code][y]
            per[code] = amount
            year_total += amount
        cumulative += year_total
        yearly.append(
            TcoYearly(
                year_index=y + 1,
                total_rub=year_total,
                by_component=per,
                cumulative_rub=cumulative,
            )
        )
    return yearly


def _safe_yearly_list(
    candidate: object, horizon: int, total: int
) -> list[int]:
    if isinstance(candidate, (list, tuple)) and len(candidate) == horizon:
        return [int(v) for v in candidate]
    return _uniform(total, horizon)


def _uniform(total: int, horizon: int) -> list[int]:
    """Distribute ``total`` evenly across ``horizon`` years, putting the
    remainder into the last year so the sum matches exactly."""
    if horizon <= 0:
        return []
    base = total // horizon
    leftover = total - base * horizon
    out = [base] * horizon
    out[-1] += leftover
    return out


def _depreciation_yearly(
    dep_details: Mapping[str, object], horizon: int, total: int
) -> list[int]:
    """Use ``annual_pcts`` + ``p0_rub`` to compute the per-year capital drop."""
    p0 = dep_details.get("p0_rub")
    annual = dep_details.get("annual_pcts")
    if not isinstance(p0, int) or not isinstance(annual, (list, tuple)) or len(annual) == 0:
        return _uniform(total, horizon)

    residual = float(p0)
    per_year: list[int] = []
    for r in annual[:horizon]:
        try:
            rate = float(r) / 100.0
        except (TypeError, ValueError):
            return _uniform(total, horizon)
        new_residual = residual * (1.0 - rate)
        per_year.append(int(residual - new_residual))
        residual = new_residual

    while len(per_year) < horizon:
        per_year.append(0)

    diff = total - sum(per_year)
    if per_year:
        per_year[-1] += diff
    return per_year


def _to_response(
    request: TcoCalculateRequest,
    profile: UserProfile,
    purchase_price_rub: int,
    result: TcoResult,
    computed_at: datetime,
) -> TcoCalculateResponse:
    total = result.total
    total_km = profile.mileage_per_year_km * profile.horizon_years

    components: dict[ComponentCode, ComponentResult] = {}
    for code in _COMPONENT_CODES:
        amount = _component_amount(result, code)
        share = (amount / total * 100.0) if total > 0 else 0.0
        components[code] = ComponentResult(
            total_rub=amount,
            share_pct=round(share, 2),
            details=dict(result.breakdowns[code].details),
        )

    # Predicted resale = purchase − depreciation, capped at 0.
    resale = max(0, purchase_price_rub - result.depreciation)
    per_km = round(total / total_km, 2) if total_km > 0 else 0.0

    return TcoCalculateResponse(
        modification_id=request.modification_id,
        horizon_years=request.horizon_years,
        purchase_price_rub=purchase_price_rub,
        predicted_resale_price_rub=resale,
        total_tco_rub=total,
        total_tco_per_km_rub=per_km,
        components=components,
        yearly=_allocate_yearly(result, request.horizon_years),
        meta=TcoMeta(
            profile_hash=_profile_hash(profile, request.modification_id),
            cached=False,
            computed_at=computed_at,
            models_versions={"sarima_fuel": "v1"},
            scope_disclaimer_ru=SCOPE_DISCLAIMER_RU,
            included_items_ru=list(INCLUDED_ITEMS_RU),
            excluded_items_ru=list(EXCLUDED_ITEMS_RU),
        ),
    )


__all__ = ["TcoService"]
