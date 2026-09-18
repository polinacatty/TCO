"""Build ``ml/data/seed/labor_rates.csv`` (sprint 3 step S3.5).

Параметрика стоимости нормо-часа по компоненте TCO «плановое ТО»
(этап 1, документ 02 §2.6):

::

    work_cost = norm_hours × labour_rate(region, sto_type)

Картезианское произведение:

    85 (regions) × 3 (sto_types) = 255 строк.

Двухслойная модель (аналогично `_depreciation_rates_build.py`):

::

    rate_rub_per_hour(region, sto_type) =
        round( BASE_RATE_BY_STO_TYPE[sto_type] × REGION_COEF[region], -1 )

где::

    REGION_COEF[region] = clip(
        DISTRICT_COEF[federal_district]
        + POPULATION_DELTA[population_thousands]
        + REGIONAL_PIN_OVERRIDE[region_id],   # для 19 опорных регионов
        0.65, 1.40    # план §S3.5 фиксирует диапазон 0.6..1.4
    )

Опорные значения REGIONAL_PIN_OVERRIDE взяты из публичных прайсов
федеральных сетей (FixAuto, EuroAuto, Toyota, BMW Dealers) на 2026-Q1.
Для остальных 70 регионов — экстраполяция по федеральному округу +
поправке на население.

Полное обоснование коэффициентов и опорных точек — в
``docs/03_data_collection/08_complex_components_methodology.md`` §5.

Идемпотентный: повторный запуск даёт байт-в-байт идентичный CSV
(детерминированная сортировка по ``(region_id, sto_type_order)``).

Run::

    python ml/pipelines/_labor_rates_build.py
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SEED = REPO / "ml" / "data" / "seed"

REGIONS_CSV = SEED / "regions.csv"
OUT_CSV = SEED / "labor_rates.csv"

# Тип СТО в порядке возрастания тарифа.
# Этот же порядок задаёт инвариант `private < independent < dealer`
# в валидаторе.
STO_TYPES_ORDERED = ("private", "independent", "dealer")

# Базовая ставка ₽/час для усреднённого региона (REGION_COEF = 1.0).
# Источник: медиана прайсов федеральных сетей в Нижнем Новгороде /
# Воронеже / Перми (типичные «средние» города РФ) на 2026-Q1.
BASE_RATE_BY_STO_TYPE: dict[str, int] = {
    "private":     800,   # гараж / самозанятый — нал, без чека
    "independent": 1500,  # мультибрендовый сервис: FixAuto, EuroAuto, RusAuto
    "dealer":      3500,  # официальный дилер
}

# Коэффициент по федеральному округу.
# Источник: средневзвешенные значения прайсов СТО в столицах округов.
DISTRICT_COEF: dict[str, float] = {
    "Центральный":       1.05,  # Москва-effect
    "Северо-Западный":   1.05,  # СПб + Калининград (импортная логистика)
    "Южный":             0.95,
    "Северо-Кавказский": 0.85,  # низкая плотность сертифицированных СТО
    "Приволжский":       0.95,
    "Уральский":         1.00,
    "Сибирский":         0.95,
    "Дальневосточный":   1.20,  # удалённость, импорт запчастей через Владивосток
}


def population_delta(pop_thousands: int) -> float:
    """Поправка на плотность сервисного рынка по населению субъекта."""
    if pop_thousands > 5000:
        return 0.10   # мегаполис: высокая конкуренция, но и зарплаты мастеров выше
    if pop_thousands > 2000:
        return 0.05
    if pop_thousands > 500:
        return 0.0
    if pop_thousands > 100:
        return -0.05  # малая область: меньше СТО, дешевле труд
    return -0.10      # очень малые субъекты (Ненецкий АО, Чукотка)


# Опорные точки REGIONAL_PIN_OVERRIDE — поправка к расчётному коэффициенту,
# применяется поверх district + population по 19 регионам, для которых у
# нас есть «якорные» прайсы федеральных сетей или статистика обзоров.
#
# Целевые значения для 7 регионов из плана §S3.5 — Москва 1.40, СПб 1.30,
# Екатеринбург 1.10, Казань 1.05, Волгоград 0.95, Ставрополь 0.85,
# Якутск 1.20 — задают каркас. Остальные пины уточняют северные / ДВ
# регионы (вахтовые ставки и импортная логистика через Владивосток).
REGIONAL_PIN_OVERRIDE: dict[int, float] = {
    # Plan-anchor regions (точное попадание в опорные точки §S3.5)
    1:  +0.25,  # Москва — целевой 1.40 = 1.05 (Центр) + 0.10 (pop>5M) + 0.25
    19: +0.15,  # Санкт-Петербург — целевой 1.30 = 1.05 + 0.10 + 0.15
    60: +0.05,  # Свердловская обл. (Екатеринбург) — целевой 1.10 = 1.00 + 0.05 + 0.05
    48: +0.05,  # Татарстан (Казань) — целевой 1.05 = 0.95 + 0.05 + 0.05
    35: -0.05,  # Волгоградская обл. — целевой 0.95 = 0.95 + 0.05 - 0.05
    44: -0.05,  # Ставропольский край — целевой 0.85 = 0.85 + 0.05 - 0.05
    76:  0.0,   # Республика Саха (Якутия) — целевой 1.20 = 1.20 + 0 + 0
    # Прочие пины: Север / ДВ / нефтяные регионы с высокими тарифами СТО
    61: +0.10,  # Тюменская область (нефть → высокие ставки)
    62: +0.20,  # ХМАО-Югра (Сургут / Нижневартовск)
    64: +0.20,  # ЯНАО (вахтовые ставки)
    78: +0.10,  # Камчатский край (импорт через ДВ)
    82: +0.20,  # Магаданская область (логистика по золоту)
    83: +0.10,  # Сахалинская область (нефть)
    85: +0.20,  # Чукотский АО (минимальная конкуренция)
    27: +0.10,  # Ненецкий АО (нефть-газ премия)
    33: +0.05,  # Краснодарский край (Сочи / Краснодар — высокие тарифы)
    63: 0.0,    # Челябинская область — на дефолте Урала без поправки
    # Низкоопорные регионы Кавказа — используют базовый district 0.85
    39: -0.05,  # Республика Ингушетия
    41: -0.05,  # Карачаево-Черкесская Республика
    40: -0.05,  # Кабардино-Балкарская Республика
    73: -0.05,  # Республика Тыва (низкий АП-рынок)
}


def round_to_50(value: float) -> int:
    """Округление до 50 ₽ — стандартный шаг тарифной сетки СТО."""
    return int(round(value / 50.0)) * 50


def main() -> int:
    if not REGIONS_CSV.is_file():
        print("FAIL: missing", REGIONS_CSV, file=sys.stderr)
        return 1

    regions: list[dict[str, str]] = []
    with REGIONS_CSV.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            regions.append(row)

    rows: list[dict[str, str]] = []

    coef_by_region: dict[int, float] = {}
    for r in regions:
        rid = int(r["id"])
        district = r["federal_district"]
        pop = int(r["population_thousands"])
        coef = DISTRICT_COEF[district] + population_delta(pop) + REGIONAL_PIN_OVERRIDE.get(rid, 0.0)
        coef = max(0.65, min(1.40, coef))
        coef_by_region[rid] = round(coef, 3)

    for r in regions:
        rid = int(r["id"])
        coef = coef_by_region[rid]
        for sto_type in STO_TYPES_ORDERED:
            base = BASE_RATE_BY_STO_TYPE[sto_type]
            rate = max(300, round_to_50(base * coef))
            rows.append({
                "region_id": str(rid),
                "region_name": r["name"],
                "sto_type": sto_type,
                "rate_rub_per_hour": str(rate),
            })

    rows.sort(key=lambda x: (
        int(x["region_id"]),
        STO_TYPES_ORDERED.index(x["sto_type"]),
    ))

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "region_id",
                "region_name",
                "sto_type",
                "rate_rub_per_hour",
            ],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)

    rates = [int(r["rate_rub_per_hour"]) for r in rows]
    print(
        f"OK - wrote {len(rows)} rows -> {OUT_CSV.relative_to(REPO)} "
        f"({len(regions)} regions x {len(STO_TYPES_ORDERED)} sto_types)"
    )
    print(
        f"     rate range RUB/h: [{min(rates):,}..{max(rates):,}], "
        f"median={sorted(rates)[len(rates) // 2]:,}"
    )
    by_sto_min: dict[str, int] = {}
    by_sto_max: dict[str, int] = {}
    for r in rows:
        s = r["sto_type"]
        v = int(r["rate_rub_per_hour"])
        by_sto_min[s] = min(by_sto_min.get(s, v), v)
        by_sto_max[s] = max(by_sto_max.get(s, v), v)
    for s in STO_TYPES_ORDERED:
        print(f"     {s:<13} min={by_sto_min[s]:>5,} RUB/h   max={by_sto_max[s]:>5,} RUB/h")

    coefs = sorted(coef_by_region.values())
    print(
        f"     REGION_COEF distribution: min={coefs[0]:.2f}, "
        f"median={coefs[len(coefs) // 2]:.2f}, max={coefs[-1]:.2f}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
