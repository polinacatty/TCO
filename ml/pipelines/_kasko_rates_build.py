"""Build ``ml/data/seed/kasko_rates.csv`` (sprint 3 step S3.6).

Параметрика КАСКО по компоненте TCO «КАСКО (опциональный)»
(этап 1, документ 02 §2.5):

::

    kasko_year_cost(car) =
          kasko_rate_pct(brand_tier, segment, age) / 100
        × car_market_value(car, age)

КАСКО **по умолчанию выключен** в профиле пользователя
(``user_profiles.include_kasko = false``); включается явным флагом.

Картезианское произведение:

    5 (brand_tier) × 6 (segment) × 5 (age_year_bucket) = 150 строк.

Двухслойная (фактически — трёхслойная) аддитивная параметрика,
аналогичная `_depreciation_rates_build.py` (шаг 2.7):

::

    kasko_rate_pct(tier, segment, age) = clip(
        BASE_BY_TIER[tier]
        + SEGMENT_DELTA[segment]
        + AGE_DELTA[age],
        1.5, 18.0
    )

Округление — до 0.5 % (стандартный шаг тарифной сетки страховщика).

Якорные значения BASE_BY_TIER и AGE_DELTA подобраны так, чтобы попадать
в опорные точки плана §S3.6 (A_B / 1 год: 4.0/5.0/4.5/6.0/7.0;
E_F / 1 год: 5.5/6.5/6.0/7.5/8.5) с погрешностью не более ±0.5 п.п.

Полное обоснование коэффициентов, метаданные (`valid_from`, источники)
— в ``docs/03_data_collection/08_complex_components_methodology.md`` §6.

Идемпотентный: повторный запуск даёт байт-в-байт идентичный CSV.

Run::

    python ml/pipelines/_kasko_rates_build.py
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SEED = REPO / "ml" / "data" / "seed"

OUT_RATES_CSV = SEED / "kasko_rates.csv"

# Brand tiers — те же 5, что в `car_makes.brand_tier`.
# Порядок задаёт инвариант монотонности `russian < jp_kr_mass < mass < chinese < premium`
# (см. §6.5 методологии).
BRAND_TIERS_ORDERED = (
    "russian",
    "japanese_korean_mass",
    "mass",
    "chinese",
    "premium",
)

# Сегменты — те же 6, что в `depreciation_rates.segment`.
SEGMENTS_ORDERED = (
    "A_B",
    "C_D",
    "E_F",
    "J_CROSS",
    "J_SUV",
    "LCV",
)

# Возрастные корзины: 1, 2, 3, 4, 5+.
AGE_BUCKETS = (1, 2, 3, 4, 5)

# Базовая ставка КАСКО (% годовых от рыночной стоимости) для якоря
# (`segment = A_B`, `age = 1 год`) по каждому tier.
# Опорные значения из плана §S3.6 (Sber Insurance / Ингосстрах /
# AlfaStrahovanie / Согласие, медиана 10–15 типовых заявок,
# плюс агрегированные обзоры Drom 2025-2026).
BASE_BY_TIER: dict[str, float] = {
    "russian":              4.0,  # Lada / UAZ — низкая угоняемость, дешёвый ремонт
    "japanese_korean_mass": 4.5,  # Toyota / Hyundai — самый «безопасный» массмаркет
    "mass":                 5.0,  # VW / Renault / Peugeot — европейский массмаркет
    "chinese":              6.0,  # Geely / Chery / Haval — растущая угоняемость + дорогая логистика запчастей
    "premium":              7.0,  # BMW / Mercedes — высокая угоняемость + дорогой ремонт
}

# Сегментная поправка к BASE_BY_TIER (в процентных пунктах).
SEGMENT_DELTA: dict[str, float] = {
    "A_B":     0.0,   # якорь — компактные легковые
    "C_D":     0.5,   # средний класс — больше мощности, выше угоняемость
    "E_F":     1.5,   # бизнес/люкс-седаны — премия за сложность ремонта и угоняемость
    "J_CROSS": 0.5,   # массовые кроссоверы — как C/D
    "J_SUV":   0.5,   # рамные внедорожники — высокая угоняемость, но дешёвый кузовной ремонт
    "LCV":    -0.5,   # коммерческие — пониженная по спец. правилам страхования (не премиум-отделка)
}

# Возрастная поправка (в процентных пунктах).
AGE_DELTA: dict[int, float] = {
    1: 0.0,   # якорь — новый автомобиль
    2: 0.5,
    3: 1.0,
    4: 1.5,
    5: 2.0,   # «5+» — плато после 5 лет, максимум по линейному росту
}


def round_to_half(value: float) -> float:
    """Округление до 0.5 — стандартный шаг тарифной сетки КАСКО."""
    return round(value * 2) / 2.0


def main() -> int:
    rows: list[dict[str, str]] = []
    for tier in BRAND_TIERS_ORDERED:
        for segment in SEGMENTS_ORDERED:
            for age in AGE_BUCKETS:
                base = BASE_BY_TIER[tier]
                seg_delta = SEGMENT_DELTA[segment]
                age_delta = AGE_DELTA[age]
                raw = base + seg_delta + age_delta
                pct = max(1.5, min(18.0, round_to_half(raw)))
                rows.append({
                    "brand_tier": tier,
                    "segment": segment,
                    "age_year_bucket": str(age),
                    "kasko_rate_pct": f"{pct:.1f}",
                })

    rows.sort(key=lambda r: (
        BRAND_TIERS_ORDERED.index(r["brand_tier"]),
        SEGMENTS_ORDERED.index(r["segment"]),
        int(r["age_year_bucket"]),
    ))

    OUT_RATES_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_RATES_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "brand_tier",
                "segment",
                "age_year_bucket",
                "kasko_rate_pct",
            ],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)

    pcts = [float(r["kasko_rate_pct"]) for r in rows]
    print(
        f"OK - wrote {len(rows)} rows -> {OUT_RATES_CSV.relative_to(REPO)} "
        f"({len(BRAND_TIERS_ORDERED)} tiers x {len(SEGMENTS_ORDERED)} segments x {len(AGE_BUCKETS)} ages)"
    )
    print(
        f"     kasko_rate_pct range: [{min(pcts):.1f}..{max(pcts):.1f}], "
        f"median={sorted(pcts)[len(pcts) // 2]:.1f}"
    )
    by_tier_min: dict[str, float] = {}
    by_tier_max: dict[str, float] = {}
    for r in rows:
        t = r["brand_tier"]
        v = float(r["kasko_rate_pct"])
        by_tier_min[t] = min(by_tier_min.get(t, v), v)
        by_tier_max[t] = max(by_tier_max.get(t, v), v)
    for t in BRAND_TIERS_ORDERED:
        print(f"     {t:<22} min={by_tier_min[t]:>4.1f} %   max={by_tier_max[t]:>4.1f} %")
    return 0


if __name__ == "__main__":
    sys.exit(main())
