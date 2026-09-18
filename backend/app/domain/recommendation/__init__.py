"""Domain for car recommendation — pure Python + numpy, no IO.

Layout:

* :mod:`app.domain.recommendation.filters`     — hard-filter dataclass
* :mod:`app.domain.recommendation.weights`     — RankingWeights + 6 presets
* :mod:`app.domain.recommendation.topsis`      — TOPSIS implementation + Pareto
* :mod:`app.domain.recommendation.candidate`   — candidate snapshot used by ranker
* :mod:`app.domain.recommendation.result`      — RankedCar, RecommendationResult
* :mod:`app.domain.recommendation.service`     — domain orchestration

See ``docs/04_ml_models/02_topsis_methodology.md`` for the full spec.
"""

from app.domain.recommendation.candidate import (
    CRITERIA_ORDER,
    CRITERION_DIRECTION,
    Candidate,
    CriterionCode,
)
from app.domain.recommendation.explainer import build_explanation
from app.domain.recommendation.filters import RecommendationFilters, apply_filters, matches
from app.domain.recommendation.result import (
    CriterionContribution,
    RankedCar,
    RecommendationResult,
)
from app.domain.recommendation.topsis import (
    ParetoExtractor,
    TopsisRanker,
)
from app.domain.recommendation.weights import (
    DEFAULT_WEIGHTS,
    PRESET_WEIGHTS,
    RankingWeights,
    resolve_weights,
)

__all__ = [
    "CRITERIA_ORDER",
    "CRITERION_DIRECTION",
    "Candidate",
    "CriterionCode",
    "CriterionContribution",
    "RankedCar",
    "RecommendationFilters",
    "RecommendationResult",
    "TopsisRanker",
    "ParetoExtractor",
    "DEFAULT_WEIGHTS",
    "PRESET_WEIGHTS",
    "RankingWeights",
    "resolve_weights",
    "build_explanation",
    "apply_filters",
    "matches",
]
