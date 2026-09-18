"""Hard-фильтры для recommendation pipeline.

Каждый фильтр — реализация `Filter` ABC с методом `apply(df) -> df`.
`RecommendationService` применяет фильтры через `functools.reduce`.

`reason_if_excluded()` возвращает причину исключения для UI («не показано
потому что бюджет ниже минимума для этого сегмента»).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

import pandas as pd


class Filter(ABC):
    """Abstract base class for hard-фильтров."""

    @abstractmethod
    def apply(self, df: pd.DataFrame) -> pd.DataFrame: ...

    @abstractmethod
    def reason_if_excluded(self) -> str: ...


class BudgetFilter(Filter):
    """`purchase_price <= budget`."""

    def __init__(self, max_price_rub: float, price_column: str = "purchase_price"):
        self.max_price = float(max_price_rub)
        self.col = price_column

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        if self.col not in df.columns:
            return df
        return df[df[self.col] <= self.max_price]

    def reason_if_excluded(self) -> str:
        return f"цена покупки превышает бюджет {self.max_price:,.0f} ₽"


class SegmentFilter(Filter):
    """`segment ∈ allowed`."""

    def __init__(self, allowed: list[str], column: str = "segment"):
        self.allowed = set(allowed)
        self.col = column

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        if not self.allowed or self.col not in df.columns:
            return df
        return df[df[self.col].isin(self.allowed)]

    def reason_if_excluded(self) -> str:
        return f"сегмент не в списке {sorted(self.allowed)}"


class FuelTypeFilter(Filter):
    """`fuel_type ∈ allowed` (case-insensitive)."""

    def __init__(self, allowed: list[str], column: str = "fuel_type"):
        self.allowed = {x.upper() for x in allowed}
        self.col = column

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        if not self.allowed or self.col not in df.columns:
            return df
        return df[df[self.col].str.upper().isin(self.allowed)]

    def reason_if_excluded(self) -> str:
        return f"тип топлива не в списке {sorted(self.allowed)}"


class TransmissionFilter(Filter):
    def __init__(self, allowed: list[str], column: str = "transmission"):
        self.allowed = {x.upper() for x in allowed}
        self.col = column

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        if not self.allowed or self.col not in df.columns:
            return df
        return df[df[self.col].str.upper().isin(self.allowed)]

    def reason_if_excluded(self) -> str:
        return f"трансмиссия не в списке {sorted(self.allowed)}"


class BodyTypeFilter(Filter):
    def __init__(self, allowed: list[str], column: str = "body_type"):
        self.allowed = {x.lower() for x in allowed}
        self.col = column

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        if not self.allowed or self.col not in df.columns:
            return df
        return df[df[self.col].str.lower().isin(self.allowed)]

    def reason_if_excluded(self) -> str:
        return f"тип кузова не в списке {sorted(self.allowed)}"


class _MinValueFilter(Filter):
    """Generic min-value filter."""

    LABEL: str = "value"
    DEFAULT_COL: str = ""

    def __init__(self, min_value: float, column: Optional[str] = None):
        self.min_value = float(min_value)
        self.col = column or self.DEFAULT_COL

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        if self.col not in df.columns:
            return df
        return df[df[self.col] >= self.min_value]

    def reason_if_excluded(self) -> str:
        return f"{self.LABEL} меньше минимума {self.min_value}"


class MinSeatsFilter(_MinValueFilter):
    LABEL = "число мест"
    DEFAULT_COL = "seats"


class MinPowerFilter(_MinValueFilter):
    LABEL = "мощность (л.с.)"
    DEFAULT_COL = "power_hp"


class MinClearanceFilter(_MinValueFilter):
    LABEL = "клиренс (мм)"
    DEFAULT_COL = "body_clearance_mm"


class MinCargoFilter(_MinValueFilter):
    LABEL = "объём багажника (л)"
    DEFAULT_COL = "cargo_volume_l"


def build_filters_from_profile(profile) -> list[Filter]:
    """Convenience: construct filter list from a UserProfile."""
    from .profile import UserProfile
    assert isinstance(profile, UserProfile)
    filters: list[Filter] = []
    if profile.budget_rub:
        filters.append(BudgetFilter(profile.budget_rub))
    if profile.preferred_segments:
        filters.append(SegmentFilter(profile.preferred_segments))
    if profile.allowed_fuel_types:
        filters.append(FuelTypeFilter(profile.allowed_fuel_types))
    if profile.allowed_transmissions:
        filters.append(TransmissionFilter(profile.allowed_transmissions))
    if profile.allowed_body_types:
        filters.append(BodyTypeFilter(profile.allowed_body_types))
    if profile.min_seats is not None:
        filters.append(MinSeatsFilter(profile.min_seats))
    if profile.min_power_hp is not None:
        filters.append(MinPowerFilter(profile.min_power_hp))
    if profile.min_clearance_mm is not None:
        filters.append(MinClearanceFilter(profile.min_clearance_mm))
    if profile.min_cargo_volume_l is not None:
        filters.append(MinCargoFilter(profile.min_cargo_volume_l))
    return filters
