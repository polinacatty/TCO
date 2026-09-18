"""Hard-filter DTO + 6 predicate helpers.

The repository layer is responsible for translating
:class:`RecommendationFilters` into SQL ``WHERE`` clauses; the domain
applies the same predicates in-memory when the test stubs are used.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from app.domain.tco.snapshots import ModificationListItemSnapshot


@dataclass(frozen=True, slots=True)
class RecommendationFilters:
    """Hard filters applied **before** TOPSIS to shrink the candidate pool.

    All fields are optional; ``None`` / empty tuple → predicate not applied.
    """

    purchase_price_min_rub: int | None = None
    purchase_price_max_rub: int | None = None
    body_types: tuple[str, ...] = field(default_factory=tuple)
    drives: tuple[str, ...] = field(default_factory=tuple)
    fuel_types: tuple[str, ...] = field(default_factory=tuple)
    transmissions: tuple[str, ...] = field(default_factory=tuple)
    segments: tuple[str, ...] = field(default_factory=tuple)
    year_min: int | None = None
    year_max: int | None = None
    power_min_hp: int | None = None
    power_max_hp: int | None = None
    cargo_min_l: int | None = None
    seats_min: int | None = None
    body_clearance_min_mm: int | None = None


def matches(
    mod: ModificationListItemSnapshot, filters: RecommendationFilters
) -> bool:
    """Apply filters in-memory; returns ``True`` if all predicates pass."""
    if filters.purchase_price_min_rub is not None and mod.msrp_new_rub < filters.purchase_price_min_rub:
        return False
    if filters.purchase_price_max_rub is not None and mod.msrp_new_rub > filters.purchase_price_max_rub:
        return False

    if filters.body_types and mod.body_type not in filters.body_types:
        return False
    if filters.drives and mod.drive not in filters.drives:
        return False
    if filters.fuel_types and mod.fuel_type not in filters.fuel_types:
        return False
    if filters.transmissions and mod.transmission not in filters.transmissions:
        return False
    if filters.segments and mod.segment not in filters.segments:
        return False

    if filters.year_min is not None and mod.year_from < filters.year_min:
        return False
    if filters.year_max is not None and mod.year_from > filters.year_max:
        return False

    if filters.power_min_hp is not None and mod.power_hp < filters.power_min_hp:
        return False
    if filters.power_max_hp is not None and mod.power_hp > filters.power_max_hp:
        return False
    if (
        filters.cargo_min_l is not None
        and (mod.cargo_volume_l is None or mod.cargo_volume_l < filters.cargo_min_l)
    ):
        return False
    if filters.seats_min is not None and (mod.seats is None or mod.seats < filters.seats_min):
        return False
    if filters.body_clearance_min_mm is not None:
        if mod.body_clearance_mm is None:
            return False
        if mod.body_clearance_mm < filters.body_clearance_min_mm:
            return False

    return True


def apply_filters(
    candidates: Sequence[ModificationListItemSnapshot],
    filters: RecommendationFilters,
) -> list[ModificationListItemSnapshot]:
    """Return only the candidates that satisfy all predicates."""
    return [c for c in candidates if matches(c, filters)]


__all__ = ["RecommendationFilters", "matches", "apply_filters"]
