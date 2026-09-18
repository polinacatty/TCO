"""Build ``ml/data/seed/parts_costs.csv`` (sprint 3 step S3.4).

Параметрика средней стоимости запчастей по компоненте TCO «плановое ТО»
(этап 1, документ 02 §2.6). Двухслойная модель, аналогичная
`_depreciation_rates_build.py` (шаг 2.7) и `_tire_size_prices_build.py`
(шаг 2.6):

::

    avg_parts_cost_rub(op, brand_segment) =
        round( BASE_BY_OP[op] × TIER_MULTIPLIER[brand_segment] / 10 ) × 10

Картезианское произведение:

    32 (operations) × 7 (brand_segments) = 224 строки.

Brand segments (схема БД ``parts_costs.brand_segment``, 7 значений) — это
расщепление 5-уровневого `car_makes.brand_tier` по `car_makes.country`:

    russian → russian
    chinese → chinese
    japanese_korean_mass × Japan → japanese
    japanese_korean_mass × South Korea → korean
    mass × {Germany, France, Italy, ...} → european_mass
    mass × {USA} → american
    premium × {Germany, UK, Italy, Sweden, ...} → european_premium
    premium × {USA} → american
    premium × {Japan, South Korea} → japanese  (Lexus, Acura, Infiniti, Genesis)
                                                — премиум-надбавка съедается тарифом
                                                нормо-часа дилера (см. labor_rates).

Полный маппинг + обоснование коэффициентов и BASE_BY_OP — в
``docs/03_data_collection/08_complex_components_methodology.md`` §4.

Идемпотентный: повторный запуск даёт байт-в-байт идентичный CSV
(детерминированная сортировка по ``(operation_id, brand_segment_order)``).

Run::

    python ml/pipelines/_parts_costs_build.py
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SEED = REPO / "ml" / "data" / "seed"

SERVICE_OPS_CSV = SEED / "service_operations.csv"
OUT_CSV = SEED / "parts_costs.csv"

# Brand segments в порядке возрастания типичной стоимости запчастей.
# Этот же порядок задаёт инвариант монотонности в валидаторе.
BRAND_SEGMENTS_ORDERED = (
    "russian",
    "chinese",
    "korean",
    "japanese",
    "european_mass",
    "american",
    "european_premium",
)

# Множители относительно "japanese" якоря (= 1.00).
# Логика: японские запчасти исторически — наиболее распространённый
# справочник aftermarket на российском рынке (Toyota / Nissan / Mazda
# везде представлены), отсюда удобно ставить anchor сюда.
TIER_MULTIPLIER: dict[str, float] = {
    "russian":          0.55,  # ВАЗ / УАЗ — отечественные запчасти доступны и дёшевы
    "chinese":          0.70,  # китайские — массовое производство, низкая цена aftermarket
    "korean":           0.90,  # Hyundai/Kia OEM/aftermarket чуть дешевле японского
    "japanese":         1.00,  # ANCHOR (Toyota / Honda / Nissan / Mazda)
    "european_mass":    1.15,  # VAG / Renault / Peugeot — премия за европейский импорт
    "american":         1.40,  # Ford / Chevrolet / Jeep / Cadillac — длинная логистика, малый объём
    "european_premium": 1.90,  # BMW / Mercedes / Audi / Porsche — OEM-only часть номенклатуры
}

# Базовые цены запчастей в ₽ для тиаrа `japanese` на 2026-Q1.
# Цифры — медиана по Emex / Exist / Autodoc для типового представителя
# каждой операции (например, для `oil_change_engine` — 4-5 л синтетики
# Toyota OEM либо аналогов Mobil/Eneos/Lukoil; для `brake_pads_front` —
# комплект 4 колодки бренда уровня Akebono / TRW для C/D-сегмента).
# Полный построчный расчёт с цитированием — в §4.4 методологии.
BASE_BY_OP: dict[str, int] = {
    # fluids (8)
    "oil_change_engine":            3500,  # 4-5 л синтетики OEM-grade + промывка
    "oil_change_atf":               6000,  # 8 л ATF Type IV / ZF Lifeguard 6
    "oil_change_mt":                1800,  # 2 л трансмиссионки
    "coolant_change":               2500,  # 5 л G12++/SLLC
    "brake_fluid_change":            800,  # 1 л DOT-4
    "power_steering_fluid_change":  1000,  # 1 л PSF
    "rear_diff_oil_change":         2000,  # 1.5 л LSD-grade
    "washer_fluid_refill":           500,  # 5 л зимней омывайки
    # filters (4)
    "oil_filter":                    800,  # фильтрующий элемент уровня MANN/Kolbenschmidt
    "air_filter":                   1000,
    "cabin_filter":                 1500,  # угольный
    "fuel_filter":                  2200,  # бензиновый или дизельный сменный картридж
    # brakes (5)
    "brake_pads_front":             4000,  # комплект 4 колодки aftermarket-mid
    "brake_pads_rear":              3500,
    "brake_discs_front":            8000,  # пара дисков ATE / Brembo aftermarket
    "brake_discs_rear":             7000,
    "brake_hoses":                  3000,  # 4 шланга армированных
    # belts (3)
    "timing_belt_kit":             15000,  # ремень + ролики + помпа Gates / SKF
    "accessory_belt":               2000,  # ремень навесных + натяжитель
    "timing_chain_inspection":       500,  # расходники при диагностике (прокладки клапанной крышки)
    # electrics (4)
    "spark_plugs":                  3500,  # 4 свечи иридий/платина уровня NGK Iridium IX
    "glow_plugs":                   5000,  # 4 свечи накала Bosch / Beru (дизель)
    "battery_replacement":         10000,  # AGM 70-80 А·ч уровня Varta Blue Dynamic
    "headlight_bulbs":              2200,  # 2 лампы H7/H4 Osram Night Breaker / Philips
    # body (3)
    "wiper_blades_front":           2000,  # пара щёток Bosch Aerotwin
    "wiper_blades_rear":            1000,  # одна щётка задняя
    "anticorrosion_treatment":      4000,  # материалы Tectyl / Dinitrol на одну обработку
    # other (5)
    "diagnostics_full":              200,  # расходные детали при диагностике
    "wheel_alignment":               200,  # расходники (грузики при необходимости)
    "wheel_balancing":               300,  # 4 балансировочных грузика
    "tyre_swap_seasonal":            200,  # клапаны TR-414 + смазка
    "ac_service":                   2000,  # фреон R134a / R1234yf + UV-краситель
}


def load_service_operations() -> list[dict[str, str]]:
    """Загружает все 32 строки service_operations.csv (id, code)."""
    if not SERVICE_OPS_CSV.is_file():
        raise FileNotFoundError(f"missing {SERVICE_OPS_CSV}")
    with SERVICE_OPS_CSV.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def round_to_10(price_float: float) -> int:
    """Округление до 10 ₽ — сохраняет монотонность по тиру и читаемость."""
    return int(round(price_float / 10.0)) * 10


def main() -> int:
    ops = load_service_operations()

    missing_in_base = [o["code"] for o in ops if o["code"] not in BASE_BY_OP]
    if missing_in_base:
        print(
            f"FAIL: BASE_BY_OP не покрывает операции: {missing_in_base}",
            file=sys.stderr,
        )
        return 1

    extra_in_base = sorted(set(BASE_BY_OP) - {o["code"] for o in ops})
    if extra_in_base:
        print(
            f"FAIL: BASE_BY_OP содержит лишние коды (нет в service_operations.csv): {extra_in_base}",
            file=sys.stderr,
        )
        return 1

    rows: list[dict[str, str]] = []
    for op in ops:
        op_id = int(op["id"])
        code = op["code"]
        base = BASE_BY_OP[code]
        for seg in BRAND_SEGMENTS_ORDERED:
            mult = TIER_MULTIPLIER[seg]
            price = max(50, round_to_10(base * mult))
            rows.append({
                "operation_id": str(op_id),
                "operation_code": code,
                "brand_segment": seg,
                "avg_parts_cost_rub": str(price),
            })

    rows.sort(key=lambda r: (
        int(r["operation_id"]),
        BRAND_SEGMENTS_ORDERED.index(r["brand_segment"]),
    ))

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "operation_id",
                "operation_code",
                "brand_segment",
                "avg_parts_cost_rub",
            ],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)

    prices = [int(r["avg_parts_cost_rub"]) for r in rows]
    print(
        f"OK - wrote {len(rows)} rows -> {OUT_CSV.relative_to(REPO)} "
        f"({len(ops)} operations x {len(BRAND_SEGMENTS_ORDERED)} brand_segments)"
    )
    print(
        f"     price range RUB: [{min(prices):,}..{max(prices):,}], "
        f"median={sorted(prices)[len(prices) // 2]:,}"
    )
    by_seg_min: dict[str, int] = {}
    by_seg_max: dict[str, int] = {}
    for r in rows:
        seg = r["brand_segment"]
        p = int(r["avg_parts_cost_rub"])
        by_seg_min[seg] = min(by_seg_min.get(seg, p), p)
        by_seg_max[seg] = max(by_seg_max.get(seg, p), p)
    for seg in BRAND_SEGMENTS_ORDERED:
        print(
            f"     {seg:<18} min={by_seg_min[seg]:>6,} RUB   max={by_seg_max[seg]:>6,} RUB"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
