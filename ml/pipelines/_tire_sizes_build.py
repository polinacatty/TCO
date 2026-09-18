"""Build ``ml/data/seed/tire_sizes.csv`` (шаг 2.5).

Для каждой модификации в ``car_modifications.parquet`` подбираем штатный
размер шин (size_code в формате ``225/55 R17``).

Strategy (hybrid, см. ``docs/03_data_collection/05_sprint2_plan.md`` §S2.5):

1. **Per-segment power-tier defaults.** Для каждого ``segment`` (по
   ``car_models.csv`` через `generation → model`) описана таблица из 3
   размеров шин: «base / mid / high» — выбор зависит от ``power_hp``
   модификации относительно порога сегмента. Покрывает большинство
   обычных машин одной строкой ``axle = both``.

2. **Make/model overrides — staggered fitments.** Для спорткаров и
   премиум-моделей с разными размерами спереди/сзади (Porsche 911,
   BMW M3/M5, Ferrari, Lamborghini, AMG GT и т. п.) — явный override
   с двумя строками: ``axle = front`` + ``axle = rear``.

Outputs ``modification_id, axle, size_code, is_default``.

Run:
    python ml/pipelines/_tire_sizes_build.py
"""

from __future__ import annotations

import csv
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
MAKES_CSV = REPO / "ml" / "data" / "seed" / "car_makes.csv"
MODELS_CSV = REPO / "ml" / "data" / "seed" / "car_models.csv"
GENS_CSV = REPO / "ml" / "data" / "seed" / "car_generations.csv"
MODS_PARQ = REPO / "ml" / "data" / "processed" / "car_modifications.parquet"
OUT_CSV = REPO / "ml" / "data" / "seed" / "tire_sizes.csv"


@dataclass(frozen=True)
class SegRule:
    """Power-band sizing rule per segment.

    ``low``/``mid``/``high`` are size_code strings (``WWW/AA RDD``).
    ``threshold_low``/``threshold_high`` split power_hp into 3 tiers.
    """
    low: str
    mid: str
    high: str
    threshold_low: int   # < this -> low
    threshold_high: int  # >= this -> high


# Source: справочники Michelin / Continental по моделям, типичные размеры
# на новые автомобили 2018-2025 для российского рынка (Drom-карточки).
SEGMENT_RULES: dict[str, SegRule] = {
    "A":       SegRule("175/65 R14", "185/60 R15", "195/55 R16",  70,  100),
    "B":       SegRule("185/65 R15", "195/55 R16", "205/50 R17",  95,  130),
    "C":       SegRule("195/65 R15", "205/55 R16", "225/45 R17", 110,  170),
    "D":       SegRule("215/55 R17", "225/50 R17", "245/45 R18", 150,  220),
    "E":       SegRule("225/55 R17", "245/45 R18", "275/35 R20", 200,  300),
    "F":       SegRule("245/50 R18", "275/40 R20", "275/35 R21", 280,  450),
    "J_CROSS": SegRule("215/65 R16", "225/60 R17", "235/55 R19", 130,  200),
    "J_SUV":   SegRule("245/70 R16", "265/60 R18", "285/55 R20", 150,  280),
    "M_MPV":   SegRule("215/65 R16", "235/55 R18", "255/50 R19", 140,  230),
    "S_SPORT": SegRule("245/40 R18", "245/35 R19", "275/30 R20", 350,  550),
    "LCV":     SegRule("235/65 R17", "245/65 R17", "265/65 R18", 150,  220),
    "OTHER":   SegRule("195/65 R15", "205/55 R16", "215/50 R17", 100,  170),
}


# (make_normalized, model_normalized) -> staggered fitment per modification.
# Если модификация попала в этот override, используется ``front_size`` +
# ``rear_size`` вместо одного ``both``-размера.  Только для машин с
# официально asymmetric tire fitments.  Источник — спецификации
# производителей (на примере годов выпуска 2018-2024).
@dataclass(frozen=True)
class Staggered:
    front: str
    rear: str
    min_power_hp: int = 0  # only apply if mod.power_hp >= this


