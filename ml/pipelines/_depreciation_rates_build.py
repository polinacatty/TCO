"""Build ``ml/data/seed/depreciation_rates.csv`` (шаг 2.7).

Параметрика амортизации по [ADR-0001](../../docs/adr/0001-parametric-depreciation.md).

Картезианское произведение:
    6 (segment) x 5 (brand_tier) x 5 (age_year_bucket)  =  150 строк.

Каждое значение получается как
    annual_depreciation_pct = clip(
        BASE_BY_TIER[brand_tier][age]
        + SEGMENT_DELTA[segment][age],
        1, 35
    )

Логика двухслойной модели — см. ``docs/03_data_collection/06_catalog_methodology.md`` §11.

Run:
    python ml/pipelines/_depreciation_rates_build.py
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT_CSV = REPO / "ml" / "data" / "seed" / "depreciation_rates.csv"

# Возрастные корзины (1..5).  В плане §S2.7 это "1, 2, 3, 4, 5+";
# поскольку поле SMALLINT, "5+" хранится как 5 и трактуется как
# "пять лет и более" (плато после 5 года).
AGE_BUCKETS = (1, 2, 3, 4, 5)

# Базовая 5-летняя кривая ежегодной потери стоимости (%) для нейтрального
# C_D / J_CROSS-сегмента.  Источник: усреднённые данные AAA «Your Driving
# Costs» 2024 и KBB 5-Year Cost to Own + российский корректив через
# обзоры Автостат и медианы Auto.ru/Drom (2024-2025).
BASE_BY_TIER: dict[str, list[int]] = {
    "russian":              [16, 10,  8,  7,  6],  # народный сегмент, держится за счёт ремонтопригодности
    "mass":                 [18, 12, 10,  9,  8],  # европейские/американские массовые
    "japanese_korean_mass": [17, 11,  9,  8,  7],  # лучшая массовая остаточная стоимость
    "chinese":              [22, 15, 12, 11, 10],  # быстрая ротация поколений + неуверенность по запчастям
    "premium":              [25, 17, 12, 10,  9],  # резкая первая просадка, плато после 3 года
}

# Сегментные дельты (поправка к базовой кривой, в процентных пунктах).
# Логика выбрана так, чтобы для любой пары (segment, tier) полученная
# 5-летняя кривая оставалась монотонно невозрастающей.
SEGMENT_DELTA: dict[str, list[int]] = {
    "A_B":     [+1, +1,  0,  0,  0],  # эконом: быстрая ротация
    "C_D":     [ 0,  0,  0,  0,  0],  # базовый референс
    "E_F":     [+2, +1, -1, -1,  0],  # бизнес/люкс: «новая машина» теряет много, потом стабильнее
    "J_SUV":   [-2, -1, -1, -1, -1],  # рамные внедорожники держат стоимость
    "J_CROSS": [ 0,  0,  0,  0,  0],  # массовый кроссовер = C_D
    "LCV":     [+3, +2, +1, +1,  0],  # коммерческая нагрузка → агрессивный износ
}

VALID_FROM = "2026-04-28"

# Маленький справочник, чтобы source_note был осмысленным.
TIER_NOTES = {
    "russian":              "AAA YDC + Автостат RU baseline",
    "mass":                 "KBB 5YCTO + Auto.ru EU mass",
    "japanese_korean_mass": "KBB 5YCTO + Auto.ru JP/KR mass",
    "chinese":              "Drom CN-EV review 2024-2025",
    "premium":              "AAA YDC + KBB premium",
}
SEGMENT_NOTES = {
    "A_B":     "A/B economy correction",
    "C_D":     "C/D baseline (no correction)",
    "E_F":     "E/F executive/luxury correction",
    "J_SUV":   "J_SUV body-on-frame retention",
    "J_CROSS": "J_CROSS unibody (= C_D)",
    "LCV":     "LCV commercial wear correction",
}


def main() -> int:
    rows: list[dict[str, str]] = []
    for segment in SEGMENT_DELTA:
        for tier in BASE_BY_TIER:
            for i, age in enumerate(AGE_BUCKETS):
                base = BASE_BY_TIER[tier][i]
                delta = SEGMENT_DELTA[segment][i]
                value = max(1, min(35, base + delta))
                source = f"{TIER_NOTES[tier]}; {SEGMENT_NOTES[segment]}"
                rows.append({
                    "segment": segment,
                    "brand_tier": tier,
                    "age_year_bucket": str(age),
                    "annual_depreciation_pct": f"{value:.2f}",
                    "source_note": source,
                    "valid_from": VALID_FROM,
                })

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "segment", "brand_tier", "age_year_bucket",
                "annual_depreciation_pct", "source_note", "valid_from",
            ],
            lineterminator="\n",
        )
        w.writeheader()
        w.writerows(rows)

    print(
        f"OK - wrote {len(rows)} rows -> {OUT_CSV.relative_to(REPO)} "
        f"({len(SEGMENT_DELTA)} segments x {len(BASE_BY_TIER)} tiers x {len(AGE_BUCKETS)} ages)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
