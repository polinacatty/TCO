"""ml.recommendation — алгоритмы подбора и ранжирования автомобилей (этап 4.2).

Public API:

    UserProfile             — параметры запроса (бюджет, регион, веса, etc.)
    CriterionSpec           — описание критерия (имя/направление/min/max)
    DEFAULT_CRITERIA        — 6 критериев MVP
    DEFAULT_WEIGHTS         — веса по умолчанию (balanced preset)
    WEIGHT_PRESETS          — 6 пресетов (balanced/cheapest/family/...)

    TCOCalculator           — расчёт TCO_5y под конкретный UserProfile
    Filter                  — ABC для hard-фильтров + 9 реализаций
    RankingStrategy         — ABC + TopsisStrategy + WeightedSumStrategy
    decompose               — раскладка closeness coefficient для UI

    RecommendationService   — оркестратор (filters → criteria → ranking → decomposition)
    RecommendationResult    — структура результата
"""

from .profile import UserProfile, WEIGHT_PRESETS, DEFAULT_WEIGHTS
from .criteria import CriterionSpec, DEFAULT_CRITERIA
from .tco_calc import TCOCalculator, load_seed
from .filters import (
    Filter,
    BudgetFilter,
    SegmentFilter,
    FuelTypeFilter,
    TransmissionFilter,
    BodyTypeFilter,
    MinSeatsFilter,
    MinPowerFilter,
    MinClearanceFilter,
    MinCargoFilter,
)
from .topsis import topsis_rank
from .strategies import RankingStrategy, TopsisStrategy, WeightedSumStrategy
from .decomposition import decompose
from .pareto import (
    pareto_front,
    pareto_front_2d,
    non_dominated_ranks,
    compute_pareto_layers,
)
from .service import RecommendationService, RecommendationResult

__all__ = [
    "UserProfile",
    "CriterionSpec",
    "DEFAULT_CRITERIA",
    "DEFAULT_WEIGHTS",
    "WEIGHT_PRESETS",
    "TCOCalculator",
    "load_seed",
    "Filter",
    "BudgetFilter",
    "SegmentFilter",
    "FuelTypeFilter",
    "TransmissionFilter",
    "BodyTypeFilter",
    "MinSeatsFilter",
    "MinPowerFilter",
    "MinClearanceFilter",
    "MinCargoFilter",
    "topsis_rank",
    "RankingStrategy",
    "TopsisStrategy",
    "WeightedSumStrategy",
    "decompose",
    "pareto_front",
    "pareto_front_2d",
    "non_dominated_ranks",
    "compute_pareto_layers",
    "RecommendationService",
    "RecommendationResult",
]
