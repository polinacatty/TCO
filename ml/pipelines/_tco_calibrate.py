"""Финальная калибровка полного TCO (sprint 3 step S3.8).

Аналог `_depreciation_calibrate.py`, но для **всего TCO целиком**: для
каждого из 10 эталонных кейсов в `tco_calibration.csv` прогоняет 6
компонент TCO через формулы из этапа 1
(`docs/01_domain_analysis/02_tco_components_ru.md` §2.1–2.8) с
использованием seed-данных спринтов 1–3, суммирует и считает APE против
`observed_total_tco_rub` (сумма из публичных обзоров «5 лет с моделью»).

КАСКО **по умолчанию ВЫКЛ** (как в профиле пользователя), потому что
обзоры Drom типично не включают КАСКО — это согласует базы сравнения.

Считаемые компоненты:

1. **Амортизация** (`depreciation`) — `msrp × Π(1 - rate(seg6, tier, age) /
   100) × (1 - mileage_penalty)` через `depreciation_rates.csv` +
   `mileage_penalties.csv`. ADR-0001 §«Параметры таблицы».

2. **Топливо** (`fuel`) — `consumption × annual_km × fuel_price × horizon`,
   `fuel_price` берётся из `fuel_prices.parquet` (последний доступный
   месяц для региона) или константы по fallback.

3. **ОСАГО** (`osago`) — упрощённая медиана ТБ × типовые коэффициенты
   для физлица в Москве с КБМ=1.0, водитель 30+ со стажем 5+. Точная
   формула ОСАГО валидируется отдельно в шагах 1.2-1.3 спринта 1.

4. **Транспортный налог** (`transport_tax`) — `tax_rate(region, hp) × hp ×
   horizon`, плюс luxury-коэффициент по перечню Минпромторга.

5. **ТО / плановое обслуживание** (`maintenance`) — для каждой операции
   из `service_plan_ops.csv`, попадающей на пробег за горизонт владения,
   считается `parts_cost(op, brand_segment) + norm_hours × labor_rate(
   region, sto_type)`.

6. **Шины** (`tyres`) — `(summer_set + winter_set) × floor(annual_km ×
   horizon / 50000) + change_cost × 2 × horizon` (0 комплектов, если пробег
   < 50 000 км за горизонт).

Светофор по итогу:

| MAPE | Светофор | Действие |
|---|---|---|
| ≤ 25 % | GREEN | exit 0, переход к этапу 4 |
| 25–35 % | YELLOW | exit 1, итерация по самой шумной компоненте |
| > 35 % | RED | exit 2, эскалация / risk-finding |

Run::

    python ml/pipelines/_tco_calibrate.py
"""

from __future__ import annotations

import csv
import math
import sys
from pathlib import Path
from typing import Optional

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
SEED = REPO / "ml" / "data" / "seed"
PROCESSED = REPO / "ml" / "data" / "processed"

from ml.recommendation.tco_calc import calc_tyres_cost  # noqa: E402

CALIBRATION_CSV = SEED / "tco_calibration.csv"

# --- Маппинги ----------------------------------------------------------------

# 11 segments (car_models.segment) -> 6 (depreciation/kasko rates)
# По методологии 06_catalog_methodology.md §7.5 + расширение.
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
    """`(brand_tier, country) -> brand_segment` для parts_costs (7 значений).

    По методологии 08_complex_components_methodology.md §4.3.
    """
    if brand_tier == "russian":
        return "russian"
    if brand_tier == "chinese":
        return "chinese"
    if brand_tier == "premium":
        # Lexus / Genesis имеют country=Japan/South Korea, но запчасти
        # на них в РФ всё равно идут по премиум-логистике; в seed нет
        # отдельного `japanese_premium`, мапим на `japanese` (это даёт
        # оптимистичную оценку запчастей для японского премиума).
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


# Дефолтные коэффициенты ОСАГО для типового кейса
# (физлицо, Москва, водитель 30+, стаж 5+, КБМ=1.0).
# Точная формула — в `osago_*.csv` спринта 1; здесь упрощение
# для калибровки.
OSAGO_TYPICAL_KBM = 1.0     # 5 лет без аварий — middle ground
OSAGO_TYPICAL_KVS = 0.93    # 30+ лет, стаж 5+ (osago_age_exp.csv)
OSAGO_TYPICAL_KO = 1.0      # ограниченный список водителей
OSAGO_TYPICAL_KS = 1.0      # полис на 12 месяцев

