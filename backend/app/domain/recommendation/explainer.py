"""Human-readable explanation strings for the top-K.

The explainer picks the **two strongest** criteria for each car and turns
them into a Russian sentence, with optional context like "ниже среднего
на 12 %" / "top-10 % по надёжности".
"""

from __future__ import annotations

from collections.abc import Sequence
from statistics import mean, quantiles

from app.domain.recommendation.candidate import (
    CRITERIA_ORDER,
    CRITERION_DIRECTION,
    Candidate,
    CriterionCode,
)
from app.domain.recommendation.result import CriterionContribution

# Russian labels (genitive — "за низкую …", "за высокую …").
_CRITERION_LABEL_RU: dict[CriterionCode, tuple[str, str]] = {
    "tco_5y": ("низкий TCO", "высокий TCO"),
    "purchase_price": ("низкую цену", "высокую цену"),
    "reliability": ("высокую надёжность", "низкую надёжность"),
    "depreciation": ("малую амортизацию", "высокую амортизацию"),
    "power": ("высокую мощность", "низкую мощность"),
    "cargo": ("вместительный багажник", "малый багажник"),
}


def _quartile_position(
    value: float, all_values: Sequence[float], direction: int
) -> str | None:
    """Return a short tag like 'top-10%' / 'выше среднего' for the value."""
    if len(all_values) < 4:
        return None
    avg = mean(all_values)
    qs = quantiles(all_values, n=10)
    if direction > 0:
        if value >= qs[-1]:
            return "top-10 %"
        if value >= avg:
            return "выше среднего"
        return None
    if value <= qs[0]:
        return "лучшие 10 %"
    if value <= avg:
        return "лучше среднего"
    return None


def build_explanation(
    candidate: Candidate,
    decomposition: dict[CriterionCode, CriterionContribution],
    all_candidates: Sequence[Candidate],
) -> str:
    """Return a 1–2 sentence Russian explanation for one ranked car."""
    sorted_codes = sorted(
        CRITERIA_ORDER,
        key=lambda code: decomposition[code].contribution,
        reverse=True,
    )
    top_two = sorted_codes[:2]

    parts: list[str] = []
    for code in top_two:
        good, _bad = _CRITERION_LABEL_RU[code]
        direction = CRITERION_DIRECTION[code]
        position = _quartile_position(
            candidate.criterion(code),
            [c.criterion(code) for c in all_candidates],
            direction,
        )
        if position:
            parts.append(f"{good} ({position})")
        else:
            parts.append(good)

    return f"{candidate.make} {candidate.model} — за " + " и ".join(parts) + "."


__all__ = ["build_explanation"]
