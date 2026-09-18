from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from app.domain.profile import UserProfile
from app.domain.recommendation.filters import RecommendationFilters, apply_filters
from app.domain.scenario import SavedScenarioSnapshot, ScenarioCarSnapshot
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
from app.domain.user import UserProfileSnapshot, UserSnapshot


class StubCatalogRepository:

    def __init__(
        self,
        *,
        cars: dict[int, CarSnapshot] | None = None,
        modifications: dict[int, ModificationListItemSnapshot] | None = None,
        tire_sizes: dict[int, Sequence[TireSizeSnapshot]] | None = None,
        tire_prices: Sequence[TirePriceSnapshot] = (),
        regions: Sequence[RegionSnapshot] = (),
        makes: Sequence[MakeSnapshot] = (),
        models_by_make: dict[int, Sequence[ModelSnapshot]] | None = None,
        generations_by_model: dict[int, Sequence[GenerationSnapshot]] | None = None,
        modifications_by_generation: dict[
            int, Sequence[ModificationListItemSnapshot]
        ]
        | None = None,
    ) -> None:
        self._cars = cars or {}
        self._modifications = modifications or {}
        self._tire_sizes = tire_sizes or {}
        self._tire_prices = list(tire_prices)
        self._regions = list(regions)
        self._makes = list(makes)
        self._models_by_make = models_by_make or {}
        self._generations_by_model = generations_by_model or {}
        self._modifications_by_generation = modifications_by_generation or {}

    async def get_modification(self, modification_id: int) -> CarSnapshot | None:
        return self._cars.get(modification_id)

    async def list_tire_sizes(
        self, modification_id: int
    ) -> Sequence[TireSizeSnapshot]:
        return self._tire_sizes.get(modification_id, ())

    async def list_tire_prices(
        self, size_codes: Sequence[str]
    ) -> Sequence[TirePriceSnapshot]:
        wanted = set(size_codes)
        return [p for p in self._tire_prices if p.size_code in wanted]

    async def list_regions(self) -> Sequence[RegionSnapshot]:
        return list(self._regions)

    async def list_makes(self, q: str | None = None) -> Sequence[MakeSnapshot]:
        if q is None:
            return list(self._makes)
        needle = q.lower()
        return [m for m in self._makes if needle in m.name.lower()]

    async def list_models_by_make(
        self, make_id: int
    ) -> Sequence[ModelSnapshot]:
        return list(self._models_by_make.get(make_id, ()))

    async def list_generations_by_model(
        self, model_id: int
    ) -> Sequence[GenerationSnapshot]:
        return list(self._generations_by_model.get(model_id, ()))

    async def list_modifications_by_generation(
        self, generation_id: int
    ) -> Sequence[ModificationListItemSnapshot]:
        return list(self._modifications_by_generation.get(generation_id, ()))

    async def get_modification_details(
        self, modification_id: int
    ) -> ModificationListItemSnapshot | None:
        return self._modifications.get(modification_id)

    async def list_modifications_filtered(
        self,
        filters: RecommendationFilters,
        *,
        limit: int = 500,
    ) -> Sequence[ModificationListItemSnapshot]:
        rows = apply_filters(list(self._modifications.values()), filters)
        return rows[:limit]


