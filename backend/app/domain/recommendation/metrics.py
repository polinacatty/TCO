"""Quality metrics for recommendation ranking."""

from __future__ import annotations

import math
import random
from collections.abc import Mapping, Sequence

from app.domain.recommendation.candidate import CRITERIA_ORDER, Candidate
from app.domain.recommendation.topsis import TopsisRanker
from app.domain.recommendation.weights import RankingWeights


def diversity_at_k(candidates: Sequence[Candidate], k: int = 10) -> int:
    return len({c.make for c in candidates[:k]})


def coverage_ratio(
    top: Sequence[Candidate],
    all_candidates: Sequence[Candidate],
    *,
    k: int = 10,
) -> float:
    top_pairs = {(c.segment, c.make) for c in top[:k]}
    all_pairs = {(c.segment, c.make) for c in all_candidates}
    if not all_pairs:
        return 0.0
    return len(top_pairs) / len(all_pairs)


def ndcg_at_k(
    ranked: Sequence[Candidate],
    relevance: Mapping[int, int],
    *,
    k: int = 10,
) -> float:
    """Compute NDCG@K with explicit relevance labels by modification id."""
    if k <= 0:
        return 0.0
    gains = [relevance.get(c.modification_id, 0) for c in ranked[:k]]
    dcg = sum(rel / math.log2(i + 2) for i, rel in enumerate(gains))
    ideal = sorted(relevance.values(), reverse=True)[:k]
    idcg = sum(rel / math.log2(i + 2) for i, rel in enumerate(ideal))
    if idcg == 0:
        return 0.0
    return dcg / idcg


def stability_at_k(
    candidates: Sequence[Candidate],
    base_weights: RankingWeights,
    *,
    k: int = 10,
    iterations: int = 40,
    jitter: float = 0.05,
) -> float:
    """Top-K overlap under random +/- jitter of weights."""
    if not candidates:
        return 0.0

    ranker = TopsisRanker()
    base_scores, _ = ranker.rank(candidates, base_weights)
    base_ids = {
        candidates[i].modification_id
        for i in sorted(range(len(candidates)), key=lambda idx: base_scores[idx], reverse=True)[:k]
    }
    if not base_ids:
        return 0.0

    overlaps: list[float] = []
    for _ in range(iterations):
        perturbed = _perturb_weights(base_weights, jitter=jitter)
        scores, _ = ranker.rank(candidates, perturbed)
        ids = {
            candidates[i].modification_id
            for i in sorted(range(len(candidates)), key=lambda idx: scores[idx], reverse=True)[:k]
        }
        overlaps.append(len(base_ids & ids) / len(base_ids))
    return sum(overlaps) / len(overlaps)


def _perturb_weights(weights: RankingWeights, *, jitter: float) -> RankingWeights:
    perturbed = {}
    for code in CRITERIA_ORDER:
        base = getattr(weights, code)
        factor = random.uniform(1 - jitter, 1 + jitter)
        perturbed[code] = max(0.0001, base * factor)
    total = sum(perturbed.values())
    normalised: dict[str, float] = {
        str(code): float(value / total) for code, value in perturbed.items()
    }
    return RankingWeights.from_dict(normalised)


__all__ = ["coverage_ratio", "diversity_at_k", "ndcg_at_k", "stability_at_k"]
