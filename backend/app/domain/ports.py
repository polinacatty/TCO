"""Domain-level repository interfaces (ports).

Each ``Protocol`` here is a thin abstraction over data access used by the
service layer to build a :class:`~app.domain.tco.inputs.TcoContext` and by
future use cases (catalog browsing, recommendation, scenarios).

Implementations live in :mod:`app.repositories` and are wired by the
FastAPI ``Depends`` chain. The domain layer **only** sees these Protocols.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol, runtime_checkable

from app.domain.profile import UserProfile
from app.domain.recommendation.filters import RecommendationFilters
from app.domain.scenario import SavedComparisonCarSnapshot, SavedComparisonSnapshot
from app.domain.tco.snapshots import (
    CarSnapshot,
    DepreciationRateSnapshot,
    FuelPriceForecastSnapshot,
    GenerationSnapshot,
    KaskoRateSnapshot,
    LaborRateSnapshot,
    LuxuryCarSnapshot,
    MakeSnapshot,
    MileagePenaltySnapshot,
    ModelSnapshot,
    ModificationListItemSnapshot,
    OsagoCoefficientsSnapshot,
    PartsCostSnapshot,
    RegionSnapshot,
    ServicePlanOpSnapshot,
    TirePriceSnapshot,
    TireSizeSnapshot,
    TransportTaxRateSnapshot,
)
from app.domain.user import FavoriteModificationSnapshot, UserProfileSnapshot, UserSnapshot


@runtime_checkable
class CatalogRepository(Protocol):
    """Read access to the car catalog."""

    async def get_modification(self, modification_id: int) -> CarSnapshot | None: ...

    async def list_tire_sizes(
        self, modification_id: int
    ) -> Sequence[TireSizeSnapshot]: ...

    async def list_tire_prices(
        self, size_codes: Sequence[str]
    ) -> Sequence[TirePriceSnapshot]: ...

    # ----- browse / search (read-only views for the catalog API) ---------
    async def list_regions(self) -> Sequence[RegionSnapshot]: ...

    async def list_makes(self, q: str | None = None) -> Sequence[MakeSnapshot]: ...

    async def list_models_by_make(self, make_id: int) -> Sequence[ModelSnapshot]: ...

    async def list_generations_by_model(
        self, model_id: int
    ) -> Sequence[GenerationSnapshot]: ...

    async def list_modifications_by_generation(
        self, generation_id: int
    ) -> Sequence[ModificationListItemSnapshot]: ...

    async def get_modification_details(
        self, modification_id: int
    ) -> ModificationListItemSnapshot | None: ...

    async def list_modifications_filtered(
        self,
        filters: RecommendationFilters,
        *,
        limit: int = 500,
    ) -> Sequence[ModificationListItemSnapshot]: ...


@runtime_checkable
class PricingRepository(Protocol):
    """Read access to pricing reference tables."""

    async def get_transport_tax_rates(
        self, region_id: int, vehicle_type: str = "passenger"
    ) -> Sequence[TransportTaxRateSnapshot]: ...

    async def find_luxury_matches(
        self, make_name: str, model_name: str, engine_volume_l: Decimal | None
    ) -> Sequence[LuxuryCarSnapshot]: ...

    async def resolve_osago_coefficients(
        self, profile: UserProfile, power_hp: int
    ) -> OsagoCoefficientsSnapshot: ...

    async def list_depreciation_rates(self) -> Sequence[DepreciationRateSnapshot]: ...

    async def list_mileage_penalties(self) -> Sequence[MileagePenaltySnapshot]: ...

    async def list_kasko_rates(self) -> Sequence[KaskoRateSnapshot]: ...

    async def list_service_plan_ops(
        self, generation_id: int
    ) -> Sequence[ServicePlanOpSnapshot]: ...

    async def list_parts_costs(
        self, operation_ids: Sequence[int], brand_segment: str
    ) -> Sequence[PartsCostSnapshot]: ...

    async def get_labor_rate(
        self, region_id: int, sto_type: str
    ) -> LaborRateSnapshot | None: ...


@runtime_checkable
class FuelRepository(Protocol):
    """Read access to the materialised SARIMA forecast (and the RU_AVG fallback)."""

    async def list_fuel_price_forecast(
        self,
        region_id: int,
        fuel_type: str,
        month_from: date,
        month_to: date,
    ) -> Sequence[FuelPriceForecastSnapshot]: ...


@runtime_checkable
class AuthRepository(Protocol):
    """Read/write storage for users, profiles and refresh sessions."""

    async def get_user_by_email(self, email: str) -> UserSnapshot | None: ...

    async def get_user_by_id(self, user_id: str) -> UserSnapshot | None: ...

    async def create_user(
        self, *, email: str, password_hash: str, pdn_consent: bool
    ) -> UserSnapshot: ...

    async def save_refresh_token(
        self, *, user_id: str, token_hash: str, expires_at: datetime
    ) -> None: ...

    async def validate_refresh_token(self, token_hash: str) -> UserSnapshot | None: ...

    async def revoke_refresh_token(self, token_hash: str) -> None: ...

    async def revoke_all_refresh_tokens_for_user(self, user_id: str) -> None: ...

    async def save_password_reset_token(
        self, *, user_id: str, token_hash: str, expires_at: datetime
    ) -> None: ...

    async def consume_password_reset_token(self, token_hash: str) -> UserSnapshot | None: ...

    async def update_user_password(self, user_id: str, password_hash: str) -> None: ...

    async def get_profile(self, user_id: str) -> UserProfileSnapshot | None: ...

    async def upsert_profile(
        self,
        *,
        user_id: str,
        profile: UserProfileSnapshot,
    ) -> UserProfileSnapshot: ...

    async def delete_profile(self, user_id: str) -> None: ...

    async def list_favorites(self, user_id: str) -> Sequence[FavoriteModificationSnapshot]: ...

    async def add_favorite(self, *, user_id: str, modification_id: int) -> None: ...

    async def remove_favorite(self, *, user_id: str, modification_id: int) -> None: ...


@runtime_checkable
class ScenarioRepository(Protocol):
    """Persistence for saved comparisons."""

    async def list_comparisons(
        self,
        *,
        user_id: str,
        limit: int,
        cursor_created_at: datetime | None = None,
        cursor_id: str | None = None,
    ) -> Sequence[SavedComparisonSnapshot]: ...

    async def get_comparison(
        self, *, user_id: str, comparison_id: str
    ) -> SavedComparisonSnapshot | None: ...

    async def get_comparison_by_signature(
        self, *, user_id: str, signature: str
    ) -> SavedComparisonSnapshot | None: ...

    async def create_comparison(
        self,
        comparison: SavedComparisonSnapshot,
        cars: Sequence[SavedComparisonCarSnapshot],
    ) -> SavedComparisonSnapshot: ...

    async def delete_comparison(self, *, user_id: str, comparison_id: str) -> None: ...

    async def list_comparison_cars(self, comparison_id: str) -> Sequence[SavedComparisonCarSnapshot]: ...

    async def list_comparison_ids_by_signature(
        self,
        *,
        user_id: str,
        signatures: Sequence[str],
    ) -> Sequence[str]: ...


__all__ = [
    "CatalogRepository",
    "PricingRepository",
    "FuelRepository",
    "AuthRepository",
    "ScenarioRepository",
]
