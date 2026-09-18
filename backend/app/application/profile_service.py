"""Profile use-cases: get, upsert, preset, delete."""

from __future__ import annotations

from datetime import UTC, datetime

from app.api.schemas.profile import ProfileRead, ProfileWrite, WeightPreset
from app.core.exceptions import NotFoundError
from app.domain.ports import AuthRepository
from app.domain.user import UserProfileSnapshot


class ProfileService:
    def __init__(self, repo: AuthRepository) -> None:
        self._repo = repo

    async def get(self, user_id: str) -> ProfileRead:
        row = await self._repo.get_profile(user_id)
        if row is None:
            raise NotFoundError("profile not found")
        return _to_read(row)

    async def put(self, user_id: str, payload: ProfileWrite) -> ProfileRead:
        now = datetime.now(UTC)
        existing = await self._repo.get_profile(user_id)
        profile = UserProfileSnapshot(
            user_id=user_id,
            region_id=payload.region_id,
            annual_mileage_km=payload.annual_mileage_km,
            driver_age=payload.driver_age,
            driver_experience_years=payload.driver_experience_years,
            osago_unlimited_drivers=payload.osago_unlimited_drivers,
            use_dealer_service=payload.use_dealer_service,
            include_kasko=payload.include_kasko,
            weights_preset=payload.weights_preset,
            created_at=existing.created_at if existing is not None else now,
            updated_at=now,
        )
        return _to_read(await self._repo.upsert_profile(user_id=user_id, profile=profile))

    async def apply_preset(self, user_id: str, preset: WeightPreset) -> ProfileRead:
        existing = await self._repo.get_profile(user_id)
        if existing is None:
            raise NotFoundError("profile not found")
        updated = UserProfileSnapshot(
            user_id=existing.user_id,
            region_id=existing.region_id,
            annual_mileage_km=existing.annual_mileage_km,
            driver_age=existing.driver_age,
            driver_experience_years=existing.driver_experience_years,
            osago_unlimited_drivers=existing.osago_unlimited_drivers,
            use_dealer_service=existing.use_dealer_service,
            include_kasko=existing.include_kasko,
            weights_preset=preset,
            created_at=existing.created_at,
            updated_at=datetime.now(UTC),
        )
        return _to_read(await self._repo.upsert_profile(user_id=user_id, profile=updated))

    async def delete(self, user_id: str) -> None:
        await self._repo.delete_profile(user_id)


def _to_read(row: UserProfileSnapshot) -> ProfileRead:
    return ProfileRead(
        user_id=row.user_id,
        region_id=row.region_id,
        annual_mileage_km=row.annual_mileage_km,
        driver_age=row.driver_age,
        driver_experience_years=row.driver_experience_years,
        osago_unlimited_drivers=row.osago_unlimited_drivers,
        use_dealer_service=row.use_dealer_service,
        include_kasko=row.include_kasko,
        weights_preset=row.weights_preset,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


__all__ = ["ProfileService"]
