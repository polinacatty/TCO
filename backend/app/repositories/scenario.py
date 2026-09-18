"""SQLAlchemy repository for saved comparisons."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.scenario import SavedComparisonCarSnapshot, SavedComparisonSnapshot
from app.infrastructure.orm.scenario import SavedScenario, ScenarioCar


class SqlScenarioRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_comparisons(
        self,
        *,
        user_id: str,
        limit: int,
        cursor_created_at: datetime | None = None,
        cursor_id: str | None = None,
    ) -> Sequence[SavedComparisonSnapshot]:
        stmt = (
            select(SavedScenario)
            .where(SavedScenario.user_id == user_id)
            .order_by(SavedScenario.created_at.desc(), SavedScenario.id.desc())
            .limit(limit)
        )
        if cursor_created_at is not None and cursor_id is not None:
            stmt = stmt.where(
                or_(
                    SavedScenario.created_at < cursor_created_at,
                    and_(
                        SavedScenario.created_at == cursor_created_at,
                        SavedScenario.id < cursor_id,
                    ),
                )
            )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_comparison(r) for r in rows]

    async def get_comparison(
        self, *, user_id: str, comparison_id: str
    ) -> SavedComparisonSnapshot | None:
        stmt = select(SavedScenario).where(
            SavedScenario.id == comparison_id,
            SavedScenario.user_id == user_id,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_comparison(row) if row is not None else None

    async def get_comparison_by_signature(
        self,
        *,
        user_id: str,
        signature: str,
    ) -> SavedComparisonSnapshot | None:
        stmt = select(SavedScenario).where(
            SavedScenario.user_id == user_id,
            SavedScenario.signature == signature,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_comparison(row) if row is not None else None

    async def create_comparison(
        self,
        comparison: SavedComparisonSnapshot,
        cars: Sequence[SavedComparisonCarSnapshot],
    ) -> SavedComparisonSnapshot:
        row = SavedScenario(
            id=comparison.id,
            user_id=comparison.user_id,
            name=comparison.name,
            signature=comparison.signature,
        )
        self._session.add(row)
        for car in cars:
            self._session.add(
                ScenarioCar(
                    scenario_id=comparison.id,
                    modification_id=car.modification_id,
                    order_index=car.order_index,
                )
            )
        await self._session.commit()
        await self._session.refresh(row)
        return _to_comparison(row)

    async def delete_comparison(self, *, user_id: str, comparison_id: str) -> None:
        stmt = select(SavedScenario).where(
            SavedScenario.id == comparison_id,
            SavedScenario.user_id == user_id,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return
        await self._session.execute(delete(ScenarioCar).where(ScenarioCar.scenario_id == comparison_id))
        await self._session.delete(row)
        await self._session.commit()

    async def list_comparison_cars(self, comparison_id: str) -> Sequence[SavedComparisonCarSnapshot]:
        stmt = (
            select(ScenarioCar)
            .where(ScenarioCar.scenario_id == comparison_id)
            .order_by(ScenarioCar.order_index.asc(), ScenarioCar.modification_id.asc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_car(r) for r in rows]

    async def list_comparison_ids_by_signature(
        self,
        *,
        user_id: str,
        signatures: Sequence[str],
    ) -> Sequence[str]:
        if not signatures:
            return []
        stmt = (
            select(SavedScenario.id)
            .where(SavedScenario.user_id == user_id, SavedScenario.signature.in_(list(signatures)))
            .order_by(SavedScenario.created_at.desc(), SavedScenario.id.desc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [row for row in rows]


def _to_comparison(row: SavedScenario) -> SavedComparisonSnapshot:
    return SavedComparisonSnapshot(
        id=row.id,
        user_id=row.user_id,
        name=row.name,
        signature=row.signature,
        created_at=row.created_at,
    )


def _to_car(row: ScenarioCar) -> SavedComparisonCarSnapshot:
    return SavedComparisonCarSnapshot(
        comparison_id=row.scenario_id,
        modification_id=row.modification_id,
        order_index=row.order_index,
    )


__all__ = ["SqlScenarioRepository"]
