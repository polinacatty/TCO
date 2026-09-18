"""Candidate DTO and criterion codes for the TOPSIS ranker.

A :class:`Candidate` carries the 6 numeric features used by TOPSIS plus
the identification fields and a precomputed ``tco_5y_rub`` (the most
expensive criterion). All values are floats — TOPSIS works on real
numbers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# 6 criteria from methodology §3.1.
CriterionCode = Literal[
    "tco_5y",
    "purchase_price",
    "reliability",
    "depreciation",
    "power",
    "cargo",
]

# direction[c] = +1 → maximize, −1 → minimize.
CRITERION_DIRECTION: dict[CriterionCode, int] = {
    "tco_5y": -1,
    "purchase_price": -1,
    "reliability": +1,
    "depreciation": -1,
    "power": +1,
    "cargo": +1,
}

CRITERIA_ORDER: tuple[CriterionCode, ...] = (
    "tco_5y",
    "purchase_price",
    "reliability",
    "depreciation",
    "power",
    "cargo",
)


@dataclass(frozen=True, slots=True)
class Candidate:
    """One row in the TOPSIS decision matrix."""

    modification_id: int
    make: str
    model: str
    generation: str
    body_type: str
    segment: str
    fuel_type: str
    drive: str
    transmission: str

    # criteria
    tco_5y_rub: float
    purchase_price_rub: float
    reliability_score: float
    depreciation_5y_pct: float
    power_hp: float
    cargo_volume_l: float

    def criterion(self, code: CriterionCode) -> float:
        return float(getattr(self, _CODE_TO_ATTR[code]))


_CODE_TO_ATTR: dict[CriterionCode, str] = {
    "tco_5y": "tco_5y_rub",
    "purchase_price": "purchase_price_rub",
    "reliability": "reliability_score",
    "depreciation": "depreciation_5y_pct",
    "power": "power_hp",
    "cargo": "cargo_volume_l",
}


__all__ = ["Candidate", "CriterionCode", "CRITERIA_ORDER", "CRITERION_DIRECTION"]
