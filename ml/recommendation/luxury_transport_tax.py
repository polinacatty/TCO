"""Повышающий коэффициент транспортного налога (копия логики backend)."""

from __future__ import annotations

import re
from typing import Optional

import pandas as pd

LUXURY_TRANSPORT_TAX_COEF = 3.0
LUXURY_YEARS_10M_TIER = 10
LUXURY_YEARS_15M_TIER = 20

_FUEL_ALIASES: dict[str, set[str]] = {
    "бензин": {"бензин", "benzin", "petrol", "gasoline", "ai92", "ai95", "ai98"},
    "дизель": {"дизель", "diesel"},
    "гибрид": {"гибрид", "hybrid"},
    "электрический": {"электрический", "электро", "electric", "ev", "bev"},
}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def _fuel_tokens(raw: str) -> set[str]:
    t = _norm(raw)
    for key, aliases in _FUEL_ALIASES.items():
        if t in aliases or key in t:
            return aliases | {key}
    return {t}


def _fuels_compatible(mod_fuel: str, list_fuel: str) -> bool:
    if not mod_fuel or not list_fuel:
        return True
    a = _fuel_tokens(mod_fuel)
    b = _fuel_tokens(list_fuel)
    return bool(a & b) or _norm(mod_fuel) in _norm(list_fuel) or _norm(list_fuel) in _norm(mod_fuel)


def _volumes_compatible(mod_vol: Optional[float], list_vol: str) -> bool:
    if not list_vol or not str(list_vol).strip():
        return True
    try:
        lv = float(str(list_vol).replace(",", "."))
    except ValueError:
        return True
    if mod_vol is None or pd.isna(mod_vol):
        return True
    return abs(float(mod_vol) - lv) <= 0.25


def _model_matches(list_model: str, catalog_model: str, trim_name: str) -> bool:
    lm = _norm(list_model)
    cm = _norm(catalog_model)
    trim = _norm(trim_name or "")
    blob = f"{cm} {trim}".strip()
    if lm in blob or blob in lm:
        return True
    first = cm.split()[0] if cm else ""
    if first and len(first) >= 2 and first in lm:
        return True
    return False


def filter_luxury_candidates(
    luxury_df: pd.DataFrame,
    make_name: str,
    model_name: str,
    trim_name: str,
    fuel_type: str,
    engine_volume_l: Optional[float],
) -> pd.DataFrame:
    if luxury_df.empty:
        return luxury_df.iloc[0:0]
    mk = _norm(make_name)
    sub = luxury_df[luxury_df["make"].map(_norm) == mk]
    if sub.empty:
        return sub
    rows = []
    for _, row in sub.iterrows():
        if not _model_matches(str(row["model"]), model_name, trim_name):
            continue
        if not _fuels_compatible(fuel_type, str(row.get("engine_type") or "")):
            continue
        if not _volumes_compatible(engine_volume_l, str(row.get("engine_volume_l") or "")):
            continue
        rows.append(row)
    if not rows:
        return sub.iloc[0:0]
    return pd.DataFrame(rows)


def luxury_years_limit(candidates: pd.DataFrame) -> int:
    if candidates.empty:
        return 0
    tiers = {str(t).strip() for t in candidates["price_tier_min_rub"].tolist()}
    if "15000000" in tiers:
        return LUXURY_YEARS_15M_TIER
    if "10000000" in tiers:
        return LUXURY_YEARS_10M_TIER
    return LUXURY_YEARS_10M_TIER


def luxury_coef_for_tax_year(
    tax_year: int,
    year_of_manufacture: int,
    candidates: pd.DataFrame,
) -> float:
    if candidates.empty or year_of_manufacture <= 0:
        return 1.0
    limit = luxury_years_limit(candidates)
    if limit <= 0:
        return 1.0
    last_year = year_of_manufacture + limit - 1
    if year_of_manufacture <= tax_year <= last_year:
        return LUXURY_TRANSPORT_TAX_COEF
    return 1.0
