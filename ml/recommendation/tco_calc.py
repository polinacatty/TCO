"""Reusable TCO calculator (extracted from `_tco_calibrate.py`).

`TCOCalculator(seed_data)` is constructed once with all seed tables loaded,
then `compute(modification, user_profile)` returns a dict with all 7 components
and the total. Designed for batch use in `RecommendationService` (~ 0.5–2 ms/call).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from datetime import date

import pandas as pd

from .luxury_transport_tax import filter_luxury_candidates, luxury_coef_for_tax_year

ROOT = Path(__file__).resolve().parents[2]
SEED = ROOT / "ml" / "data" / "seed"
PROCESSED = ROOT / "ml" / "data" / "processed"


SEGMENT_11_TO_6: dict[str, str] = {
    "A": "A_B",
    "B": "A_B",
    "C": "C_D",
    "D": "C_D",
    "E": "E_F",
    "F": "E_F",
    "S_SPORT": "E_F",
    "M_MPV": "J_CROSS",
    "J_CROSS": "J_CROSS",
    "J_SUV": "J_SUV",
    "LCV": "LCV",
}


def map_brand_segment(brand_tier: str, country: str) -> str:
    """`(brand_tier, country) -> brand_segment` for parts_costs (7 values)."""
    if brand_tier == "russian":
        return "russian"
    if brand_tier == "chinese":
        return "chinese"
    if brand_tier == "premium":
        if country in ("Japan", "South Korea"):
            return "japanese"
        return "european_premium"
    if brand_tier == "japanese_korean_mass":
        if country in ("South Korea", "Korea"):
            return "korean"
        return "japanese"
    if brand_tier == "mass":
        if country in ("USA", "United States"):
            return "american"
        return "european_mass"
    return "european_mass"


OSAGO_TYPICAL_KBM = 1.0
OSAGO_TYPICAL_KVS = 0.93    # 30+ лет, стаж 5+
OSAGO_TYPICAL_KO = 1.0
OSAGO_TYPICAL_KS = 1.0


TIRE_LIFETIME_KM = 50_000
TIRE_CHANGE_COST_RUB = 2_500
TYPICAL_SIZE_BY_SEGMENT6: dict[str, str] = {
    "A_B": "185/65 R15",
    "C_D": "205/55 R16",
    "E_F": "225/45 R17",
    "J_CROSS": "215/65 R17",
    "J_SUV": "265/65 R17",
    "LCV": "195/65 R15",
}
DEFAULT_SUMMER_SET_RUB = 15_000
DEFAULT_WINTER_SET_RUB = 18_000
DEFAULT_FUEL_PRICE_RUB_PER_L = {
    "ai92": 55.0,
    "ai95": 60.0,
    "ai98": 70.0,
    "diesel": 65.0,
}
EV_PRICE_RUB_PER_KWH = 6.5
AI98_FROM_AI95_FACTOR = 1.08


@dataclass
class TCOResult:
    depreciation: int
    fuel: int
    osago: int
    transport_tax: int
    maintenance: int
    tyres: int
    kasko: int
    total: int

    def to_dict(self) -> dict[str, int]:
        return {
            "tco_depreciation": self.depreciation,
            "tco_fuel": self.fuel,
            "tco_osago": self.osago,
            "tco_transport_tax": self.transport_tax,
            "tco_maintenance": self.maintenance,
            "tco_tyres": self.tyres,
            "tco_kasko": self.kasko,
            "tco_total": self.total,
        }


def load_seed() -> dict[str, pd.DataFrame]:
    """Load all seed tables required for TCO calculation."""
    data = {
        "makes": pd.read_csv(SEED / "car_makes.csv"),
        "models": pd.read_csv(SEED / "car_models.csv"),
        "generations": pd.read_csv(SEED / "car_generations.csv"),
        "modifications": pd.read_parquet(PROCESSED / "car_modifications.parquet"),
        "regions": pd.read_csv(SEED / "regions.csv"),
        "depreciation": pd.read_csv(SEED / "depreciation_rates.csv"),
        "mileage_penalties": pd.read_csv(SEED / "mileage_penalties.csv"),
        "fuel_prices": pd.read_parquet(PROCESSED / "fuel_prices.parquet"),
        "osago_base": pd.read_csv(SEED / "osago_base_tariffs.csv"),
        "osago_power": pd.read_csv(SEED / "osago_power.csv"),
        "osago_territory": pd.read_csv(SEED / "osago_territory_coefs.csv"),
        "transport_tax": pd.read_csv(SEED / "transport_tax_rates.csv"),
        "luxury": pd.read_csv(SEED / "luxury_car_list.csv"),
        "service_ops": pd.read_csv(SEED / "service_operations.csv"),
        "service_plan_ops": pd.read_csv(SEED / "service_plan_ops.csv"),
        "parts_costs": pd.read_csv(SEED / "parts_costs.csv"),
        "labor_rates": pd.read_csv(SEED / "labor_rates.csv"),
        "tire_sizes": pd.read_csv(SEED / "tire_sizes.csv"),
        "tire_size_prices": pd.read_csv(SEED / "tire_size_prices.csv"),
        "kasko_rates": pd.read_csv(SEED / "kasko_rates.csv"),
    }
    return data


def _pair_price_rub(prices: pd.DataFrame, size_code: str) -> tuple[float, float]:
    summer = prices[(prices["size_code"] == size_code) & (prices["season"] == "summer")]
    winter = prices[(prices["size_code"] == size_code) & (prices["season"] == "winter")]
    ps = float(summer.iloc[0]["avg_set_price_rub"]) if not summer.empty else DEFAULT_SUMMER_SET_RUB
    pw = float(winter.iloc[0]["avg_set_price_rub"]) if not winter.empty else DEFAULT_WINTER_SET_RUB
    return ps, pw


def tire_size_codes_for_modification(
    modification_id: int,
    tire_sizes: pd.DataFrame,
    segment6: str,
) -> list[str]:
    """Штатные размеры из tire_sizes; fallback — типовый по segment6."""
    rows = tire_sizes[tire_sizes["modification_id"] == modification_id]
    if rows.empty:
        return [TYPICAL_SIZE_BY_SEGMENT6.get(segment6, "205/55 R16")]
    both = rows[rows["axle"] == "both"]
    if not both.empty:
        return [str(both.iloc[0]["size_code"])]
    codes: list[str] = []
    for axle in ("front", "rear"):
        sub = rows[rows["axle"] == axle]
        if not sub.empty:
            codes.append(str(sub.iloc[0]["size_code"]))
    if codes:
        return codes
    return [TYPICAL_SIZE_BY_SEGMENT6.get(segment6, "205/55 R16")]


def cycle_summer_winter_cost_rub(prices: pd.DataFrame, size_codes: list[str]) -> float:
    """Стоимость одного цикла «лето + зима» по всем осям (staggered = сумма осей)."""
    total = 0.0
    for code in size_codes:
        ps, pw = _pair_price_rub(prices, code)
        total += ps + pw
    return total


def calc_tyres_cost(
    modification_id: int,
    segment6: str,
    horizon: int,
    mileage_per_year: int,
    tire_sizes: pd.DataFrame,
    tire_prices: pd.DataFrame,
) -> int:
    size_codes = tire_size_codes_for_modification(modification_id, tire_sizes, segment6)
    cycle_cost = cycle_summer_winter_cost_rub(tire_prices, size_codes)
    sets_needed = (mileage_per_year * horizon) // TIRE_LIFETIME_KM
    return int(cycle_cost * sets_needed + TIRE_CHANGE_COST_RUB * 2 * horizon)


class TCOCalculator:
    """Reusable TCO calculator for `RecommendationService`."""

    def __init__(self, seed: dict[str, pd.DataFrame]):
        self.seed = seed
        self._fuel_price_cache: dict[tuple[int, str], float] = {}

    def _get_fuel_price(self, region_id: int, fuel_key: str) -> float:
        cache_key = (region_id, fuel_key)
        if cache_key in self._fuel_price_cache:
            return self._fuel_price_cache[cache_key]

        sub = self.seed["fuel_prices"]
        rows = sub[(sub["region_id"] == region_id) & (sub["fuel_type"] == fuel_key)]
        if rows.empty and fuel_key == "ai98":
            rows95 = sub[(sub["region_id"] == region_id) & (sub["fuel_type"] == "ai95")]
            if not rows95.empty:
                p = float(rows95.sort_values("price_month").iloc[-1]["price_rub_per_l"]) * AI98_FROM_AI95_FACTOR
                self._fuel_price_cache[cache_key] = p
                return p

        if rows.empty:
            p = DEFAULT_FUEL_PRICE_RUB_PER_L.get(fuel_key, 60.0)
        else:
            latest = rows.sort_values("price_month").iloc[-1]
            p = float(latest["price_rub_per_l"])

        self._fuel_price_cache[cache_key] = p
        return p

    def _calc_depreciation(self, msrp: int, segment6: str, brand_tier: str,
                           horizon: int, mileage_total_km: int) -> int:
        depr_df = self.seed["depreciation"]
        rates = depr_df[(depr_df["segment"] == segment6) & (depr_df["brand_tier"] == brand_tier)]
        if rates.empty:
            return msrp // 2
        rates = rates.sort_values("age_year_bucket")

        residual = msrp
        for age in range(1, horizon + 1):
            bucket = min(age, 5)
            rows = rates[rates["age_year_bucket"] == bucket]
            if rows.empty:
                continue
            rate_pct = rows.iloc[0]["annual_depreciation_pct"]
            residual *= (1.0 - rate_pct / 100.0)

        mileage_penalty_pct = 0.0
        for _, row in self.seed["mileage_penalties"].iterrows():
            if mileage_total_km >= row["mileage_threshold_km"]:
                mileage_penalty_pct = row["extra_depreciation_pct"]
        residual *= (1.0 - mileage_penalty_pct / 100.0)

        return max(0, msrp - int(residual))

    def _calc_fuel(self, mod: pd.Series, region_id: int, mileage_per_year: int, horizon: int) -> int:
        fuel_type_raw = (mod.get("fuel_type") or "").upper()
        consumption = mod.get("fuel_consumption_combined_l_100km")
        if consumption is None or pd.isna(consumption):
            consumption = 8.0

        if fuel_type_raw == "ELECTRIC":
            kwh_per_year = float(consumption) * mileage_per_year / 100.0
            return int(kwh_per_year * EV_PRICE_RUB_PER_KWH * horizon)

        if fuel_type_raw == "HYBRID":
            consumption = float(consumption) * 0.85

        fuel_key_map = {"AI92": "ai92", "AI95": "ai95", "AI98": "ai98", "DIESEL": "diesel"}
        fuel_key = fuel_key_map.get(fuel_type_raw, "ai95")
        price_per_l = self._get_fuel_price(region_id, fuel_key)
        liters_per_year = float(consumption) * mileage_per_year / 100.0
        return int(liters_per_year * price_per_l * horizon)

    def _osago_km(self, power_hp: float, vehicle_family: str = "B_BE") -> float:
        sub = self.seed["osago_power"]
        sub = sub[sub["vehicle_family"] == vehicle_family]
        for _, row in sub.iterrows():
            lo = float(row["power_min_hp_excl"])
            hi = float(row["power_max_hp_incl"])
            if lo < power_hp <= hi:
                return float(row["km_value"])
        return 1.0

    def _osago_kt(self, region_id: int) -> float:
        rows = self.seed["osago_territory"][self.seed["osago_territory"]["region_id"] == region_id]
        if rows.empty:
            raise ValueError(f"no OSAGO KT for region_id={region_id}")
        return float(rows.iloc[0]["kt_general"])

    def _calc_osago(self, power_hp: float, region_id: int, horizon: int) -> int:
        base_rows = self.seed["osago_base"]
        cat = base_rows[base_rows["category_id"] == "2.2"]
        if cat.empty:
            tb = 5000
        else:
            tb = (cat.iloc[0]["tb_min_rub"] + cat.iloc[0]["tb_max_rub"]) / 2

        kt = self._osago_kt(region_id)
        km = self._osago_km(power_hp)
        cost = (
            tb * kt * OSAGO_TYPICAL_KBM * OSAGO_TYPICAL_KVS
            * OSAGO_TYPICAL_KO * km * OSAGO_TYPICAL_KS
        )
        return int(cost * horizon)

    def _rate_per_hp(self, power_hp: float, region_id: int) -> float:
        tax_df = self.seed["transport_tax"]
        rates = tax_df[tax_df["region_id"] == region_id]
        if rates.empty:
            rates = tax_df[tax_df["region_id"] == 0]
        rate = 5.0
        for _, row in rates.iterrows():
            hp_min = float(row["hp_min"]) if not pd.isna(row["hp_min"]) else 0
            hp_max = float(row["hp_max"]) if not pd.isna(row["hp_max"]) else 99999
            if hp_min <= power_hp <= hp_max:
                rate = float(row["rate_rub_per_hp"])
                break
        return rate

    def _calc_transport_tax(
        self,
        modification: pd.Series,
        power_hp: float,
        region_id: int,
        horizon: int,
        year_of_manufacture: int,
        make_name: str,
        model_name: str,
        tax_year_start: int | None = None,
    ) -> int:
        rate = self._rate_per_hp(power_hp, region_id)
        luxury_df = self.seed["luxury"]
        engine_l = modification.get("engine_volume_l")
        if engine_l is None or pd.isna(engine_l):
            engine_l = None
        else:
            engine_l = float(engine_l)
        candidates = filter_luxury_candidates(
            luxury_df,
            make_name,
            model_name,
            str(modification.get("trim_name") or ""),
            str(modification.get("fuel_type") or ""),
            engine_l,
        )
        y_start = tax_year_start if tax_year_start is not None else date.today().year
        y_mfg = int(year_of_manufacture)
        total = 0
        for year_idx in range(horizon):
            tax_year = y_start + year_idx
            coef = luxury_coef_for_tax_year(tax_year, y_mfg, candidates)
            total += int(rate * power_hp * coef)
        return total

    def _calc_maintenance(self, generation_id: int, brand_segment: str, region_id: int,
                          sto_type: str, mileage_per_year: int, horizon: int) -> int:
        plan = self.seed["service_plan_ops"]
        plan_rows = plan[plan["generation_id"] == generation_id]
        if plan_rows.empty:
            return 0

        labor_df = self.seed["labor_rates"]
        labor_row = labor_df[(labor_df["region_id"] == region_id) & (labor_df["sto_type"] == sto_type)]
        if labor_row.empty:
            labor_row = labor_df[(labor_df["region_id"] == 1) & (labor_df["sto_type"] == sto_type)]
        labor_rate = float(labor_row.iloc[0]["rate_rub_per_hour"]) if not labor_row.empty else 1500.0

        total_mileage = mileage_per_year * horizon
        total_months = horizon * 12
        total = 0

        ops_meta = self.seed["service_ops"].set_index("id")
        parts = self.seed["parts_costs"]

        for _, op_row in plan_rows.iterrows():
            op_id = int(op_row["operation_id"])
            every_km = op_row["every_km"]
            every_months = op_row["every_months"]
            hits_km = 0
            if not pd.isna(every_km) and every_km > 0:
                hits_km = int(total_mileage // every_km)
            hits_months = 0
            if not pd.isna(every_months) and every_months > 0:
                hits_months = max(0, int(total_months // every_months))
            hits = max(hits_km, hits_months)
            if hits == 0:
                continue

            if op_id not in ops_meta.index:
                continue
            norm_hours = float(ops_meta.loc[op_id, "default_norm_hours"])

            parts_row = parts[(parts["operation_id"] == op_id) & (parts["brand_segment"] == brand_segment)]
            parts_cost = float(parts_row.iloc[0]["avg_parts_cost_rub"]) if not parts_row.empty else 0.0
            per_hit = parts_cost + norm_hours * labor_rate
            total += int(per_hit * hits)
        return total

    def _calc_tyres(
        self, modification_id: int, segment6: str, horizon: int, mileage_per_year: int,
    ) -> int:
        return calc_tyres_cost(
            modification_id,
            segment6,
            horizon,
            mileage_per_year,
            self.seed["tire_sizes"],
            self.seed["tire_size_prices"],
        )

    def _calc_kasko(self, msrp: int, segment6: str, brand_tier: str,
                    age_year: int, horizon: int) -> int:
        if not (1 <= age_year <= 5):
            age_year = min(max(age_year, 1), 5)
        df = self.seed["kasko_rates"]
        sub = df[
            (df["segment"] == segment6)
            & (df["brand_tier"] == brand_tier)
            & (df["age_year_bucket"] == age_year)
        ]
        if sub.empty:
            return 0
        rate = float(sub.iloc[0]["kasko_rate_pct"]) / 100.0
        return int(msrp * rate * horizon)

    def compute(
        self,
        modification: pd.Series,
        user_profile,
        msrp_override_rub: Optional[int] = None,
        car_model_segment: Optional[str] = None,
    ) -> TCOResult:
        """Compute full TCO for one modification under one UserProfile."""
        from .profile import UserProfile

        assert isinstance(user_profile, UserProfile)

        msrp = int(msrp_override_rub or modification.get("msrp_new_rub") or 0)
        if msrp == 0:
            msrp = 1_500_000  # very rough fallback (should be filled by S4.0 enrich)

        model_id = int(modification["model_id"])
        mrow = self.seed["models"][self.seed["models"]["id"] == model_id]
        if car_model_segment is None:
            seg_raw = mrow.iloc[0]["segment"] if not mrow.empty else "C"
        else:
            seg_raw = car_model_segment
        segment6 = SEGMENT_11_TO_6.get(seg_raw, "C_D")
        model_name = str(mrow.iloc[0]["name"]) if not mrow.empty else ""

        make_id = int(modification["make_id"])
        mk_row = self.seed["makes"][self.seed["makes"]["id"] == make_id]
        if mk_row.empty:
            brand_tier, country, make_name = "mass", "Russia", ""
        else:
            brand_tier = mk_row.iloc[0]["brand_tier"]
            country = mk_row.iloc[0]["country"]
            make_name = str(mk_row.iloc[0]["name"])
        brand_segment = map_brand_segment(brand_tier, country)

        horizon = user_profile.horizon_years
        mileage_per_year = user_profile.mileage_per_year_km
        mileage_total = mileage_per_year * horizon
        tax_year_start = date.today().year
        y_mfg = getattr(user_profile, "year_of_manufacture", None)
        if y_mfg is None:
            age_at_purchase = max(0, int(getattr(user_profile, "age_at_purchase_years", 0)))
            y_mfg = tax_year_start - age_at_purchase
        else:
            y_mfg = int(y_mfg)

        depr = self._calc_depreciation(msrp, segment6, brand_tier, horizon, mileage_total)
        fuel = self._calc_fuel(modification, user_profile.region_id, mileage_per_year, horizon)
        power_hp = float(modification.get("power_hp", 100))
        osago = self._calc_osago(power_hp, user_profile.region_id, horizon)
        tax = self._calc_transport_tax(
            modification, power_hp, user_profile.region_id, horizon,
            y_mfg, make_name, model_name, tax_year_start,
        )
        maint = self._calc_maintenance(
            int(modification["generation_id"]), brand_segment,
            user_profile.region_id, user_profile.sto_type,
            mileage_per_year, horizon,
        )
        tyres = self._calc_tyres(int(modification["id"]), segment6, horizon, mileage_per_year)
        kasko = 0
        if user_profile.include_kasko:
            for age in range(1, horizon + 1):
                kasko += self._calc_kasko(msrp, segment6, brand_tier, age, 1)

        total = depr + fuel + osago + tax + maint + tyres + kasko

        return TCOResult(
            depreciation=depr, fuel=fuel, osago=osago, transport_tax=tax,
            maintenance=maint, tyres=tyres, kasko=kasko,
            total=total,
        )

    def compute_depreciation_pct(
        self,
        modification: pd.Series,
        horizon_years: int = 5,
        mileage_per_year_km: int = 15_000,
        msrp_override_rub: Optional[int] = None,
        car_model_segment: Optional[str] = None,
    ) -> float:
        """Compute depreciation_pct = depreciation / msrp × 100, for ranking."""
        msrp = int(msrp_override_rub or modification.get("msrp_new_rub") or 0)
        if msrp == 0:
            return 50.0  # neutral fallback

        if car_model_segment is None:
            model_id = int(modification["model_id"])
            mrow = self.seed["models"][self.seed["models"]["id"] == model_id]
            seg_raw = mrow.iloc[0]["segment"] if not mrow.empty else "C"
        else:
            seg_raw = car_model_segment
        segment6 = SEGMENT_11_TO_6.get(seg_raw, "C_D")

        make_id = int(modification["make_id"])
        mk_row = self.seed["makes"][self.seed["makes"]["id"] == make_id]
        brand_tier = mk_row.iloc[0]["brand_tier"] if not mk_row.empty else "mass"

        depr = self._calc_depreciation(
            msrp, segment6, brand_tier, horizon_years,
            mileage_per_year_km * horizon_years,
        )
        return depr / msrp * 100.0
