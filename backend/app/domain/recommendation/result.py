"""Result DTOs for the recommendation pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.recommendation.candidate import Candidate, CriterionCode


@dataclass(frozen=True, slots=True)
class CriterionContribution:
    """Per-criterion contribution to the closeness coefficient."""

    value: float          # raw value of the criterion for this candidate
    normalized: float     # weighted normalised value (after step 3)
    contribution: float   # weighted contribution to closeness, in [0, 1]


@dataclass(frozen=True, slots=True)
class RankedCar:
    """One row in the ranked recommendation list."""

    candidate: Candidate
    rank: int
    score: float          # closeness coefficient (TOPSIS) — [0, 1]
    decomposition: dict[CriterionCode, CriterionContribution]
    explanation_ru: str


@dataclass(frozen=True, slots=True)
class RecommendationResult:
    """Output of :class:`RecommendationService.recommend()`."""

    ranked: tuple[RankedCar, ...]
    pareto_modification_ids: tuple[int, ...]
    total_candidates: int
    weights: dict[CriterionCode, float]
    diversity_count: int = 0
    notes: tuple[str, ...] = field(default_factory=tuple)


__all__ = [
    "CriterionContribution",
    "RankedCar",
    "RecommendationResult",
]
