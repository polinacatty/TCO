"""Build ``ml/data/seed/tire_size_prices.csv`` (шаг 2.6).

Для каждого уникального ``size_code`` из ``tire_sizes.csv`` пишем 2 строки
(``summer`` + ``winter``) с оценкой средней цены комплекта 4 шин (₽).

Strategy (parametric, см. ``docs/03_data_collection/05_sprint2_plan.md`` §S2.6):

1. **Anchor-таблица «диаметр → базовая цена»** (комплект на ширине 215 мм)
   — медианы среднего ценового яруса (Pirelli / Continental / Bridgestone /
   Nokian Tyres / Hankook) по агрегатам Колесо.ру, Я.Маркет, Шинторг
   на 2025-2026 годы.

2. **Linear width factor** — реальный разброс цен внутри одного диаметра
   определяется шириной (например, 205/55 R17 vs 245/45 R17 различаются
   ≈ +6 % по медиане). Базовая ширина — 215 мм; на каждые 10 мм добавляем
   ≈ 1.5 %.

3. **Winter factor 1.15** — типичная премия зимних (нешипованных,
   «липучка») над летом по медиане 2025 г. Шипованные дороже на 5-10 %,
   но в MVP считаем «среднее зимнее».

Run:
    python ml/pipelines/_tire_size_prices_build.py
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TIRES_CSV = REPO / "ml" / "data" / "seed" / "tire_sizes.csv"
OUT_CSV = REPO / "ml" / "data" / "seed" / "tire_size_prices.csv"

SIZE_RE = re.compile(r"^(\d{3})/(\d{2})\sR(\d{2})$")

RIM_BASE_SUMMER_RUB: dict[int, int] = {
    14:  12_000,
    15:  16_000,
    16:  22_000,
    17:  32_000,
    18:  44_000,
    19:  58_000,
    20:  78_000,
    21: 100_000,
    22: 130_000,
    23: 165_000,
    24: 200_000,
}

WIDTH_BASELINE_MM = 215
WIDTH_FACTOR_PER_MM = 0.0015
WINTER_FACTOR = 1.15

def estimate_summer(width: int, rim: int) -> int:
    base = RIM_BASE_SUMMER_RUB.get(rim)
    if base is None:
        raise ValueError(f"no anchor for R{rim}")
    width_factor = 1.0 + (width - WIDTH_BASELINE_MM) * WIDTH_FACTOR_PER_MM
    width_factor = max(0.85, min(width_factor, 1.30))  # clip extremes
    return int(round(base * width_factor / 100.0) * 100)


def estimate_winter(price_summer: int) -> int:
    return int(round(price_summer * WINTER_FACTOR / 100.0) * 100)


def main() -> int:
    if not TIRES_CSV.is_file():
        print("FAIL: missing", TIRES_CSV, file=sys.stderr)
        return 1

    sizes: set[str] = set()
    with TIRES_CSV.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            sizes.add(row["size_code"])

    rows: list[dict[str, str]] = []
    for size in sorted(sizes):
        m = SIZE_RE.match(size)
        if not m:
            print(f"FAIL: bad size_code {size!r} in tire_sizes.csv", file=sys.stderr)
            return 1
        width, _aspect, rim = int(m.group(1)), int(m.group(2)), int(m.group(3))
        ps = estimate_summer(width, rim)
        pw = estimate_winter(ps)
        rows.append({
            "size_code": size,
            "season": "summer",
            "avg_set_price_rub": str(ps),
        })
        rows.append({
            "size_code": size,
            "season": "winter",
            "avg_set_price_rub": str(pw),
        })

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["size_code", "season", "avg_set_price_rub"],
            lineterminator="\n",
        )
        w.writeheader()
        w.writerows(rows)

    summer_prices = [int(r["avg_set_price_rub"]) for r in rows if r["season"] == "summer"]
    winter_prices = [int(r["avg_set_price_rub"]) for r in rows if r["season"] == "winter"]
    print(
        f"OK — wrote {len(rows)} rows -> {OUT_CSV.relative_to(REPO)} "
        f"({len(sizes)} sizes x 2 seasons; "
        f"summer RUB[{min(summer_prices):,}..{max(summer_prices):,}], "
        f"winter RUB[{min(winter_prices):,}..{max(winter_prices):,}])"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
