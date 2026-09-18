from __future__ import annotations

from app.domain.recommendation.candidate import Candidate
from app.domain.recommendation.topsis import ParetoExtractor, TopsisRanker
from app.domain.recommendation.weights import DEFAULT_WEIGHTS


def _c(
    mod_id: int,
    *,
    tco: float,
    price: float,
    rel: float,
    dep: float,
    power: float,
    cargo: float,
) -> Candidate:
    return Candidate(
        modification_id=mod_id,
        make=f"Make{mod_id}",
        model=f"Model{mod_id}",
        generation="I",
        body_type="sedan",
        segment="C",
        fuel_type="AI95",
        drive="FWD",
        transmission="AT",
        tco_5y_rub=tco,
        purchase_price_rub=price,
        reliability_score=rel,
        depreciation_5y_pct=dep,
        power_hp=power,
        cargo_volume_l=cargo,
    )


def test_topsis_prefers_balanced_candidate() -> None:
    candidates = [
        _c(1, tco=1_300_000, price=1_000_000, rel=0.7, dep=45, power=120, cargo=430),
        _c(2, tco=1_450_000, price=900_000, rel=0.95, dep=32, power=190, cargo=540),
        _c(3, tco=1_600_000, price=1_200_000, rel=0.5, dep=48, power=110, cargo=420),
    ]
    scores, _ = TopsisRanker().rank(candidates, DEFAULT_WEIGHTS)
    best = max(range(len(scores)), key=lambda idx: float(scores[idx]))
    assert candidates[best].modification_id == 2


def test_pareto_excludes_dominated_alternative() -> None:
    a = _c(1, tco=1_000_000, price=900_000, rel=0.9, dep=30, power=160, cargo=500)
    b = _c(2, tco=1_100_000, price=950_000, rel=0.8, dep=35, power=150, cargo=450)
    c = _c(3, tco=950_000, price=980_000, rel=0.7, dep=40, power=170, cargo=420)
    ids = ParetoExtractor().extract([a, b, c])
    assert 2 not in ids
    assert 1 in ids
    assert 3 in ids
