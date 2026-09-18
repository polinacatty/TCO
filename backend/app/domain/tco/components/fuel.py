"""Fuel / electricity component (`C_fuel`) — monthly sum over SARIMA forecast.

    C_fuel(T) = Σ_{t=1..12T}  (F_eff × M / 12 / 100) × P̂(region, fuel, t)

* ``F_eff`` — paspart consumption with a 0.85 factor for HYBRID
* ``M / 12`` — equal monthly distribution of annual kilometres
* ``P̂(region, fuel, t)`` — ₽/litre from materialised ``fuel_price_forecast``
  for the month ``calculation_start_date + t``.

If the requested region has no forecast rows we transparently fall back to
the ``RU_AVG`` block (``region_id = 0``). For ``AI98`` we use
``AI95 × 1.08`` if there is no own ``AI98`` series — matches the SARIMA
training set documented in ``docs/04_ml_models/01_fuel_sarima_methodology.md``.

ELECTRIC keeps its own simple flat tariff — see ``EV_PRICE_RUB_PER_KWH``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.domain.profile import UserProfile
from app.domain.tco.snapshots import CarSnapshot, FuelPriceForecastSnapshot

_DEFAULT_CONSUMPTION_L_PER_100KM = Decimal("8.0")
_HYBRID_FACTOR = Decimal("0.85")

# Fallback flat tariff for electric cars (₽/kWh) — see methodology §8.1.
EV_PRICE_RUB_PER_KWH = Decimal("6.5")

# AI98 ≈ AI95 × 1.08 — methodology §8.3 / §8.5.
_AI98_FROM_AI95_FACTOR = Decimal("1.08")

# Fuel-type aliases ->  what we look up in ``fuel_price_forecast``.
_FUEL_KEY_MAP: dict[str, str] = {
    "AI92": "ai92",
    "AI95": "ai95",
    "AI98": "ai98",
    "DIESEL": "diesel",
}

# Hard fallback if no forecast row exists at all (extreme edge case).
_DEFAULT_PRICES: dict[str, Decimal] = {
    "ai92": Decimal("55"),
    "ai95": Decimal("60"),
    "ai98": Decimal("70"),
    "diesel": Decimal("65"),
}


@dataclass(frozen=True, slots=True)
class FuelBreakdown:
    fuel_type: str
    consumption_l_per_100km: Decimal
    monthly_litres: Decimal
    months: int
    yearly_amounts_rub: tuple[int, ...]
    used_forecast_rows: int
    used_ru_avg_fallback: bool
    used_ai98_from_ai95: bool
    used_default_constant: bool
    average_price_rub_per_l: Decimal


def _months_iter(start: date, count: int) -> list[date]:
    """Generate first-of-month dates starting from start (truncated to day=1)."""
    out: list[date] = []
    year = start.year
    month = start.month
    for _ in range(count):
        out.append(date(year, month, 1))
        month += 1
        if month > 12:
            month = 1
            year += 1
    return out


def _index_by_month(
    rows: Sequence[FuelPriceForecastSnapshot],
) -> dict[date, Decimal]:
    return {r.price_month: r.price_rub_per_l for r in rows}


def _pick_price(
    month: date,
    primary: dict[date, Decimal],
    ru_avg: dict[date, Decimal],
    ai95_primary: dict[date, Decimal],
    ai95_ru_avg: dict[date, Decimal],
    fuel_key: str,
    flags: dict[str, bool],
) -> Decimal:
    """Resolve price for one month with the full fallback chain."""
    if month in primary:
        return primary[month]
    if month in ru_avg:
        flags["used_ru_avg_fallback"] = True
        return ru_avg[month]
    if fuel_key == "ai98":
        if month in ai95_primary:
            flags["used_ai98_from_ai95"] = True
            return ai95_primary[month] * _AI98_FROM_AI95_FACTOR
        if month in ai95_ru_avg:
            flags["used_ai98_from_ai95"] = True
            flags["used_ru_avg_fallback"] = True
            return ai95_ru_avg[month] * _AI98_FROM_AI95_FACTOR
    flags["used_default_constant"] = True
    return _DEFAULT_PRICES.get(fuel_key, Decimal("60"))


def _round_yearly_amounts(yearly_raw: Sequence[Decimal], total: int) -> tuple[int, ...]:
    yearly = [int(v.quantize(Decimal("1"))) for v in yearly_raw]
    if yearly:
        yearly[-1] += total - sum(yearly)
    return tuple(yearly)


class FuelComponent:
    """Compute ``C_fuel`` as the monthly sum over the SARIMA forecast."""

    def compute(
        self,
        profile: UserProfile,
        car: CarSnapshot,
        forecast: Sequence[FuelPriceForecastSnapshot],
        forecast_ru_avg: Sequence[FuelPriceForecastSnapshot],
        calculation_start_date: date,
        forecast_ai95_region: Sequence[FuelPriceForecastSnapshot] = (),
        forecast_ai95_ru_avg: Sequence[FuelPriceForecastSnapshot] = (),
    ) -> tuple[int, FuelBreakdown]:
        # ----- consumption ---------------------------------------------------
        cons = car.fuel_consumption_combined_l_100km or _DEFAULT_CONSUMPTION_L_PER_100KM
        fuel_type = car.fuel_type.upper() if car.fuel_type else "AI95"

        if fuel_type == "ELECTRIC":
            litres_per_year = cons * Decimal(profile.mileage_per_year_km) / Decimal(100)
            yearly_raw = [
                litres_per_year * EV_PRICE_RUB_PER_KWH
                for _ in range(profile.horizon_years)
            ]
            total = int(
                sum(yearly_raw, Decimal("0"))
                .quantize(Decimal("1"))
            )
            return total, FuelBreakdown(
                fuel_type=fuel_type,
                consumption_l_per_100km=cons,
                monthly_litres=Decimal("0"),
                months=profile.horizon_years * 12,
                yearly_amounts_rub=_round_yearly_amounts(yearly_raw, total),
                used_forecast_rows=0,
                used_ru_avg_fallback=False,
                used_ai98_from_ai95=False,
                used_default_constant=True,
                average_price_rub_per_l=EV_PRICE_RUB_PER_KWH,
            )

        if fuel_type == "HYBRID":
            cons = cons * _HYBRID_FACTOR

        fuel_key = _FUEL_KEY_MAP.get(fuel_type, "ai95")

        # ----- monthly schedule + price lookup -------------------------------
        months = _months_iter(calculation_start_date, profile.horizon_years * 12)
        primary = _index_by_month(forecast)
        ru_avg = _index_by_month(forecast_ru_avg)
        ai95_p = _index_by_month(forecast_ai95_region)
        ai95_r = _index_by_month(forecast_ai95_ru_avg)

        flags = {
            "used_ru_avg_fallback": False,
            "used_ai98_from_ai95": False,
            "used_default_constant": False,
        }

        monthly_litres = cons * Decimal(profile.mileage_per_year_km) / Decimal(12) / Decimal(100)

        total_rub = Decimal("0")
        price_sum = Decimal("0")
        yearly_raw = [Decimal("0") for _ in range(profile.horizon_years)]
        for idx, m in enumerate(months):
            price = _pick_price(m, primary, ru_avg, ai95_p, ai95_r, fuel_key, flags)
            month_amount = monthly_litres * price
            total_rub += month_amount
            yearly_raw[idx // 12] += month_amount
            price_sum += price

        avg_price = (price_sum / Decimal(len(months))).quantize(Decimal("0.01"))
        total_int = int(total_rub.quantize(Decimal("1")))
        used_rows = len(forecast) or len(forecast_ru_avg)
        if not used_rows and fuel_key == "ai98":
            used_rows = len(forecast_ai95_region) or len(forecast_ai95_ru_avg)

        breakdown = FuelBreakdown(
            fuel_type=fuel_type,
            consumption_l_per_100km=cons,
            monthly_litres=monthly_litres,
            months=len(months),
            yearly_amounts_rub=_round_yearly_amounts(yearly_raw, total_int),
            used_forecast_rows=used_rows,
            used_ru_avg_fallback=flags["used_ru_avg_fallback"],
            used_ai98_from_ai95=flags["used_ai98_from_ai95"],
            used_default_constant=flags["used_default_constant"],
            average_price_rub_per_l=avg_price,
        )
        return total_int, breakdown


__all__ = ["FuelComponent", "FuelBreakdown", "EV_PRICE_RUB_PER_KWH"]