# Pricing constants
TIRE_LIFETIME_KM = 50_000           # типичный ресурс комплекта (среднее лето+зима)
TIRE_CHANGE_COST_RUB = 2_500        # одна сезонная переобувка (× 2 = 5 000 ₽/год)
DEFAULT_FUEL_PRICE_RUB_PER_L = {
    "ai92": 55.0,
    "ai95": 60.0,
    "ai98": 70.0,
    "diesel": 65.0,
}
EV_PRICE_RUB_PER_KWH = 6.5     # тариф «дома» 2026; для EV кейсов

# --- Загрузка данных ---------------------------------------------------------


def load_seed():
    """Возвращает все нужные таблицы как dict[str, pd.DataFrame]."""
    data = {}
    data["makes"] = pd.read_csv(SEED / "car_makes.csv")
    data["models"] = pd.read_csv(SEED / "car_models.csv")
    data["generations"] = pd.read_csv(SEED / "car_generations.csv")
    data["modifications"] = pd.read_parquet(PROCESSED / "car_modifications.parquet")
    data["regions"] = pd.read_csv(SEED / "regions.csv")
    data["depreciation"] = pd.read_csv(SEED / "depreciation_rates.csv")
    data["mileage_penalties"] = pd.read_csv(SEED / "mileage_penalties.csv")
    data["fuel_prices"] = pd.read_parquet(PROCESSED / "fuel_prices.parquet")
    data["osago_base"] = pd.read_csv(SEED / "osago_base_tariffs.csv")
    data["osago_power"] = pd.read_csv(SEED / "osago_power.csv")
    data["osago_territory"] = pd.read_csv(SEED / "osago_territory_coefs.csv")
    data["transport_tax"] = pd.read_csv(SEED / "transport_tax_rates.csv")
    data["luxury"] = pd.read_csv(SEED / "luxury_car_list.csv")
    data["service_ops"] = pd.read_csv(SEED / "service_operations.csv")
    data["service_plan_ops"] = pd.read_csv(SEED / "service_plan_ops.csv")
    data["parts_costs"] = pd.read_csv(SEED / "parts_costs.csv")
    data["labor_rates"] = pd.read_csv(SEED / "labor_rates.csv")
    data["tire_sizes"] = pd.read_csv(SEED / "tire_sizes.csv")
    data["tire_size_prices"] = pd.read_csv(SEED / "tire_size_prices.csv")
    return data


# --- Расчёт компонент --------------------------------------------------------


def calc_depreciation(
    msrp: int, segment6: str, brand_tier: str, horizon: int, mileage_total_km: int,
    depr_df: pd.DataFrame, mileage_pen_df: pd.DataFrame,
) -> int:
    """`msrp` минус остаточная стоимость через ADR-0001."""
    rates = depr_df[(depr_df["segment"] == segment6) & (depr_df["brand_tier"] == brand_tier)]
    if rates.empty:
        return msrp // 2
    rates = rates.sort_values("age_year_bucket")

    residual = msrp
    for age in range(1, horizon + 1):
        bucket = min(age, 5)
        rate_pct = rates[rates["age_year_bucket"] == bucket].iloc[0]["annual_depreciation_pct"]
        residual *= (1.0 - rate_pct / 100.0)

    mileage_penalty_pct = 0.0
    for _, row in mileage_pen_df.iterrows():
        if mileage_total_km >= row["mileage_threshold_km"]:
            mileage_penalty_pct = row["extra_depreciation_pct"]
    residual *= (1.0 - mileage_penalty_pct / 100.0)

    depreciation = max(0, msrp - int(residual))
    return depreciation