STAGGERED_OVERRIDES: dict[tuple[str, str], Staggered] = {
    # Porsche staggered family.
    ("porsche", "911"):           Staggered("245/35 R20", "305/30 R20"),
    ("porsche", "panamera"):      Staggered("275/40 R20", "315/35 R20", min_power_hp=440),
    ("porsche", "cayenne"):       Staggered("285/40 R21", "315/35 R21", min_power_hp=460),
    ("porsche", "718cayman"):     Staggered("235/35 R20", "265/35 R20"),
    ("porsche", "718boxster"):    Staggered("235/35 R20", "265/35 R20"),
    ("porsche", "taycan"):        Staggered("245/45 R20", "285/40 R20"),

    # BMW M-cars.
    ("bmw", "m3"):                Staggered("275/35 R19", "285/30 R20"),
    ("bmw", "m5"):                Staggered("275/35 R20", "285/35 R20"),
    ("bmw", "z4"):                Staggered("225/45 R18", "255/40 R18"),

    # Mercedes-AMG.
    ("mercedesbenz", "amggt"):    Staggered("265/35 R19", "295/35 R19"),

    # Audi RS.
    ("audi", "rs6"):              Staggered("285/30 R22", "285/30 R22"),

    # Italian super sport.
    ("ferrari", "296gtb"):        Staggered("245/35 R20", "305/35 R20"),
    ("ferrari", "f8tributo"):     Staggered("245/35 R20", "305/30 R20"),
    ("ferrari", "roma"):          Staggered("245/35 R20", "285/35 R20"),
    ("ferrari", "sf90"):          Staggered("255/35 R20", "315/30 R20"),
    ("ferrari", "purosangue"):    Staggered("255/40 R22", "315/35 R23"),
    ("ferrari", "812superfast"):  Staggered("275/35 R20", "315/35 R20"),
    ("ferrari", "portofino"):     Staggered("245/35 R20", "285/35 R20"),
    ("lamborghini", "huracan"):   Staggered("245/30 R20", "305/30 R20"),
    ("lamborghini", "aventador"): Staggered("255/30 R20", "355/25 R21"),
    ("lamborghini", "urus"):      Staggered("285/40 R22", "325/35 R22"),
    ("lamborghini", "revuelto"):  Staggered("265/35 R20", "345/30 R21"),
    ("maserati", "mc20"):         Staggered("245/35 R20", "305/30 R20"),
    ("mclaren", "720s"):          Staggered("245/35 R19", "305/30 R20"),
    ("mclaren", "gt"):            Staggered("225/35 R20", "295/30 R21"),
    ("mclaren", "artura"):        Staggered("235/35 R19", "295/35 R20"),
    ("bugatti", "chiron"):        Staggered("285/30 R20", "355/25 R21"),

    # British super sport.
    ("astonmartin", "db11"):      Staggered("255/40 R20", "295/35 R20"),
    ("astonmartin", "vantage"):   Staggered("255/40 R20", "295/35 R20"),
    ("astonmartin", "dbs"):       Staggered("265/35 R21", "305/30 R21"),
    ("astonmartin", "rapide"):    Staggered("245/40 R20", "295/35 R20"),
    ("jaguar", "ftype"):          Staggered("255/35 R20", "295/30 R20"),
    ("lotus", "emira"):           Staggered("245/35 R20", "295/30 R20"),

    # JDM / KDM sport.
    ("nissan", "gtr"):            Staggered("255/40 R20", "285/35 R20"),
    ("subaru", "wrx"):            Staggered("245/40 R18", "245/40 R18"),

    # Bentley / Rolls-Royce.
    ("bentley", "continentalgt"): Staggered("275/40 R21", "315/35 R21"),
    ("rollsroyce", "wraith"):     Staggered("255/45 R21", "285/40 R21"),
    ("rollsroyce", "spectre"):    Staggered("255/40 R23", "295/35 R23"),

    # Aurus.
    ("aurus", "senat"):           Staggered("255/45 R20", "285/40 R20"),
    ("aurus", "komendant"):       Staggered("265/50 R21", "295/45 R21"),
}


def _pick_default_size(segment: str, power_hp: int) -> str:
    rule = SEGMENT_RULES.get(segment, SEGMENT_RULES["OTHER"])
    if power_hp < rule.threshold_low:
        return rule.low
    if power_hp >= rule.threshold_high:
        return rule.high
    return rule.mid


def main() -> int:
    if not all(p.is_file() for p in (MAKES_CSV, MODELS_CSV, GENS_CSV, MODS_PARQ)):
        print("FAIL: missing one of inputs", file=sys.stderr)
        return 1

    norm_by_make_id: dict[int, str] = {}
    with MAKES_CSV.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            norm_by_make_id[int(row["id"])] = row["name_normalized"]

    models_by_id: dict[int, dict[str, str]] = {}
    with MODELS_CSV.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            models_by_id[int(row["id"])] = row

    gen_to_model: dict[int, int] = {}
    with GENS_CSV.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            gen_to_model[int(row["id"])] = int(row["model_id"])

    mods = pd.read_parquet(MODS_PARQ)

    rows: list[dict[str, str | int]] = []
    staggered_used = 0
    default_used = 0

    for _, m in mods.iterrows():
        gid = int(m["generation_id"])
        mid = int(m["id"])
        power_hp = int(m["power_hp"])
        model = models_by_id[gen_to_model[gid]]
        segment = model["segment"]
        make_norm = norm_by_make_id[int(model["make_id"])]
        model_norm = model["name_normalized"]

        key = (make_norm, model_norm)
        st = STAGGERED_OVERRIDES.get(key)
        if st is not None and power_hp >= st.min_power_hp:
            rows.append({
                "modification_id": mid,
                "axle": "front",
                "size_code": st.front,
                "is_default": "true",
            })
            rows.append({
                "modification_id": mid,
                "axle": "rear",
                "size_code": st.rear,
                "is_default": "true",
            })
            staggered_used += 1
        else:
            size = _pick_default_size(segment, power_hp)
            rows.append({
                "modification_id": mid,
                "axle": "both",
                "size_code": size,
                "is_default": "true",
            })
            default_used += 1

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["modification_id", "axle", "size_code", "is_default"],
            lineterminator="\n",
        )
        w.writeheader()
        w.writerows(rows)

    print(
        f"OK — wrote {len(rows)} rows -> {OUT_CSV.relative_to(REPO)} "
        f"(default both-axle: {default_used}, staggered front+rear: {staggered_used})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