class StubPricingRepository:

    def __init__(
        self,
        *,
        transport_tax_rates: Sequence[TransportTaxRateSnapshot] = (),
        luxury_matches: Sequence[LuxuryCarSnapshot] = (),
        osago: OsagoCoefficientsSnapshot | None = None,
        depreciation_rates: Sequence[DepreciationRateSnapshot] = (),
        mileage_penalties: Sequence[MileagePenaltySnapshot] = (),
        kasko_rates: Sequence[KaskoRateSnapshot] = (),
        service_plan_ops: Sequence[ServicePlanOpSnapshot] = (),
        service_plan_ops_by_generation: dict[int, Sequence[ServicePlanOpSnapshot]] | None = None,
        parts_costs: Sequence[PartsCostSnapshot] = (),
        labor_rates_by_region_sto: dict[tuple[int, str], LaborRateSnapshot]
        | None = None,
    ) -> None:
        self._tax = list(transport_tax_rates)
        self._lux = list(luxury_matches)
        self._osago = osago or OsagoCoefficientsSnapshot(
            tb_min_rub=Decimal("1399"),
            tb_max_rub=Decimal("8665"),
            kt_general=Decimal("1.96"),
            km_value=Decimal("1.20"),
            kvs_value=Decimal("0.95"),
            ko_value=Decimal("1.00"),
        )
        self._depr = list(depreciation_rates)
        self._mileage = list(mileage_penalties)
        self._kasko = list(kasko_rates)
        self._service = list(service_plan_ops)
        self._service_by_generation = service_plan_ops_by_generation or {}
        self._parts = list(parts_costs)
        self._labor = labor_rates_by_region_sto or {}

    async def get_transport_tax_rates(
        self, region_id: int, vehicle_type: str = "passenger"
    ) -> Sequence[TransportTaxRateSnapshot]:
        return [r for r in self._tax if r.region_id in (region_id, 0)]

    async def find_luxury_matches(
        self,
        make_name: str,
        model_name: str,
        engine_volume_l: Decimal | None,
    ) -> Sequence[LuxuryCarSnapshot]:
        return [
            r
            for r in self._lux
            if r.make_name.lower() == make_name.lower()
            and model_name.lower() in r.model_name.lower()
        ]

    async def resolve_osago_coefficients(
        self, profile: UserProfile, power_hp: int
    ) -> OsagoCoefficientsSnapshot:
        return self._osago

    async def list_depreciation_rates(
        self,
    ) -> Sequence[DepreciationRateSnapshot]:
        return list(self._depr)

    async def list_mileage_penalties(
        self,
    ) -> Sequence[MileagePenaltySnapshot]:
        return list(self._mileage)

    async def list_kasko_rates(self) -> Sequence[KaskoRateSnapshot]:
        return list(self._kasko)

    async def list_service_plan_ops(
        self, generation_id: int
    ) -> Sequence[ServicePlanOpSnapshot]:
        if generation_id in self._service_by_generation:
            return list(self._service_by_generation[generation_id])
        return list(self._service)

    async def list_parts_costs(
        self, operation_ids: Sequence[int], brand_segment: str
    ) -> Sequence[PartsCostSnapshot]:
        ids = set(operation_ids)
        return [
            r
            for r in self._parts
            if r.operation_id in ids and r.brand_segment == brand_segment
        ]

    async def get_labor_rate(
        self, region_id: int, sto_type: str
    ) -> LaborRateSnapshot | None:
        return self._labor.get((region_id, sto_type))


class StubFuelRepository:

    def __init__(
        self,
        rows: Sequence[FuelPriceForecastSnapshot] = (),
    ) -> None:
        self._rows = list(rows)

    async def list_fuel_price_forecast(
        self,
        region_id: int,
        fuel_type: str,
        month_from: date,
        month_to: date,
    ) -> Sequence[FuelPriceForecastSnapshot]:
        return [
            r
            for r in self._rows
            if r.region_id == region_id
            and r.fuel_type == fuel_type
            and month_from <= r.price_month <= month_to
        ]


__all__ = [
    "StubCatalogRepository",
    "StubPricingRepository",
    "StubFuelRepository",
    "StubAuthRepository",
    "StubPasswordResetNotifier",
    "StubScenarioRepository",
]


class StubAuthRepository:

    def __init__(self) -> None:
        self._users_by_id: dict[str, UserSnapshot] = {}
        self._users_by_email: dict[str, str] = {}
        self._profiles: dict[str, UserProfileSnapshot] = {}
        self._refresh: dict[str, tuple[str, datetime, datetime | None]] = {}
        self._password_reset: dict[str, tuple[str, datetime, datetime | None]] = {}

    async def get_user_by_email(self, email: str) -> UserSnapshot | None:
        user_id = self._users_by_email.get(email.lower())
        if user_id is None:
            return None
        return self._users_by_id.get(user_id)

    async def get_user_by_id(self, user_id: str) -> UserSnapshot | None:
        return self._users_by_id.get(user_id)

    async def create_user(
        self, *, email: str, password_hash: str, pdn_consent: bool
    ) -> UserSnapshot:
        user = UserSnapshot(
            id=str(uuid4()),
            email=email.lower(),
            password_hash=password_hash,
            pdn_consent=pdn_consent,
            is_active=True,
            created_at=datetime.now(UTC),
        )
        self._users_by_id[user.id] = user
        self._users_by_email[user.email] = user.id
        return user

    async def save_refresh_token(
        self, *, user_id: str, token_hash: str, expires_at: datetime
    ) -> None:
        self._refresh[token_hash] = (user_id, expires_at, None)

    async def validate_refresh_token(self, token_hash: str) -> UserSnapshot | None:
        row = self._refresh.get(token_hash)
        if row is None:
            return None
        user_id, expires_at, revoked_at = row
        if revoked_at is not None or expires_at <= datetime.now(UTC):
            return None
        return self._users_by_id.get(user_id)

    async def revoke_refresh_token(self, token_hash: str) -> None:
        row = self._refresh.get(token_hash)
        if row is None:
            return
        self._refresh[token_hash] = (row[0], row[1], datetime.now(UTC))

    async def revoke_all_refresh_tokens_for_user(self, user_id: str) -> None:
        now = datetime.now(UTC)
        for token_hash, row in list(self._refresh.items()):
            if row[0] == user_id:
                self._refresh[token_hash] = (row[0], row[1], now)

    async def save_password_reset_token(
        self, *, user_id: str, token_hash: str, expires_at: datetime
    ) -> None:
        self._password_reset[token_hash] = (user_id, expires_at, None)

    async def consume_password_reset_token(self, token_hash: str) -> UserSnapshot | None:
        row = self._password_reset.get(token_hash)
        if row is None:
            return None
        user_id, expires_at, consumed_at = row
        if consumed_at is not None or expires_at <= datetime.now(UTC):
            return None
        self._password_reset[token_hash] = (user_id, expires_at, datetime.now(UTC))
        return self._users_by_id.get(user_id)

    async def update_user_password(self, user_id: str, password_hash: str) -> None:
        user = self._users_by_id.get(user_id)
        if user is None:
            return
        self._users_by_id[user_id] = UserSnapshot(
            id=user.id,
            email=user.email,
            password_hash=password_hash,
            pdn_consent=user.pdn_consent,
            is_active=user.is_active,
            created_at=user.created_at,
        )

    async def get_profile(self, user_id: str) -> UserProfileSnapshot | None:
        return self._profiles.get(user_id)

    async def upsert_profile(
        self,
        *,
        user_id: str,
        profile: UserProfileSnapshot,
    ) -> UserProfileSnapshot:
        self._profiles[user_id] = profile
        return profile

    async def delete_profile(self, user_id: str) -> None:
        self._profiles.pop(user_id, None)


