"""Pure helpers reused by several TCO components."""

from __future__ import annotations

# 12 catalog segments → 6 working segments used in depreciation / KASKO / parts cost.
# Order of fallback: any value not in this map falls back to "C_D".
_SEGMENT_11_TO_6: dict[str, str] = {
    "A": "A_B",
    "B": "A_B",
    "C": "C_D",
    "D": "C_D",
    "OTHER": "C_D",
    "E": "E_F",
    "F": "E_F",
    "S_SPORT": "E_F",
    "J_CROSS": "J_CROSS",
    "M_MPV": "J_CROSS",
    "J_SUV": "J_SUV",
    "LCV": "LCV",
}


def segment_to_segment6(segment: str) -> str:
    """Collapse 12 catalog segments into 6 working segments (with C_D fallback)."""
    return _SEGMENT_11_TO_6.get(segment, "C_D")


_KOREA_NAMES = frozenset({"south korea", "korea", "south korea (republic)"})
_JAPAN_NAMES = frozenset({"japan"})
_USA_NAMES = frozenset({"usa", "united states", "united states of america"})


def map_brand_segment(brand_tier: str, country: str | None) -> str:
    """Map (brand_tier, country) → one of 7 ``brand_segment`` codes used in
    ``parts_costs.csv``.

    Rules:

    * ``russian`` / ``chinese`` → same
    * ``japanese_korean_mass`` → ``japanese`` or ``korean`` (by country)
    * ``mass``                 → ``american`` if USA, else ``european_mass``
    * ``premium``              → ``japanese`` / ``korean`` for JP/KR brands,
                                 otherwise ``european_premium``
    """
    country_low = (country or "").strip().lower()
    is_korea = country_low in _KOREA_NAMES
    is_japan = country_low in _JAPAN_NAMES
    is_usa = country_low in _USA_NAMES

    if brand_tier == "russian":
        return "russian"
    if brand_tier == "chinese":
        return "chinese"
    if brand_tier == "japanese_korean_mass":
        return "korean" if is_korea else "japanese"
    if brand_tier == "mass":
        return "american" if is_usa else "european_mass"
    if brand_tier == "premium":
        if is_japan:
            return "japanese"
        if is_korea:
            return "korean"
        return "european_premium"

    # Unknown tier — safest "average" choice.
    return "european_mass"


def hits_for_interval(
    total_km: int,
    total_months: int,
    every_km: int | None,
    every_months: int | None,
) -> int:
    """Return number of times a scheduled operation fires over the horizon.

    Implements: integer division (the first hit happens
    *after* a full interval has been accumulated, never at km/month 0);
    when both km and time intervals are set we take ``max(km, time)`` —
    documented over-approximation aligned with the calibration baseline.
    """
    hits_km = total_km // every_km if every_km and every_km > 0 else 0
    hits_months = total_months // every_months if every_months and every_months > 0 else 0
    return max(hits_km, hits_months)


__all__ = ["segment_to_segment6", "map_brand_segment", "hits_for_interval"]
