"""Ranking weights — 6 criteria + 6 presets."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from app.domain.recommendation.candidate import CRITERIA_ORDER, CriterionCode


@dataclass(frozen=True, slots=True)
class RankingWeights:
    """Weights for the 6 TOPSIS criteria. Must sum to (approximately) 1."""

    tco_5y: float
    purchase_price: float
    reliability: float
    depreciation: float
    power: float
    cargo: float

    def __post_init__(self) -> None:
        for code in CRITERIA_ORDER:
            value = getattr(self, code)
            if value < 0 or value > 1:
                raise ValueError(
                    f"weight {code!r} must be in [0, 1], got {value}"
                )
        total = sum(getattr(self, code) for code in CRITERIA_ORDER)
        if abs(total - 1.0) > 1e-3:
            raise ValueError(
                f"weights must sum to 1.0 (got {total:.4f}); presets are pre-normalised"
            )

    def as_dict(self) -> dict[CriterionCode, float]:
        return {code: float(getattr(self, code)) for code in CRITERIA_ORDER}

    @classmethod
    def from_dict(cls, weights: Mapping[str, float]) -> RankingWeights:
        return cls(
            tco_5y=weights.get("tco_5y", 0.0),
            purchase_price=weights.get("purchase_price", 0.0),
            reliability=weights.get("reliability", 0.0),
            depreciation=weights.get("depreciation", 0.0),
            power=weights.get("power", 0.0),
            cargo=weights.get("cargo", 0.0),
        )


# Presets straight from methodology §3.3.
DEFAULT_WEIGHTS = RankingWeights(
    tco_5y=0.30,
    purchase_price=0.20,
    reliability=0.20,
    depreciation=0.10,
    power=0.10,
    cargo=0.10,
)

PRESET_WEIGHTS: dict[str, RankingWeights] = {
    "balanced": DEFAULT_WEIGHTS,
    "cheapest": RankingWeights(
        tco_5y=0.40,
        purchase_price=0.40,
        reliability=0.10,
        depreciation=0.05,
        power=0.025,
        cargo=0.025,
    ),
    "family": RankingWeights(
        tco_5y=0.20,
        purchase_price=0.10,
        reliability=0.30,
        depreciation=0.05,
        power=0.10,
        cargo=0.25,
    ),
    "premium": RankingWeights(
        tco_5y=0.15,
        purchase_price=0.05,
        reliability=0.20,
        depreciation=0.20,
        power=0.30,
        cargo=0.10,
    ),
    "student": RankingWeights(
        tco_5y=0.30,
        purchase_price=0.50,
        reliability=0.10,
        depreciation=0.05,
        power=0.025,
        cargo=0.025,
    ),
    "business": RankingWeights(
        tco_5y=0.30,
        purchase_price=0.10,
        reliability=0.20,
        depreciation=0.20,
        power=0.15,
        cargo=0.05,
    ),
}


def resolve_weights(
    preset: str | None,
    weights: Mapping[str, float] | None,
) -> RankingWeights:
    """Resolve weights: explicit override > preset > balanced default."""
    if weights:
        return RankingWeights.from_dict(weights)
    if preset and preset in PRESET_WEIGHTS:
        return PRESET_WEIGHTS[preset]
    return DEFAULT_WEIGHTS


__all__ = [
    "RankingWeights",
    "DEFAULT_WEIGHTS",
    "PRESET_WEIGHTS",
    "resolve_weights",
]
