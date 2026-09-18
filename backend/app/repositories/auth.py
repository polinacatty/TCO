"""SQLAlchemy implementation of auth/profile persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.user import FavoriteModificationSnapshot, UserProfileSnapshot, UserSnapshot
from app.infrastructure.orm.user import (
    FavoriteModification,
    PasswordResetToken,
    RefreshToken,
    User,
    UserProfile,
)


class SqlAuthRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_user_by_email(self, email: str) -> UserSnapshot | None:
        stmt = select(User).where(User.email == email.lower())
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_user(row) if row is not None else None

    async def get_user_by_id(self, user_id: str) -> UserSnapshot | None:
        stmt = select(User).where(User.id == user_id)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_user(row) if row is not None else None

    async def create_user(
        self, *, email: str, password_hash: str, pdn_consent: bool
    ) -> UserSnapshot:
        row = User(
            id=str(uuid4()),
            email=email.lower(),
            password_hash=password_hash,
            pdn_consent=pdn_consent,
            is_active=True,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.commit()
        await self._session.refresh(row)
        return _to_user(row)

    async def save_refresh_token(
        self, *, user_id: str, token_hash: str, expires_at: datetime
    ) -> None:
        row = RefreshToken(
            id=str(uuid4()),
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            revoked_at=None,
        )
        self._session.add(row)
        await self._session.commit()

    async def validate_refresh_token(self, token_hash: str) -> UserSnapshot | None:
        stmt = (
            select(User)
            .join(RefreshToken, RefreshToken.user_id == User.id)
            .where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.revoked_at.is_(None),
                RefreshToken.expires_at > datetime.now(UTC),
            )
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_user(row) if row is not None else None

    async def revoke_refresh_token(self, token_hash: str) -> None:
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return
        row.revoked_at = datetime.now(UTC)
        await self._session.commit()

    async def revoke_all_refresh_tokens_for_user(self, user_id: str) -> None:
        stmt = (
            select(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        now = datetime.now(UTC)
        for row in rows:
            row.revoked_at = now
        await self._session.commit()

    async def save_password_reset_token(
        self, *, user_id: str, token_hash: str, expires_at: datetime
    ) -> None:
        row = PasswordResetToken(
            id=str(uuid4()),
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            consumed_at=None,
        )
        self._session.add(row)
        await self._session.commit()

    async def consume_password_reset_token(self, token_hash: str) -> UserSnapshot | None:
        stmt = (
            select(User, PasswordResetToken)
            .join(PasswordResetToken, PasswordResetToken.user_id == User.id)
            .where(
                PasswordResetToken.token_hash == token_hash,
                PasswordResetToken.consumed_at.is_(None),
                PasswordResetToken.expires_at > datetime.now(UTC),
            )
        )
        row = (await self._session.execute(stmt)).one_or_none()
        if row is None:
            return None
        token_row: PasswordResetToken = row[1]
        token_row.consumed_at = datetime.now(UTC)
        await self._session.commit()
        return _to_user(row[0])

    async def update_user_password(self, user_id: str, password_hash: str) -> None:
        stmt = select(User).where(User.id == user_id)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return
        row.password_hash = password_hash
        await self._session.commit()

    async def get_profile(self, user_id: str) -> UserProfileSnapshot | None:
        stmt = select(UserProfile).where(UserProfile.user_id == user_id)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_profile(row) if row is not None else None

    async def upsert_profile(
        self,
        *,
        user_id: str,
        profile: UserProfileSnapshot,
    ) -> UserProfileSnapshot:
        stmt = select(UserProfile).where(UserProfile.user_id == user_id)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            row = UserProfile(
                user_id=user_id,
                region_id=profile.region_id,
                annual_mileage_km=profile.annual_mileage_km,
                driver_age=profile.driver_age,
                driver_experience_years=profile.driver_experience_years,
                osago_unlimited_drivers=profile.osago_unlimited_drivers,
                use_dealer_service=profile.use_dealer_service,
                include_kasko=profile.include_kasko,
                weights_preset=profile.weights_preset,
            )
            self._session.add(row)
        else:
            row.region_id = profile.region_id
            row.annual_mileage_km = profile.annual_mileage_km
            row.driver_age = profile.driver_age
            row.driver_experience_years = profile.driver_experience_years
            row.osago_unlimited_drivers = profile.osago_unlimited_drivers
            row.use_dealer_service = profile.use_dealer_service
            row.include_kasko = profile.include_kasko
            row.weights_preset = profile.weights_preset
            row.updated_at = datetime.now(UTC)
        await self._session.commit()
        await self._session.refresh(row)
        return _to_profile(row)

    async def delete_profile(self, user_id: str) -> None:
        stmt = select(UserProfile).where(UserProfile.user_id == user_id)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return
        await self._session.delete(row)
        await self._session.commit()

    async def list_favorites(self, user_id: str) -> list[FavoriteModificationSnapshot]:
        stmt = (
            select(FavoriteModification)
            .where(FavoriteModification.user_id == user_id)
            .order_by(FavoriteModification.created_at.desc(), FavoriteModification.modification_id.asc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_favorite(row) for row in rows]

    async def add_favorite(self, *, user_id: str, modification_id: int) -> None:
        stmt = select(FavoriteModification).where(
            FavoriteModification.user_id == user_id,
            FavoriteModification.modification_id == modification_id,
        )
        existing = (await self._session.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            return
        row = FavoriteModification(user_id=user_id, modification_id=modification_id)
        self._session.add(row)
        await self._session.commit()

    async def remove_favorite(self, *, user_id: str, modification_id: int) -> None:
        stmt = select(FavoriteModification).where(
            FavoriteModification.user_id == user_id,
            FavoriteModification.modification_id == modification_id,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return
        await self._session.delete(row)
        await self._session.commit()


def _to_user(row: User) -> UserSnapshot:
    return UserSnapshot(
        id=row.id,
        email=row.email,
        password_hash=row.password_hash,
        pdn_consent=bool(row.pdn_consent),
        is_active=bool(row.is_active),
        created_at=row.created_at,
    )


def _to_profile(row: UserProfile) -> UserProfileSnapshot:
    return UserProfileSnapshot(
        user_id=row.user_id,
        region_id=row.region_id,
        annual_mileage_km=row.annual_mileage_km,
        driver_age=row.driver_age,
        driver_experience_years=row.driver_experience_years,
        osago_unlimited_drivers=bool(row.osago_unlimited_drivers),
        use_dealer_service=bool(row.use_dealer_service),
        include_kasko=bool(row.include_kasko),
        weights_preset=row.weights_preset,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_favorite(row: FavoriteModification) -> FavoriteModificationSnapshot:
    return FavoriteModificationSnapshot(
        user_id=row.user_id,
        modification_id=row.modification_id,
        created_at=row.created_at,
    )


__all__ = ["SqlAuthRepository"]
