"""Saved comparisons application service."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

from app.api.schemas.scenario import (
    ScenarioCreateRequest,
    ScenarioExistsResponse,
    ScenarioListResponse,
    ScenarioRead,
    ScenarioSummaryRead,
)
from app.core.exceptions import NotFoundError, ValidationAppError
from app.core.metrics import metrics_registry
from app.domain.ports import ScenarioRepository
from app.domain.scenario import SavedComparisonCarSnapshot, SavedComparisonSnapshot


class ScenarioService:
    def __init__(self, repo: ScenarioRepository, *args: object, **kwargs: object) -> None:
        self._repo = repo

    async def list_scenarios(
        self, *, user_id: str, include_deleted: bool, limit: int, cursor: str | None = None
    ) -> ScenarioListResponse:
        started = datetime.now(UTC)
        failed = False
        _ = include_deleted
        cursor_created_at, cursor_id = _decode_cursor(cursor)
        items = await self._repo.list_comparisons(
            user_id=user_id,
            limit=limit + 1,
            cursor_created_at=cursor_created_at,
            cursor_id=cursor_id,
        )
        has_more = len(items) > limit
        page = items[:limit]
        summaries: list[ScenarioSummaryRead] = []
        for s in page:
            cars = await self._repo.list_comparison_cars(s.id)
            summaries.append(
                ScenarioSummaryRead(
                    id=s.id,
                    name=s.name,
                    modifications_count=len(cars),
                    modification_ids=[car.modification_id for car in cars],
                    created_at=s.created_at,
                )
            )
        next_cursor = _encode_cursor(page[-1].created_at, page[-1].id) if has_more and page else None
        metrics_registry.observe_service(
            operation="scenarios.list",
            success=not failed,
            duration_ms=_duration_ms(started),
        )
        return ScenarioListResponse(items=summaries, has_more=has_more, next_cursor=next_cursor)

    async def create(
        self,
        *,
        user_id: str,
        payload: ScenarioCreateRequest,
        idempotency_key: str | None,
    ) -> ScenarioRead:
        started = datetime.now(UTC)
        failed = False
        _ = idempotency_key
        normalized_ids = _normalize_modification_ids(payload.modification_ids)
        signature = _build_signature(normalized_ids)
        existing = await self._repo.get_comparison_by_signature(user_id=user_id, signature=signature)
        if existing is not None:
            out = await self.get(user_id=user_id, scenario_id=existing.id)
            metrics_registry.observe_service(
                operation="scenarios.create",
                success=not failed,
                duration_ms=_duration_ms(started),
            )
            return out

        comparison_id = str(uuid4())
        now = datetime.now(UTC)
        name = payload.name or f"Сравнение {now.strftime('%d.%m.%Y %H:%M')}"
        saved = SavedComparisonSnapshot(
            id=comparison_id,
            user_id=user_id,
            name=name,
            signature=signature,
            created_at=now,
        )
        cars = [
            SavedComparisonCarSnapshot(
                comparison_id=comparison_id,
                modification_id=modification_id,
                order_index=index,
            )
            for index, modification_id in enumerate(normalized_ids)
        ]
        saved = await self._repo.create_comparison(saved, cars)
        out = ScenarioRead(
            id=saved.id,
            name=saved.name,
            modification_ids=normalized_ids,
            created_at=saved.created_at,
        )
        metrics_registry.observe_service(
            operation="scenarios.create",
            success=not failed,
            duration_ms=_duration_ms(started),
        )
        return out

    async def get(self, *, user_id: str, scenario_id: str) -> ScenarioRead:
        started = datetime.now(UTC)
        failed = False
        saved = await self._repo.get_comparison(user_id=user_id, comparison_id=scenario_id)
        if saved is None:
            failed = True
            metrics_registry.observe_service(
                operation="scenarios.get",
                success=not failed,
                duration_ms=_duration_ms(started),
            )
            raise NotFoundError("scenario not found")
        cars = await self._repo.list_comparison_cars(scenario_id)
        out = ScenarioRead(
            id=saved.id,
            name=saved.name,
            modification_ids=[car.modification_id for car in cars],
            created_at=saved.created_at,
        )
        metrics_registry.observe_service(
            operation="scenarios.get",
            success=not failed,
            duration_ms=_duration_ms(started),
        )
        return out

    async def delete(self, *, user_id: str, scenario_id: str) -> None:
        started = datetime.now(UTC)
        failed = False
        await self._repo.delete_comparison(user_id=user_id, comparison_id=scenario_id)
        metrics_registry.observe_service(
            operation="scenarios.delete",
            success=not failed,
            duration_ms=_duration_ms(started),
        )

    async def exists(self, *, user_id: str, modification_ids: Sequence[int]) -> ScenarioExistsResponse:
        normalized_ids = _normalize_modification_ids(modification_ids)
        signature = _build_signature(normalized_ids)
        saved = await self._repo.get_comparison_by_signature(user_id=user_id, signature=signature)
        return ScenarioExistsResponse(
            exists=saved is not None,
            comparison_id=saved.id if saved is not None else None,
        )

    async def recalculate(self, *, user_id: str, scenario_id: str) -> ScenarioRead:
        _ = user_id
        _ = scenario_id
        raise ValidationAppError("recalculate is no longer supported for saved comparisons")

    async def update(self, *, user_id: str, scenario_id: str, payload: object) -> ScenarioRead:
        _ = user_id
        _ = scenario_id
        _ = payload
        raise ValidationAppError("update is no longer supported for saved comparisons")

    async def _evaluate(self, *args: object, **kwargs: object) -> list[object]:
        _ = args
        _ = kwargs
        return []


__all__ = ["ScenarioService"]


def _normalize_modification_ids(modification_ids: Sequence[int]) -> list[int]:
    unique = sorted({int(modification_id) for modification_id in modification_ids})
    if len(unique) < 2 or len(unique) > 3:
        raise ValidationAppError("saved comparison must contain 2 or 3 unique modification_ids")
    return unique


def _build_signature(modification_ids: Sequence[int]) -> str:
    return ",".join(str(modification_id) for modification_id in modification_ids)


def _duration_ms(started: datetime) -> float:
    return (datetime.now(UTC) - started).total_seconds() * 1000.0


def _encode_cursor(created_at: datetime, scenario_id: str) -> str:
    raw = f"{created_at.isoformat()}|{scenario_id}"
    return raw.encode("utf-8").hex()


def _decode_cursor(cursor: str | None) -> tuple[datetime | None, str | None]:
    if not cursor:
        return None, None
    try:
        raw = bytes.fromhex(cursor).decode("utf-8")
        left, right = raw.split("|", maxsplit=1)
        return datetime.fromisoformat(left), right
    except ValueError as exc:
        raise ValidationAppError("invalid cursor") from exc
