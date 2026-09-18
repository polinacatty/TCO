"""TOPSIS implementation + Pareto-front extraction."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray

from app.domain.recommendation.candidate import (
    CRITERIA_ORDER,
    CRITERION_DIRECTION,
    Candidate,
    CriterionCode,
)
from app.domain.recommendation.result import CriterionContribution
from app.domain.recommendation.weights import RankingWeights


class TopsisRanker:
    
    def rank(
        self,
        candidates: Sequence[Candidate],
        weights: RankingWeights,
    ) -> tuple[NDArray[np.float64], list[dict[CriterionCode, CriterionContribution]]]:
        """Rank the candidates, returning ``(closeness, decomposition)``.

        Both lists are aligned with ``candidates`` (i.e. ``closeness[i]`` and
        ``decomposition[i]`` refer to ``candidates[i]``).
        """
        if not candidates:
            return np.zeros(0), []

        n = len(candidates)
        m = len(CRITERIA_ORDER)

        # ---- Step 1: decision matrix X (n × m) ------------------------------
        x = np.empty((n, m), dtype=float)
        for j, code in enumerate(CRITERIA_ORDER):
            for i, c in enumerate(candidates):
                x[i, j] = c.criterion(code)

        # ---- Step 2: vector normalization R[i, j] = X / sqrt(Σ X²) -----------
        norms = np.sqrt(np.sum(x**2, axis=0))
        # Avoid division by zero — fallback to 1/n for degenerate criteria.
        safe_norms = np.where(norms == 0, 1.0, norms)
        r = x / safe_norms
        for j in range(m):
            if norms[j] == 0:
                r[:, j] = 1.0 / n

        # ---- Step 3: weighted matrix V[i, j] = w[j] × R[i, j] ----------------
        w_vec = np.array([getattr(weights, code) for code in CRITERIA_ORDER])
        v = r * w_vec

        # ---- Step 4: ideal (A+) and anti-ideal (A−) per direction ------------
        a_plus = np.empty(m)
        a_minus = np.empty(m)
        for j, code in enumerate(CRITERIA_ORDER):
            col = v[:, j]
            if CRITERION_DIRECTION[code] > 0:
                a_plus[j] = col.max()
                a_minus[j] = col.min()
            else:
                a_plus[j] = col.min()
                a_minus[j] = col.max()

        # ---- Step 5: Euclidean distances -------------------------------------
        s_plus = np.sqrt(np.sum((v - a_plus) ** 2, axis=1))
        s_minus = np.sqrt(np.sum((v - a_minus) ** 2, axis=1))

        denom = s_plus + s_minus
        closeness = np.where(denom == 0, 0.5, s_minus / np.where(denom == 0, 1.0, denom))

        # ---- Step 7 (decomposition for UI, §7) -------------------------------
        # contribution_j = w_j × (V[i, j] − A_minus[j]) / (S+ + S−)
        # The contributions sum to closeness[i] = S− / (S+ + S−).
        # We re-derive them per candidate for clarity.
        decompositions: list[dict[CriterionCode, CriterionContribution]] = []
        for i in range(n):
            decomp: dict[CriterionCode, CriterionContribution] = {}
            denom_i = s_plus[i] + s_minus[i]
            for j, code in enumerate(CRITERIA_ORDER):
                if denom_i == 0:
                    contrib = w_vec[j] / m
                else:
                    contrib = float(
                        np.abs(v[i, j] - a_minus[j]) / denom_i
                    )
                decomp[code] = CriterionContribution(
                    value=float(x[i, j]),
                    normalized=float(v[i, j]),
                    contribution=contrib,
                )
            decompositions.append(decomp)

        return closeness, decompositions


class ParetoExtractor:
    """Extract the Pareto-optimal subset (no candidate dominated by another).

    A candidate ``a`` *dominates* ``b`` iff for every criterion ``a`` is at
    least as good as ``b`` and strictly better for at least one criterion.
    Returns ``modification_id``-s of non-dominated candidates.
    """

    def extract(self, candidates: Sequence[Candidate]) -> tuple[int, ...]:
        n = len(candidates)
        if n <= 1:
            return tuple(c.modification_id for c in candidates)

        m = len(CRITERIA_ORDER)
        x = np.empty((n, m), dtype=float)
        directions = np.empty(m, dtype=float)
        for j, code in enumerate(CRITERIA_ORDER):
            directions[j] = CRITERION_DIRECTION[code]
            for i, c in enumerate(candidates):
                x[i, j] = c.criterion(code)

        # Convert minimize → maximize by multiplying by direction sign.
        xx = x * directions

        non_dominated: list[int] = []
        for i in range(n):
            dominated = False
            for k in range(n):
                if k == i:
                    continue
                if np.all(xx[k] >= xx[i]) and np.any(xx[k] > xx[i]):
                    dominated = True
                    break
            if not dominated:
                non_dominated.append(candidates[i].modification_id)
        return tuple(non_dominated)


__all__ = ["TopsisRanker", "ParetoExtractor"]
