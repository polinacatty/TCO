"""UserProfile — структура запроса пользователя для подбора автомобиля."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


DEFAULT_WEIGHTS: dict[str, float] = {
    "tco_5y": 0.30,
    "purchase_price": 0.20,
    "reliability_score": 0.20,
    "depreciation_5y_pct": 0.10,
    "power_hp": 0.10,
    "cargo_volume_l": 0.10,
}


WEIGHT_PRESETS: dict[str, dict[str, float]] = {
    "balanced": DEFAULT_WEIGHTS,
    "cheapest": {
        "tco_5y": 0.40, "purchase_price": 0.40, "reliability_score": 0.10,
        "depreciation_5y_pct": 0.05, "power_hp": 0.025, "cargo_volume_l": 0.025,
    },
    "family": {
        "tco_5y": 0.20, "purchase_price": 0.10, "reliability_score": 0.30,
        "depreciation_5y_pct": 0.05, "power_hp": 0.10, "cargo_volume_l": 0.25,
    },
    "premium": {
        "tco_5y": 0.15, "purchase_price": 0.05, "reliability_score": 0.20,
        "depreciation_5y_pct": 0.20, "power_hp": 0.30, "cargo_volume_l": 0.10,
    },
    "student": {
        "tco_5y": 0.30, "purchase_price": 0.50, "reliability_score": 0.10,
        "depreciation_5y_pct": 0.05, "power_hp": 0.025, "cargo_volume_l": 0.025,
    },
    "business": {
        "tco_5y": 0.30, "purchase_price": 0.10, "reliability_score": 0.20,
        "depreciation_5y_pct": 0.20, "power_hp": 0.15, "cargo_volume_l": 0.05,
    },
}


@dataclass
class UserProfile:
    """Параметры запроса пользователя.

    Attributes:
        budget_rub: максимальный бюджет на покупку, ₽
        region_id: ID региона (для tax/osago/fuel_prices)
        mileage_per_year_km: пробег в год, км
        horizon_years: горизонт владения, лет (default 5)
        year_of_manufacture: год выпуска ТС (ПТС); при None — из age_at_purchase_years
        age_at_purchase_years: возраст при покупке, лет (0 = новый)
        sto_type: тип СТО для расчёта ТО (private/independent/dealer)
        include_kasko: учитывать ли КАСКО в TCO (default False)
        weights: веса критериев (или None → DEFAULT_WEIGHTS)
        weight_preset: имя пресета (использовать вместо weights)
        preferred_segments: список разрешённых сегментов (или None — все)
        allowed_fuel_types: список разрешённых типов топлива (или None — все)
        allowed_transmissions: ...
        allowed_body_types: ...
        min_seats: минимум мест
        min_power_hp: минимум л.с.
        min_clearance_mm: минимальный клиренс
        min_cargo_volume_l: минимум объёма багажника
    """

    budget_rub: float
    region_id: int
    mileage_per_year_km: int = 15_000
    horizon_years: int = 5
    year_of_manufacture: Optional[int] = None
    age_at_purchase_years: int = 0
    sto_type: str = "independent"
    include_kasko: bool = False

    weights: Optional[dict[str, float]] = None
    weight_preset: Optional[str] = None

    preferred_segments: Optional[list[str]] = None
    allowed_fuel_types: Optional[list[str]] = None
    allowed_transmissions: Optional[list[str]] = None
    allowed_body_types: Optional[list[str]] = None

    min_seats: Optional[int] = None
    min_power_hp: Optional[int] = None
    min_clearance_mm: Optional[int] = None
    min_cargo_volume_l: Optional[int] = None

    extras: dict = field(default_factory=dict)

    def resolve_weights(self) -> dict[str, float]:
        """Return effective weights: explicit > preset > default."""
        if self.weights is not None:
            w = dict(self.weights)
        elif self.weight_preset is not None:
            if self.weight_preset not in WEIGHT_PRESETS:
                raise ValueError(
                    f"unknown weight_preset {self.weight_preset!r}; "
                    f"valid: {sorted(WEIGHT_PRESETS)}"
                )
            w = dict(WEIGHT_PRESETS[self.weight_preset])
        else:
            w = dict(DEFAULT_WEIGHTS)

        s = sum(w.values())
        if abs(s - 1.0) > 1e-6:
            w = {k: v / s for k, v in w.items()}
        return w
