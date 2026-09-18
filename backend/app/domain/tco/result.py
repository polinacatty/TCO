"""Result of a TCO calculation — pure value object returned to the API layer.

The structure mirrors the seven components:

* ``depreciation``  — capital loss over the horizon
* ``fuel``          — monthly sum over SARIMA forecast
* ``osago``         — annual premium × horizon
* ``kasko``         — annual premium × horizon (zero if disabled)
* ``transport_tax`` — annual tax × horizon (with luxury coef.)
* ``maintenance``   — Σ scheduled ops, **including** seasonal tyre swap
* ``tyres``         — purchase of new sets only (no seasonal swap here)

All amounts are in integer rubles (rounded at the component level).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ComponentBreakdown:
    """Optional component-specific explanation block, useful for the UI.

    Kept loose (``dict[str, Any]``) on purpose: each component decides what
    is worth surfacing (e.g. tax breakdown by year, number of tyre sets,
    list of maintenance operations with hit counts). UI / API can render
    only the keys it understands.
    """

    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TcoResult:
    """All seven TCO components + total, in integer rubles."""

    depreciation: int
    fuel: int
    osago: int
    kasko: int
    transport_tax: int
    maintenance: int
    tyres: int

    breakdowns: dict[str, ComponentBreakdown] = field(default_factory=dict)

    @property
    def total(self) -> int:
        """Sum of all seven components."""
        return (
            self.depreciation
            + self.fuel
            + self.osago
            + self.kasko
            + self.transport_tax
            + self.maintenance
            + self.tyres
        )

    def as_dict(self) -> dict[str, int]:
        """Flat ``{component_code: rubles}`` mapping including ``total``."""
        return {
            "depreciation": self.depreciation,
            "fuel": self.fuel,
            "osago": self.osago,
            "kasko": self.kasko,
            "transport_tax": self.transport_tax,
            "maintenance": self.maintenance,
            "tyres": self.tyres,
            "total": self.total,
        }


__all__ = ["ComponentBreakdown", "TcoResult"]
