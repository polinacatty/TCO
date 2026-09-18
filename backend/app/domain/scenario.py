"""Domain DTOs for saved comparisons."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
@dataclass(frozen=True, slots=True)
class SavedComparisonCarSnapshot:
    comparison_id: str
    modification_id: int
    order_index: int


@dataclass(frozen=True, slots=True)
class SavedComparisonSnapshot:
    id: str
    user_id: str
    name: str
    signature: str
    created_at: datetime


__all__ = ["SavedComparisonSnapshot", "SavedComparisonCarSnapshot"]