class StubPasswordResetNotifier:
    def __init__(self) -> None:
        self.last_token_by_email: dict[str, str] = {}

    async def send_reset_token(self, email: str, token: str) -> None:
        self.last_token_by_email[email] = token


class StubScenarioRepository:
    def __init__(self) -> None:
        self._saved: dict[str, SavedScenarioSnapshot] = {}
        self._cars: dict[str, list[ScenarioCarSnapshot]] = {}
        self._idempotency: dict[tuple[str, str], tuple[str, datetime]] = {}

    async def list_scenarios(
        self,
        *,
        user_id: str,
        include_deleted: bool,
        limit: int,
        cursor_created_at: datetime | None = None,
        cursor_id: str | None = None,
    ) -> Sequence[SavedScenarioSnapshot]:
        rows = [s for s in self._saved.values() if s.user_id == user_id]
        if not include_deleted:
            rows = [s for s in rows if s.deleted_at is None]
        if cursor_created_at is not None and cursor_id is not None:
            rows = [
                s
                for s in rows
                if s.created_at < cursor_created_at
                or (s.created_at == cursor_created_at and s.id < cursor_id)
            ]
        rows.sort(key=lambda s: (s.created_at, s.id), reverse=True)
        return rows[:limit]

    async def get_scenario(
        self, *, user_id: str, scenario_id: str, include_deleted: bool = False
    ) -> SavedScenarioSnapshot | None:
        row = self._saved.get(scenario_id)
        if row is None or row.user_id != user_id:
            return None
        if not include_deleted and row.deleted_at is not None:
            return None
        return row

    async def create_scenario(self, scenario: SavedScenarioSnapshot) -> SavedScenarioSnapshot:
        self._saved[scenario.id] = scenario
        return scenario

    async def update_scenario(self, scenario: SavedScenarioSnapshot) -> SavedScenarioSnapshot:
        self._saved[scenario.id] = scenario
        return scenario

    async def soft_delete_scenario(self, *, user_id: str, scenario_id: str) -> None:
        row = self._saved.get(scenario_id)
        if row is None or row.user_id != user_id:
            return
        self._saved[scenario_id] = SavedScenarioSnapshot(
            id=row.id,
            user_id=row.user_id,
            name=row.name,
            profile_snapshot=row.profile_snapshot,
            horizon_years=row.horizon_years,
            options_json=row.options_json,
            summary_total_tco_rub=row.summary_total_tco_rub,
            created_at=row.created_at,
            updated_at=row.updated_at,
            deleted_at=datetime.now(UTC),
        )

    async def list_scenario_cars(self, scenario_id: str) -> Sequence[ScenarioCarSnapshot]:
        rows = list(self._cars.get(scenario_id, []))
        rows.sort(key=lambda c: c.order_index)
        return rows

    async def replace_scenario_cars(
        self, *, scenario_id: str, cars: Sequence[ScenarioCarSnapshot]
    ) -> None:
        self._cars[scenario_id] = list(cars)

    async def get_idempotency_scenario_id(
        self, *, user_id: str, idempotency_key: str
    ) -> str | None:
        payload = self._idempotency.get((user_id, idempotency_key))
        if payload is None:
            return None
        scenario_id, expires_at = payload
        if expires_at <= datetime.now(UTC):
            self._idempotency.pop((user_id, idempotency_key), None)
            return None
        return scenario_id

    async def save_idempotency_scenario_id(
        self,
        *,
        user_id: str,
        idempotency_key: str,
        scenario_id: str,
        expires_at: datetime,
    ) -> None:
        self._idempotency[(user_id, idempotency_key)] = (scenario_id, expires_at)
