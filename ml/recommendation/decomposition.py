"""Decomposition of TOPSIS closeness coefficient — for UI «почему именно эта машина».

For each top-K candidate, we split rank_score = sum_j contribution_j, where
contribution_j = w_j * (V[i,j] - A_minus[j]) / (S+ + S-) for TOPSIS.

For other strategies (WSM), we simply return w_j * normalized_value as contribution.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .criteria import CriterionSpec, DEFAULT_CRITERIA


def decompose(
    ranked_df: pd.DataFrame,
    weights: dict[str, float],
    criteria: list[CriterionSpec] = None,  # type: ignore[assignment]
    strategy_name: str = "topsis",
) -> list[dict[str, Any]]:
    """Return decomposition list, one per row in `ranked_df`.

    Each item: {
        'modification_id': int,
        'rank': int,
        'rank_score': float,
        'contributions': list[{
            'criterion': str, 'label_ru': str, 'unit': str,
            'value': float,         # raw value
            'contribution': float,  # absolute contribution to rank_score
            'share': float,         # contribution / rank_score
        }],
        'total_share_check': float,  # должна быть ≈ 1.0 (для self-test)
    }
    """
    criteria = criteria or DEFAULT_CRITERIA
    out = []

    for rank_pos, (_, row) in enumerate(ranked_df.iterrows()):
        score = float(row["rank_score"])
        contribs = []

        for c in criteria:
            raw_val = float(row[c.name])
            if strategy_name == "topsis":
                v_col = f"_topsis_v_{c.name}"
                aminus_col = f"_topsis_aminus_{c.name}"
                if v_col not in row or aminus_col not in row:
                    contrib = score * weights[c.name]
                else:
                    s_plus = float(row.get("_topsis_s_plus", 0.0))
                    s_minus = float(row.get("_topsis_s_minus", 0.0))
                    denom = s_plus + s_minus
                    if denom <= 0:
                        contrib = score * weights[c.name]
                    else:
                        v = float(row[v_col])
                        a_minus = float(row[aminus_col])
                        contrib = (abs(v - a_minus)) / denom * np.sign(score)
            else:
                contrib = score * weights[c.name]

            contribs.append({
                "criterion": c.name,
                "label_ru": c.label_ru,
                "unit": c.unit,
                "value": raw_val,
                "contribution": contrib,
                "weight": weights[c.name],
            })

        if strategy_name == "topsis":
            total_abs = sum(abs(x["contribution"]) for x in contribs) or 1.0
            for x in contribs:
                x["share"] = abs(x["contribution"]) / total_abs
        else:
            for x in contribs:
                x["share"] = x["contribution"] / max(score, 1e-9)

        share_sum = sum(x["share"] for x in contribs)
        out.append({
            "modification_id": int(row["modification_id"]) if "modification_id" in row else int(row.name),
            "rank": rank_pos,
            "rank_score": score,
            "contributions": sorted(contribs, key=lambda x: -x["share"]),
            "total_share_check": share_sum,
        })

    return out