def get_typical_modification(
    generation_id: int, mods_df: pd.DataFrame
) -> Optional[pd.Series]:
    """Возвращает 'типовую' модификацию для поколения — медианная по hp."""
    rows = mods_df[mods_df["generation_id"] == generation_id]
    if rows.empty:
        return None
    rows_sorted = rows.sort_values("power_hp")
    return rows_sorted.iloc[len(rows_sorted) // 2]


def calc_fuel(
    mod: pd.Series, region_id: int, mileage_per_year: int, horizon: int,
    fuel_prices_df: pd.DataFrame,
) -> int:
    """Стоимость топлива за горизонт."""
    fuel_type = (mod["fuel_type"] or "").upper()
    consumption = mod.get("fuel_consumption_combined_l_100km")
    if consumption is None or pd.isna(consumption):
        consumption = 8.0  # дефолт

    if fuel_type == "ELECTRIC":
        # consumption в kWh/100km — но столбец называется fuel_consumption_combined_l_100km;
        # для EV подставляется кВт-ч/100км в том же поле.
        kwh_per_year = float(consumption) * mileage_per_year / 100.0
        return int(kwh_per_year * EV_PRICE_RUB_PER_KWH * horizon)

    if fuel_type == "HYBRID":
        # типичный гибрид (HEV) расход 5-6 л/100км
        consumption = float(consumption) * 0.85

    fuel_key = {"AI92": "ai92", "AI95": "ai95", "AI98": "ai98", "DIESEL": "diesel"}.get(fuel_type)
    if not fuel_key:
        fuel_key = "ai95"  # fallback

    region_prices = fuel_prices_df[
        (fuel_prices_df["region_id"] == region_id)
        & (fuel_prices_df["fuel_type"] == fuel_key)
    ]
    if not region_prices.empty:
        latest = region_prices.sort_values("price_month").iloc[-1]
        price_per_l = float(latest["price_rub_per_l"])
    else:
        price_per_l = DEFAULT_FUEL_PRICE_RUB_PER_L.get(fuel_key, 60.0)

    liters_per_year = float(consumption) * mileage_per_year / 100.0
    return int(liters_per_year * price_per_l * horizon)


def _osago_kt(region_id: int, osago_territory_df: pd.DataFrame) -> float:
    rows = osago_territory_df[osago_territory_df["region_id"] == region_id]
    if rows.empty:
        raise ValueError(f"no OSAGO KT for region_id={region_id}")
    return float(rows.iloc[0]["kt_general"])


def calc_osago(
    power_hp: float,
    horizon: int,
    region_id: int,
    osago_base_df: pd.DataFrame,
    osago_power_df: pd.DataFrame,
    osago_territory_df: pd.DataFrame,
) -> int:
    """Упрощённая ОСАГО: физлицо, ограниченный список; КТ по региону из osago_territory_coefs."""
    base_row = osago_base_df[osago_base_df["category_id"] == "2.2"]
    if base_row.empty:
        tb = 5000
    else:
        tb = (base_row.iloc[0]["tb_min_rub"] + base_row.iloc[0]["tb_max_rub"]) / 2

    kt = _osago_kt(region_id, osago_territory_df)
    km = 1.0
    sub = osago_power_df[osago_power_df["vehicle_family"] == "B_BE"]
    for _, row in sub.iterrows():
        lo = float(row["power_min_hp_excl"])
        hi = float(row["power_max_hp_incl"])
        if lo < power_hp <= hi:
            km = float(row["km_value"])
            break

    cost_per_year = (
        tb * kt * OSAGO_TYPICAL_KBM * OSAGO_TYPICAL_KVS * OSAGO_TYPICAL_KO * km * OSAGO_TYPICAL_KS
    )
    return int(cost_per_year * horizon)


def calc_transport_tax(
    power_hp: float,
    region_id: int,
    horizon: int,
    year_of_manufacture: int,
    tax_year_start: int,
    modification: pd.Series,
    make_name: str,
    model_name: str,
    transport_tax_df: pd.DataFrame,
    luxury_df: pd.DataFrame,
) -> int:
    """Транспортный налог за горизонт: по годам, ×3 по перечню и окну 10/20 лет с года выпуска."""
    from ml.recommendation.luxury_transport_tax import (
        filter_luxury_candidates,
        luxury_coef_for_tax_year,
    )

    region_rates = transport_tax_df[transport_tax_df["region_id"] == region_id]
    if region_rates.empty:
        region_rates = transport_tax_df[transport_tax_df["region_id"] == 0]

    rate_per_hp = 5.0
    for _, row in region_rates.iterrows():
        hp_min = float(row["hp_min"]) if not pd.isna(row["hp_min"]) else 0
        hp_max = float(row["hp_max"]) if not pd.isna(row["hp_max"]) else 99999
        if hp_min <= power_hp <= hp_max:
            rate_per_hp = float(row["rate_rub_per_hp"])
            break

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
    total = 0
    y_mfg = int(year_of_manufacture)
    for year_idx in range(horizon):
        tax_year = tax_year_start + year_idx
        coef = luxury_coef_for_tax_year(tax_year, y_mfg, candidates)
        total += int(rate_per_hp * power_hp * coef)
    return total


def calc_maintenance(
    generation_id: int, brand_segment: str, region_id: int, sto_type: str,
    mileage_per_year: int, horizon: int,
    plan_ops_df: pd.DataFrame, service_ops_df: pd.DataFrame,
    parts_df: pd.DataFrame, labor_df: pd.DataFrame,
) -> int:
    """Сумма всех плановых ТО, попадающих на пробег за горизонт."""
    plan = plan_ops_df[plan_ops_df["generation_id"] == generation_id]
    if plan.empty:
        return 0

    labor_row = labor_df[
        (labor_df["region_id"] == region_id) & (labor_df["sto_type"] == sto_type)
    ]
    if labor_row.empty:
        labor_row = labor_df[
            (labor_df["region_id"] == 1) & (labor_df["sto_type"] == sto_type)
        ]
    labor_rate = float(labor_row.iloc[0]["rate_rub_per_hour"]) if not labor_row.empty else 1500.0

    total_mileage = mileage_per_year * horizon
    total_months = horizon * 12
    total = 0

    for _, op_row in plan.iterrows():
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

        op_meta = service_ops_df[service_ops_df["id"] == op_id]
        if op_meta.empty:
            continue
        norm_hours = float(op_meta.iloc[0]["default_norm_hours"])

        parts_row = parts_df[
            (parts_df["operation_id"] == op_id) & (parts_df["brand_segment"] == brand_segment)
        ]
        parts_cost = float(parts_row.iloc[0]["avg_parts_cost_rub"]) if not parts_row.empty else 0.0

        per_hit = parts_cost + norm_hours * labor_rate
        total += int(per_hit * hits)

    return total


# --- Главный цикл ------------------------------------------------------------


def calibrate_case(case: dict, data: dict) -> dict:
    """Прогнать все 6 компонент TCO для одного кейса."""
    result = dict(case)

    make_row = data["makes"][data["makes"]["name"] == case["make"]]
    if make_row.empty:
        result["error"] = f"unknown make {case['make']}"
        return result
    brand_tier = make_row.iloc[0]["brand_tier"]
    country = make_row.iloc[0]["country"]

    model_row = data["models"][data["models"]["id"] == int(case["model_id"])]
    if model_row.empty:
        result["error"] = f"unknown model_id {case['model_id']}"
        return result
    seg_raw = model_row.iloc[0]["segment"]
    segment6 = SEGMENT_11_TO_6.get(seg_raw, "C_D")

    brand_segment = map_brand_segment(brand_tier, country)

    mod = get_typical_modification(int(case["generation_id"]), data["modifications"])
    if mod is None:
        result["error"] = f"no modifications for generation_id {case['generation_id']}"
        return result

    horizon = int(case["owner_horizon_years"])
    mileage_per_year = int(case["mileage_per_year_km"])
    region_id = int(case["region_id"])
    msrp = int(case["msrp_new_rub"])
    sto_type = case["sto_type"]

    year_of_manufacture = int(case["year_of_purchase"])
    tax_year_start = 2026
    mileage_total = mileage_per_year * horizon

    pred_depr = calc_depreciation(
        msrp, segment6, brand_tier, horizon, mileage_total,
        data["depreciation"], data["mileage_penalties"],
    )
    pred_fuel = calc_fuel(mod, region_id, mileage_per_year, horizon, data["fuel_prices"])
    pred_osago = calc_osago(
        float(mod["power_hp"]),
        horizon,
        region_id,
        data["osago_base"],
        data["osago_power"],
        data["osago_territory"],
    )
    pred_tax = calc_transport_tax(
        float(mod["power_hp"]), region_id, horizon, year_of_manufacture, tax_year_start,
        mod, str(case["make"]), str(case["model"]),
        data["transport_tax"], data["luxury"],
    )
    pred_maint = calc_maintenance(
        int(case["generation_id"]), brand_segment, region_id, sto_type,
        mileage_per_year, horizon,
        data["service_plan_ops"], data["service_ops"],
        data["parts_costs"], data["labor_rates"],
    )
    pred_tyres = calc_tyres_cost(
        int(mod["id"]), segment6, horizon, mileage_per_year,
        data["tire_sizes"], data["tire_size_prices"],
    )
    pred_kasko = 0  # КАСКО ВЫКЛ по умолчанию

    pred_total = (
        pred_depr + pred_fuel + pred_osago + pred_tax
        + pred_maint + pred_tyres + pred_kasko
    )

    observed = int(case["observed_total_tco_rub"])
    ape = abs(pred_total - observed) / observed * 100.0

    result.update({
        "brand_tier": brand_tier,
        "country": country,
        "segment6": segment6,
        "brand_segment": brand_segment,
        "power_hp": int(mod["power_hp"]),
        "fuel_type": mod["fuel_type"],
        "consumption": float(mod["fuel_consumption_combined_l_100km"] or 0),
        "pred_depreciation": pred_depr,
        "pred_fuel": pred_fuel,
        "pred_osago": pred_osago,
        "pred_transport_tax": pred_tax,
        "pred_maintenance": pred_maint,
        "pred_tyres": pred_tyres,
        "pred_kasko": pred_kasko,
        "pred_total": pred_total,
        "observed_total": observed,
        "ape_pct": ape,
    })
    return result


def main() -> int:
    if not CALIBRATION_CSV.is_file():
        print(f"FAIL: missing {CALIBRATION_CSV}")
        return 2

    with CALIBRATION_CSV.open(encoding="utf-8", newline="") as f:
        cases = list(csv.DictReader(f))

    print(f"Loading seed data...")
    data = load_seed()
    print(f"Loaded {len(data)} tables")
    print()

    results = []
    for case in cases:
        r = calibrate_case(case, data)
        results.append(r)

    # --- Печать таблицы breakdown -------------------------------------------
    print("=" * 130)
    print(f"TCO calibration — {len(results)} cases (6 components)")
    print("Note: observed_total from Drom reviews may still include ad-hoc repairs;")
    print("our methodology does not model unplanned repairs (high stochasticity).")
    print("=" * 130)
    header = (
        f"{'#':>2} {'make/model':<20} {'seg':<8} {'tier':<22} {'depr':>9} {'fuel':>7} "
        f"{'osago':>7} {'tax':>7} {'maint':>8} {'tyre':>7} "
        f"{'PRED':>10} {'OBSRV':>10} {'APE%':>6}"
    )
    print(header)
    print("-" * 130)

    bad: list[str] = []
    apes = []
    for r in results:
        if "error" in r:
            print(f"  case {r['case_id']}: ERROR {r['error']}")
            bad.append(r["case_id"])
            continue
        line = (
            f"{r['case_id']:>2} {r['make'] + '/' + r['model']:<20} "
            f"{r['segment6']:<8} {r['brand_tier']:<22} "
            f"{r['pred_depreciation']:>9,} {r['pred_fuel']:>7,} "
            f"{r['pred_osago']:>7,} {r['pred_transport_tax']:>7,} "
            f"{r['pred_maintenance']:>8,} {r['pred_tyres']:>7,} "
            f"{r['pred_total']:>10,} {r['observed_total']:>10,} {r['ape_pct']:>5.1f}%"
        )
        print(line)
        apes.append(r["ape_pct"])

    if bad:
        print(f"\nFAIL: {len(bad)} cases failed: {bad}")
        return 2

    if not apes:
        print("FAIL: no successful cases")
        return 2

    print("-" * 130)

    mape = sum(apes) / len(apes)
    median_ape = sorted(apes)[len(apes) // 2]
    max_ape = max(apes)
    n_under_25 = sum(1 for a in apes if a <= 25)

    print()
    print(f"MAPE     = {mape:.2f} %")
    print(f"Median   = {median_ape:.2f} %")
    print(f"Max APE  = {max_ape:.2f} %")
    print(f"<= 25 %  = {n_under_25}/{len(apes)}")
    print()

    # --- Summary by segment / brand ----------------------------------------
    print("APE by segment6:")
    for seg in sorted(set(r["segment6"] for r in results if "error" not in r)):
        seg_apes = [r["ape_pct"] for r in results if r.get("segment6") == seg]
        print(f"  {seg:<10} n={len(seg_apes)} MAPE={sum(seg_apes)/len(seg_apes):.2f} %")
    print()

    print("APE by brand_tier:")
    for tier in sorted(set(r["brand_tier"] for r in results if "error" not in r)):
        tier_apes = [r["ape_pct"] for r in results if r.get("brand_tier") == tier]
        print(f"  {tier:<22} n={len(tier_apes)} MAPE={sum(tier_apes)/len(tier_apes):.2f} %")
    print()

    # --- Светофор ----------------------------------------------------------
    if mape <= 25:
        print(f"GREEN: MAPE = {mape:.2f}% (<= 25% target). Sprint 3 calibration PASSED.")
        return 0
    elif mape <= 35:
        print(f"YELLOW: MAPE = {mape:.2f}% (> 25% target). Iterate over noisiest component.")
        return 1
    else:
        print(f"RED: MAPE = {mape:.2f}% (> 35%). Escalate / risk-finding.")
        return 2


if __name__ == "__main__":
    sys.exit(main())
