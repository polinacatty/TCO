"""Build ``ml/data/processed/car_modifications.parquet`` (шаг 2.4).

Strategy (hybrid, see ``docs/03_data_collection/05_sprint2_plan.md`` §S2.4):

1. **Segment defaults** — for each `segment` from ``car_models.csv`` we
   keep 2 typical modifications (engine, transmission, drive, consumption).
   This auto-fills any model where we don't have a curated override.
2. **Model overrides** — for topical EV models and for top-30 ICE models
   (Camry, RAV4, Solaris, X5, Coolray, etc.) we hand-write 2–4 specific
   modifications based on Wikipedia / Drom-обзоры.
3. **Electric overrides** are mandatory: for any model whose name is in
   ``ELECTRIC_MODELS`` the segment-default rule is skipped and the EV-spec
   from ``EV_OVERRIDES`` is used instead (volume=0, fc=0, fuel=ELECTRIC).

Each modification gets:
- ``id`` (auto, monotonic from 1)
- ``generation_id`` (FK to car_generations.csv)
- ``trim_name`` (human label like "1.6 AT")
- ``engine_volume_l, power_hp, torque_nm`` (basic powertrain)
- ``fuel_type, transmission, drive`` (enums)
- ``fuel_consumption_combined_l_100km`` (the only consumption field that's
  NOT NULL by schema; city/highway are nullable in MVP)
- ``length_mm, width_mm, height_mm, curb_weight_kg, seats`` (left NULL in MVP
  because they don't affect TCO directly)
- ``msrp_new_rub`` (NULL in MVP — comes from market signals later)

Run:
    python ml/pipelines/_car_modifications_build.py
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import NamedTuple

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
MAKES_CSV = REPO / "ml" / "data" / "seed" / "car_makes.csv"
MODELS_CSV = REPO / "ml" / "data" / "seed" / "car_models.csv"
GENS_CSV = REPO / "ml" / "data" / "seed" / "car_generations.csv"
OUT_PARQUET = REPO / "ml" / "data" / "processed" / "car_modifications.parquet"


class Mod(NamedTuple):
    """One modification spec (segment-default or override)."""
    engine_volume_l: float
    power_hp: int
    torque_nm: int | None
    fuel_type: str           # AI92|AI95|AI98|AI100|DIESEL|LPG|CNG|ELECTRIC|HYBRID
    transmission: str        # MT|AT|CVT|AMT|DCT|DIRECT
    drive: str               # FWD|RWD|AWD|4WD_PARTTIME
    fuel_consumption_combined_l_100km: float
    trim_name: str


# ─── Segment defaults ───────────────────────────────────────────────────
# Typical 2-modification template per segment for ICE cars.
SEGMENT_DEFAULTS: dict[str, list[Mod]] = {
    "A":       [Mod(1.0,  75,  95, "AI95", "MT",  "FWD", 5.5, "1.0 MT"),
                Mod(1.2,  85, 110, "AI95", "AT",  "FWD", 6.0, "1.2 AT")],
    "B":       [Mod(1.4, 100, 130, "AI95", "MT",  "FWD", 6.3, "1.4 MT"),
                Mod(1.6, 113, 152, "AI95", "AT",  "FWD", 6.8, "1.6 AT")],
    "C":       [Mod(1.6, 123, 158, "AI95", "MT",  "FWD", 7.0, "1.6 MT"),
                Mod(1.8, 140, 180, "AI95", "AT",  "FWD", 7.5, "1.8 AT")],
    "D":       [Mod(2.0, 150, 200, "AI95", "AT",  "FWD", 7.8, "2.0 AT"),
                Mod(2.5, 200, 250, "AI95", "AT",  "AWD", 9.0, "2.5 AT AWD")],
    "E":       [Mod(2.0, 220, 350, "AI95", "AT",  "AWD", 8.5, "2.0T AT AWD"),
                Mod(3.0, 290, 450, "AI95", "AT",  "AWD", 10.0, "3.0 AT AWD")],
    "F":       [Mod(3.0, 340, 480, "AI98", "AT",  "AWD", 11.0, "3.0 AT AWD"),
                Mod(4.0, 450, 650, "AI98", "AT",  "AWD", 12.5, "4.0 AT AWD")],
    "J_CROSS": [Mod(1.6, 130, 200, "AI95", "AT",  "FWD", 7.5, "1.6 AT"),
                Mod(2.0, 170, 240, "AI95", "AT",  "AWD", 8.7, "2.0 AT AWD")],
    "J_SUV":   [Mod(2.8, 180, 450, "DIESEL", "AT", "4WD_PARTTIME", 9.5, "2.8d AT 4WD"),
                Mod(3.5, 280, 380, "AI95", "AT",  "4WD_PARTTIME", 12.0, "3.5 AT 4WD")],
    "M_MPV":   [Mod(2.0, 150, 200, "AI95", "AT",  "FWD", 8.5, "2.0 AT"),
                Mod(2.5, 180, 350, "DIESEL", "AT", "AWD", 9.0, "2.5d AT AWD")],
    "S_SPORT": [Mod(3.0, 400, 500, "AI98", "AT",  "RWD", 10.5, "3.0 AT"),
                Mod(5.0, 580, 650, "AI98", "AT",  "AWD", 13.0, "5.0 AT AWD")],
    "LCV":     [Mod(2.4, 150, 360, "DIESEL", "MT", "RWD", 9.0, "2.4d MT"),
                Mod(2.8, 180, 450, "DIESEL", "AT", "4WD_PARTTIME", 11.0, "2.8d AT 4WD")],
    "OTHER":   [Mod(1.6, 100, 150, "AI95", "MT",  "FWD", 7.0, "1.6 MT")],
}


# ─── Electric models (full BEV) — one EV spec per model ─────────────────
# Source: производительность по официальной спецификации производителя
# на момент актуального поколения; расход топлива = 0 (электричка), а
# fuel_type = ELECTRIC.  Для расчёта TCO по топливу используем не fc, а
# отдельный параметр потребления электроэнергии (вне этой таблицы).
EV_OVERRIDES: dict[tuple[str, str], list[Mod]] = {
    # ── Tesla ─────────────────────────────────────────────
    ("tesla", "models"):       [Mod(0.0, 670, None, "ELECTRIC", "DIRECT", "AWD", 0.0, "Long Range AWD")],
    ("tesla", "model3"):       [Mod(0.0, 283, None, "ELECTRIC", "DIRECT", "RWD", 0.0, "RWD"),
                                Mod(0.0, 498, None, "ELECTRIC", "DIRECT", "AWD", 0.0, "Long Range AWD")],
    ("tesla", "modelx"):       [Mod(0.0, 670, None, "ELECTRIC", "DIRECT", "AWD", 0.0, "Long Range AWD")],
    ("tesla", "modely"):       [Mod(0.0, 295, None, "ELECTRIC", "DIRECT", "RWD", 0.0, "RWD"),
                                Mod(0.0, 384, None, "ELECTRIC", "DIRECT", "AWD", 0.0, "Long Range AWD")],
    ("tesla", "cybertruck"):   [Mod(0.0, 845, None, "ELECTRIC", "DIRECT", "AWD", 0.0, "Cyberbeast")],
    # ── Chinese EVs ───────────────────────────────────────
    ("aito", "m5"):            [Mod(0.0, 496, None, "HYBRID",   "DIRECT", "AWD", 6.0, "EREV AWD")],
    ("aito", "m7"):            [Mod(0.0, 496, None, "HYBRID",   "DIRECT", "AWD", 6.5, "EREV AWD")],
    ("aito", "m9"):            [Mod(0.0, 530, None, "HYBRID",   "DIRECT", "AWD", 7.0, "EREV AWD")],
    ("lixiang", "l7"):         [Mod(0.0, 449, None, "HYBRID",   "DIRECT", "AWD", 6.5, "EREV AWD")],
    ("lixiang", "l8"):         [Mod(0.0, 449, None, "HYBRID",   "DIRECT", "AWD", 7.0, "EREV AWD")],
    ("lixiang", "l9"):         [Mod(0.0, 449, None, "HYBRID",   "DIRECT", "AWD", 7.5, "EREV AWD")],
    ("lixiang", "one"):        [Mod(0.0, 326, None, "HYBRID",   "DIRECT", "AWD", 6.0, "EREV AWD")],
    ("xiaomi", "su7"):         [Mod(0.0, 673, None, "ELECTRIC", "DIRECT", "AWD", 0.0, "Max AWD")],
    ("zeekr", "001"):          [Mod(0.0, 544, None, "ELECTRIC", "DIRECT", "AWD", 0.0, "AWD")],
    ("zeekr", "007"):          [Mod(0.0, 475, None, "ELECTRIC", "DIRECT", "AWD", 0.0, "AWD")],
    ("zeekr", "009"):          [Mod(0.0, 544, None, "ELECTRIC", "DIRECT", "AWD", 0.0, "AWD")],
    ("zeekr", "x"):            [Mod(0.0, 422, None, "ELECTRIC", "DIRECT", "AWD", 0.0, "AWD")],
    ("avatr", "11"):           [Mod(0.0, 578, None, "ELECTRIC", "DIRECT", "AWD", 0.0, "AWD")],
    ("avatr", "12"):           [Mod(0.0, 578, None, "ELECTRIC", "DIRECT", "AWD", 0.0, "AWD")],
    ("byd", "atto3"):          [Mod(0.0, 204, None, "ELECTRIC", "DIRECT", "FWD", 0.0, "FWD")],
    ("byd", "han"):            [Mod(0.0, 517, None, "ELECTRIC", "DIRECT", "AWD", 0.0, "EV AWD")],
    ("byd", "seal"):           [Mod(0.0, 530, None, "ELECTRIC", "DIRECT", "AWD", 0.0, "AWD")],
    ("byd", "seagull"):        [Mod(0.0, 75,  None, "ELECTRIC", "DIRECT", "FWD", 0.0, "FWD")],
    ("byd", "songplus"):       [Mod(1.5, 160, 245, "HYBRID",   "DCT",    "FWD", 5.5, "1.5 DM-i")],
    ("byd", "tang"):           [Mod(0.0, 517, None, "ELECTRIC", "DIRECT", "AWD", 0.0, "EV AWD")],
    ("voyah", "free"):         [Mod(0.0, 530, None, "ELECTRIC", "DIRECT", "AWD", 0.0, "AWD")],
    ("voyah", "dream"):        [Mod(0.0, 435, None, "HYBRID",   "DIRECT", "AWD", 6.5, "EREV AWD")],
    ("voyah", "courage"):      [Mod(0.0, 422, None, "ELECTRIC", "DIRECT", "AWD", 0.0, "AWD")],
    ("voyah", "passion"):      [Mod(0.0, 530, None, "ELECTRIC", "DIRECT", "AWD", 0.0, "AWD")],
    ("hiphi", "x"):            [Mod(0.0, 598, None, "ELECTRIC", "DIRECT", "AWD", 0.0, "AWD")],
    ("hiphi", "y"):            [Mod(0.0, 489, None, "ELECTRIC", "DIRECT", "AWD", 0.0, "AWD")],
    ("hiphi", "z"):            [Mod(0.0, 672, None, "ELECTRIC", "DIRECT", "AWD", 0.0, "AWD")],
    ("nio", "es6"):            [Mod(0.0, 489, None, "ELECTRIC", "DIRECT", "AWD", 0.0, "AWD")],
    ("nio", "es8"):            [Mod(0.0, 645, None, "ELECTRIC", "DIRECT", "AWD", 0.0, "AWD")],
    ("nio", "et7"):            [Mod(0.0, 644, None, "ELECTRIC", "DIRECT", "AWD", 0.0, "AWD")],
    ("mhero", "mhero1"):       [Mod(0.0, 800, None, "ELECTRIC", "DIRECT", "AWD", 0.0, "AWD")],
    ("seres", "3"):            [Mod(1.5, 152, 270, "HYBRID",   "DIRECT", "FWD", 6.0, "EREV FWD")],
    ("seres", "5"):            [Mod(0.0, 530, None, "ELECTRIC", "DIRECT", "AWD", 0.0, "AWD")],
    ("skywell", "et5"):        [Mod(0.0, 204, None, "ELECTRIC", "DIRECT", "FWD", 0.0, "FWD")],
    ("hongqi", "ehs9"):        [Mod(0.0, 462, None, "ELECTRIC", "DIRECT", "AWD", 0.0, "AWD")],
    ("wuling", "hongguangminiev"): [Mod(0.0, 41, None, "ELECTRIC", "DIRECT", "RWD", 0.0, "Macaron")],
    # ── European premium EVs ──────────────────────────────
    ("audi", "etron"):         [Mod(0.0, 408, None, "ELECTRIC", "DIRECT", "AWD", 0.0, "55 quattro")],
    ("bmw", "ix"):             [Mod(0.0, 523, None, "ELECTRIC", "DIRECT", "AWD", 0.0, "xDrive50")],
    ("bmw", "i4"):             [Mod(0.0, 340, None, "ELECTRIC", "DIRECT", "RWD", 0.0, "eDrive40")],
    ("mercedesbenz", "eqs"):   [Mod(0.0, 524, None, "ELECTRIC", "DIRECT", "AWD", 0.0, "450 4MATIC")],
    ("porsche", "taycan"):     [Mod(0.0, 408, None, "ELECTRIC", "DIRECT", "RWD", 0.0, "RWD"),
                                Mod(0.0, 761, None, "ELECTRIC", "DIRECT", "AWD", 0.0, "Turbo S")],
    ("genesis", "gv60"):       [Mod(0.0, 314, None, "ELECTRIC", "DIRECT", "AWD", 0.0, "AWD")],
    ("jaguar", "ipace"):       [Mod(0.0, 400, None, "ELECTRIC", "DIRECT", "AWD", 0.0, "EV400")],
    ("nissan", "leaf"):        [Mod(0.0, 150, None, "ELECTRIC", "DIRECT", "FWD", 0.0, "e+")],
    ("lotus", "eletre"):       [Mod(0.0, 603, None, "ELECTRIC", "DIRECT", "AWD", 0.0, "AWD")],
}


# ─── Top-N ICE model overrides ──────────────────────────────────────────
# Hand-curated specs for the most popular ICE models on the Russian market
# (Wikipedia + Drom-обзоры).  3–4 modifications each so the catalog has
# enough breadth for the user to pick a "real" trim.
ICE_OVERRIDES: dict[tuple[str, str], list[Mod]] = {
    # ── Lada ──────────────────────────────────────────────
    ("lada", "granta"):        [Mod(1.6,  90, 143, "AI92", "MT",  "FWD", 7.0, "1.6 MT 8V"),
                                Mod(1.6, 106, 148, "AI92", "AT",  "FWD", 7.5, "1.6 AT 16V")],
    ("lada", "vesta"):         [Mod(1.6, 106, 148, "AI92", "MT",  "FWD", 6.9, "1.6 MT"),
                                Mod(1.6, 106, 148, "AI92", "CVT", "FWD", 7.4, "1.6 CVT"),
                                Mod(1.8, 122, 170, "AI92", "CVT", "FWD", 8.0, "1.8 CVT")],
    ("lada", "nivalegend"):    [Mod(1.7,  83, 129, "AI92", "MT",  "4WD_PARTTIME", 9.9, "1.7 MT 4WD")],
    ("lada", "nivatravel"):    [Mod(1.7,  80, 127, "AI92", "MT",  "4WD_PARTTIME", 10.0, "1.7 MT 4WD")],
    ("lada", "largus"):        [Mod(1.6,  90, 143, "AI92", "MT",  "FWD", 7.7, "1.6 MT 8V"),
                                Mod(1.6, 106, 148, "AI92", "MT",  "FWD", 7.7, "1.6 MT 16V")],
    # ── UAZ ───────────────────────────────────────────────
    ("uaz", "patriot"):        [Mod(2.7, 150, 235, "AI92", "MT",  "4WD_PARTTIME", 11.5, "2.7 MT 4WD"),
                                Mod(2.7, 150, 235, "AI92", "AT",  "4WD_PARTTIME", 12.5, "2.7 AT 4WD")],
    ("uaz", "hunter"):         [Mod(2.7, 128, 209, "AI92", "MT",  "4WD_PARTTIME", 12.5, "2.7 MT 4WD")],
    # ── Hyundai/Kia top sedans/CUVs ──────────────────────
    ("hyundai", "solaris"):    [Mod(1.4, 100, 132, "AI95", "MT",  "FWD", 6.4, "1.4 MT"),
                                Mod(1.6, 123, 151, "AI95", "AT",  "FWD", 7.1, "1.6 AT")],
    ("hyundai", "creta"):      [Mod(1.6, 121, 150, "AI95", "AT",  "FWD", 7.4, "1.6 AT FWD"),
                                Mod(2.0, 149, 191, "AI95", "AT",  "AWD", 8.6, "2.0 AT AWD")],
    ("hyundai", "tucson"):     [Mod(2.0, 150, 192, "AI95", "AT",  "FWD", 8.4, "2.0 AT FWD"),
                                Mod(2.5, 180, 232, "AI95", "AT",  "AWD", 9.4, "2.5 AT AWD")],
    ("hyundai", "sonata"):     [Mod(2.0, 150, 192, "AI95", "AT",  "FWD", 7.6, "2.0 AT"),
                                Mod(2.5, 180, 232, "AI95", "AT",  "FWD", 8.5, "2.5 AT")],
    ("hyundai", "elantra"):    [Mod(1.6, 128, 157, "AI95", "AT",  "FWD", 6.9, "1.6 AT"),
                                Mod(2.0, 150, 192, "AI95", "AT",  "FWD", 7.6, "2.0 AT")],
    ("hyundai", "palisade"):   [Mod(2.2, 200, 440, "DIESEL","AT",  "AWD", 8.0, "2.2d AT AWD"),
                                Mod(3.5, 249, 336, "AI95", "AT",  "AWD", 11.4, "3.5 AT AWD")],
    ("hyundai", "santafe"):    [Mod(2.5, 180, 232, "AI95", "AT",  "AWD", 9.5, "2.5 AT AWD"),
                                Mod(2.2, 200, 440, "DIESEL","AT",  "AWD", 7.5, "2.2d AT AWD")],
    ("kia", "rio"):            [Mod(1.4, 100, 132, "AI95", "MT",  "FWD", 6.5, "1.4 MT"),
                                Mod(1.6, 123, 151, "AI95", "AT",  "FWD", 7.1, "1.6 AT")],
    ("kia", "cerato"):         [Mod(1.6, 128, 157, "AI95", "AT",  "FWD", 7.0, "1.6 AT"),
                                Mod(2.0, 150, 192, "AI95", "AT",  "FWD", 7.6, "2.0 AT")],
    ("kia", "sportage"):       [Mod(2.0, 150, 192, "AI95", "AT",  "FWD", 8.4, "2.0 AT FWD"),
                                Mod(2.5, 180, 232, "AI95", "AT",  "AWD", 9.4, "2.5 AT AWD")],
    ("kia", "sorento"):        [Mod(2.5, 180, 232, "AI95", "AT",  "AWD", 9.5, "2.5 AT AWD"),
                                Mod(2.2, 199, 440, "DIESEL","AT",  "AWD", 7.5, "2.2d AT AWD")],
    ("kia", "k5"):             [Mod(2.0, 150, 192, "AI95", "AT",  "FWD", 7.6, "2.0 AT"),
                                Mod(2.5, 180, 232, "AI95", "AT",  "FWD", 8.5, "2.5 AT")],
    ("kia", "seltos"):         [Mod(1.6, 123, 151, "AI95", "AT",  "FWD", 7.5, "1.6 AT FWD"),
                                Mod(2.0, 149, 180, "AI95", "CVT", "AWD", 8.0, "2.0 CVT AWD")],
    # ── Toyota top ────────────────────────────────────────
    ("toyota", "camry"):       [Mod(2.0, 150, 200, "AI95", "AT",  "FWD", 7.5, "2.0 AT"),
                                Mod(2.5, 200, 250, "AI95", "AT",  "FWD", 8.0, "2.5 AT"),
                                Mod(3.5, 249, 356, "AI95", "AT",  "AWD", 9.5, "3.5 AT AWD")],
    ("toyota", "corolla"):     [Mod(1.6, 122, 157, "AI95", "AT",  "FWD", 6.5, "1.6 AT"),
                                Mod(1.8, 140, 175, "AI95", "CVT", "FWD", 6.4, "1.8 CVT")],
    ("toyota", "rav4"):        [Mod(2.0, 149, 195, "AI95", "CVT", "FWD", 7.0, "2.0 CVT FWD"),
                                Mod(2.5, 199, 243, "AI95", "AT",  "AWD", 8.0, "2.5 AT AWD")],
    ("toyota", "landcruiser"): [Mod(3.5, 415, 650, "AI95", "AT",  "4WD_PARTTIME", 12.4, "3.5TT AT 4WD"),
                                Mod(3.3, 309, 700, "DIESEL","AT",  "4WD_PARTTIME", 8.9, "3.3d AT 4WD")],
    ("toyota", "landcruiserprado"): [Mod(2.7, 163, 246, "AI95", "AT",  "4WD_PARTTIME", 11.0, "2.7 AT 4WD"),
                                     Mod(2.8, 204, 500, "DIESEL","AT", "4WD_PARTTIME", 8.5, "2.8d AT 4WD")],
    ("toyota", "highlander"):  [Mod(3.5, 249, 356, "AI95", "AT",  "AWD", 9.7, "3.5 AT AWD")],
    ("toyota", "fortuner"):    [Mod(2.7, 166, 245, "AI95", "AT",  "4WD_PARTTIME", 10.5, "2.7 AT 4WD"),
                                Mod(2.8, 204, 500, "DIESEL","AT", "4WD_PARTTIME", 8.6, "2.8d AT 4WD")],
    ("toyota", "hilux"):       [Mod(2.4, 150, 400, "DIESEL","MT", "4WD_PARTTIME", 7.5, "2.4d MT 4WD"),
                                Mod(2.8, 204, 500, "DIESEL","AT", "4WD_PARTTIME", 8.1, "2.8d AT 4WD")],
    # ── Mazda ─────────────────────────────────────────────
    ("mazda", "cx5"):          [Mod(2.0, 150, 200, "AI95", "AT",  "FWD", 7.4, "2.0 AT FWD"),
                                Mod(2.5, 192, 258, "AI95", "AT",  "AWD", 8.4, "2.5 AT AWD")],
    ("mazda", "6"):            [Mod(2.0, 150, 200, "AI95", "AT",  "FWD", 7.0, "2.0 AT"),
                                Mod(2.5, 192, 258, "AI95", "AT",  "FWD", 7.4, "2.5 AT")],
    # ── Nissan ────────────────────────────────────────────
    ("nissan", "qashqai"):     [Mod(2.0, 144, 200, "AI95", "CVT", "FWD", 7.4, "2.0 CVT FWD"),
                                Mod(2.0, 144, 200, "AI95", "CVT", "AWD", 8.0, "2.0 CVT AWD")],
    ("nissan", "xtrail"):      [Mod(2.0, 144, 200, "AI95", "CVT", "FWD", 7.4, "2.0 CVT FWD"),
                                Mod(2.5, 171, 233, "AI95", "CVT", "AWD", 8.3, "2.5 CVT AWD")],
    ("nissan", "almera"):      [Mod(1.6, 102, 145, "AI95", "MT",  "FWD", 7.0, "1.6 MT"),
                                Mod(1.6, 102, 145, "AI95", "AT",  "FWD", 7.6, "1.6 AT")],
    ("nissan", "patrol"):      [Mod(5.6, 405, 560, "AI95", "AT",  "4WD_PARTTIME", 14.4, "5.6 AT 4WD")],
    # ── VW/Skoda ──────────────────────────────────────────
    ("volkswagen", "polo"):    [Mod(1.6, 110, 155, "AI95", "MT",  "FWD", 6.0, "1.6 MT"),
                                Mod(1.6, 110, 155, "AI95", "AT",  "FWD", 6.5, "1.6 AT")],
    ("volkswagen", "tiguan"):  [Mod(1.4, 150, 250, "AI95", "DCT", "FWD", 7.4, "1.4 TSI DSG"),
                                Mod(2.0, 180, 320, "AI95", "DCT", "AWD", 7.9, "2.0 TSI 4Motion")],
    ("volkswagen", "touareg"): [Mod(3.0, 249, 500, "DIESEL","AT", "AWD", 7.4, "3.0 TDI AT 4Motion"),
                                Mod(3.0, 340, 450, "AI95", "AT",  "AWD", 9.6, "3.0 TSI AT 4Motion")],
    ("skoda", "octavia"):      [Mod(1.4, 150, 250, "AI95", "DCT", "FWD", 6.0, "1.4 TSI DSG"),
                                Mod(1.8, 180, 250, "AI95", "DCT", "AWD", 7.0, "1.8 TSI DSG 4x4")],
    ("skoda", "kodiaq"):       [Mod(1.4, 150, 250, "AI95", "AT",  "FWD", 7.4, "1.4 TSI AT"),
                                Mod(2.0, 190, 320, "AI95", "DCT", "AWD", 7.9, "2.0 TSI DSG 4x4")],
    # ── Renault ───────────────────────────────────────────
    ("renault", "logan"):      [Mod(1.6,  82, 134, "AI92", "MT",  "FWD", 7.1, "1.6 MT 8V"),
                                Mod(1.6, 113, 152, "AI95", "AT",  "FWD", 7.5, "1.6 AT 16V")],
    ("renault", "duster"):     [Mod(1.6, 114, 156, "AI95", "MT",  "FWD", 7.6, "1.6 MT FWD"),
                                Mod(2.0, 143, 195, "AI95", "AT",  "AWD", 9.4, "2.0 AT AWD")],
    ("renault", "kaptur"):     [Mod(1.6, 114, 156, "AI95", "MT",  "FWD", 7.6, "1.6 MT FWD"),
                                Mod(2.0, 143, 195, "AI95", "AT",  "AWD", 9.4, "2.0 AT AWD")],
    ("renault", "arkana"):     [Mod(1.6, 114, 152, "AI95", "CVT", "FWD", 7.6, "1.6 CVT FWD"),
                                Mod(1.3, 150, 250, "AI95", "CVT", "AWD", 7.4, "1.3 TCe CVT AWD")],
    # ── BMW ───────────────────────────────────────────────
    ("bmw", "3series"):        [Mod(2.0, 184, 300, "AI95", "AT",  "RWD", 6.5, "320i AT"),
                                Mod(2.0, 245, 400, "AI95", "AT",  "AWD", 7.0, "330i xDrive AT"),
                                Mod(3.0, 374, 500, "AI98", "AT",  "AWD", 8.5, "M340i xDrive AT")],
    ("bmw", "5series"):        [Mod(2.0, 252, 400, "AI95", "AT",  "AWD", 7.5, "530i xDrive AT"),
                                Mod(3.0, 333, 450, "AI98", "AT",  "AWD", 8.5, "540i xDrive AT")],
    ("bmw", "x3"):             [Mod(2.0, 184, 300, "AI95", "AT",  "AWD", 7.6, "xDrive20i AT"),
                                Mod(2.0, 252, 400, "AI95", "AT",  "AWD", 8.0, "xDrive30i AT")],
    ("bmw", "x5"):             [Mod(3.0, 340, 450, "AI98", "AT",  "AWD", 9.5, "xDrive40i AT"),
                                Mod(3.0, 286, 650, "DIESEL","AT", "AWD", 7.0, "xDrive30d AT"),
                                Mod(4.4, 530, 750, "AI98", "AT",  "AWD", 12.5, "M50i AT")],
    ("bmw", "x7"):             [Mod(3.0, 340, 450, "AI98", "AT",  "AWD", 10.5, "xDrive40i AT"),
                                Mod(4.4, 530, 750, "AI98", "AT",  "AWD", 13.0, "M60i AT")],
    # ── Mercedes ──────────────────────────────────────────
    ("mercedesbenz", "cclass"):[Mod(1.5, 204, 300, "AI95", "AT",  "RWD", 6.5, "C 200 AT"),
                                Mod(2.0, 258, 400, "AI95", "AT",  "AWD", 7.5, "C 300 4MATIC AT")],
    ("mercedesbenz", "eclass"):[Mod(2.0, 197, 320, "AI95", "AT",  "AWD", 7.0, "E 200 4MATIC AT"),
                                Mod(3.0, 367, 500, "AI98", "AT",  "AWD", 8.5, "E 450 4MATIC AT")],
    ("mercedesbenz", "sclass"):[Mod(3.0, 367, 500, "AI98", "AT",  "AWD", 8.5, "S 450 4MATIC AT"),
                                Mod(4.0, 612, 900, "AI98", "AT",  "AWD", 11.5, "S 63 AMG 4MATIC")],
    ("mercedesbenz", "glc"):   [Mod(2.0, 258, 400, "AI95", "AT",  "AWD", 7.8, "GLC 300 4MATIC AT"),
                                Mod(2.0, 197, 320, "AI95", "AT",  "AWD", 7.5, "GLC 200 4MATIC AT")],
    ("mercedesbenz", "gle"):   [Mod(3.0, 367, 500, "AI98", "AT",  "AWD", 9.5, "GLE 450 4MATIC AT"),
                                Mod(3.0, 286, 650, "DIESEL","AT", "AWD", 7.4, "GLE 350d 4MATIC AT")],
    ("mercedesbenz", "gclass"):[Mod(4.0, 422, 610, "AI98", "AT",  "4WD_PARTTIME", 12.0, "G 500 AT"),
                                Mod(4.0, 585, 850, "AI98", "AT",  "4WD_PARTTIME", 13.5, "G 63 AMG AT")],
    # ── Audi ──────────────────────────────────────────────
    ("audi", "a4"):            [Mod(2.0, 190, 320, "AI95", "AT",  "FWD", 6.4, "40 TFSI AT"),
                                Mod(2.0, 249, 370, "AI95", "AT",  "AWD", 7.0, "45 TFSI quattro AT")],
    ("audi", "a6"):            [Mod(2.0, 245, 370, "AI95", "AT",  "AWD", 7.0, "45 TFSI quattro AT"),
                                Mod(3.0, 340, 500, "AI98", "AT",  "AWD", 8.0, "55 TFSI quattro AT")],
    ("audi", "q5"):            [Mod(2.0, 249, 370, "AI95", "AT",  "AWD", 7.5, "45 TFSI quattro AT"),
                                Mod(2.0, 204, 400, "DIESEL","AT", "AWD", 6.0, "40 TDI quattro AT")],
    ("audi", "q7"):            [Mod(3.0, 340, 500, "AI98", "AT",  "AWD", 9.0, "55 TFSI quattro AT"),
                                Mod(3.0, 286, 600, "DIESEL","AT", "AWD", 7.0, "50 TDI quattro AT")],
    ("audi", "q8"):            [Mod(3.0, 340, 500, "AI98", "AT",  "AWD", 9.5, "55 TFSI quattro AT")],
    # ── Geely / Chery / Haval (top Chinese ICE) ──────────
    ("geely", "coolray"):      [Mod(1.5, 150, 255, "AI95", "DCT", "FWD", 7.0, "1.5T DCT")],
    ("geely", "atlas"):        [Mod(2.0, 200, 300, "AI95", "AT",  "FWD", 7.6, "2.0T AT FWD"),
                                Mod(2.0, 200, 300, "AI95", "AT",  "AWD", 8.5, "2.0T AT AWD")],
    ("geely", "atlaspro"):     [Mod(1.5, 177, 255, "AI95", "DCT", "FWD", 6.8, "1.5T DCT")],
    ("geely", "tugella"):      [Mod(2.0, 238, 350, "AI95", "AT",  "AWD", 8.0, "2.0T AT AWD")],
    ("geely", "monjaro"):      [Mod(2.0, 238, 350, "AI95", "AT",  "AWD", 8.5, "2.0T AT AWD")],
    ("chery", "tiggo7pro"):    [Mod(1.5, 147, 210, "AI95", "CVT", "FWD", 6.9, "1.5T CVT"),
                                Mod(1.6, 186, 290, "AI95", "DCT", "FWD", 7.5, "1.6T DCT")],
    ("chery", "tiggo8pro"):    [Mod(1.6, 186, 290, "AI95", "DCT", "FWD", 7.5, "1.6T DCT FWD"),
                                Mod(2.0, 254, 390, "AI95", "DCT", "AWD", 8.5, "2.0T DCT AWD")],
    ("chery", "tiggo8promax"): [Mod(2.0, 261, 400, "AI95", "DCT", "AWD", 8.6, "2.0T DCT AWD")],
    ("chery", "tiggo4"):       [Mod(1.5, 113, 141, "AI95", "CVT", "FWD", 7.0, "1.5 CVT"),
                                Mod(1.5, 147, 210, "AI95", "CVT", "FWD", 7.4, "1.5T CVT")],
    ("haval", "jolion"):       [Mod(1.5, 143, 210, "AI95", "DCT", "FWD", 7.0, "1.5T DCT")],
    ("haval", "f7"):           [Mod(1.5, 150, 220, "AI95", "DCT", "FWD", 7.4, "1.5T DCT FWD"),
                                Mod(2.0, 190, 340, "AI95", "DCT", "AWD", 8.4, "2.0T DCT AWD")],
    ("haval", "h6"):           [Mod(1.5, 150, 220, "AI95", "DCT", "FWD", 7.0, "1.5T DCT")],
    ("haval", "dargo"):        [Mod(2.0, 192, 320, "AI95", "DCT", "AWD", 8.5, "2.0T DCT AWD")],
    ("changan", "cs35plus"):   [Mod(1.4, 158, 260, "AI95", "DCT", "FWD", 6.9, "1.4T DCT")],
    ("changan", "cs55plus"):   [Mod(1.5, 188, 300, "AI95", "AT",  "FWD", 7.4, "1.5T AT")],
    ("changan", "cs75plus"):   [Mod(2.0, 233, 360, "AI95", "AT",  "AWD", 8.4, "2.0T AT AWD")],
    ("exeed", "txl"):          [Mod(1.6, 197, 290, "AI95", "DCT", "AWD", 8.0, "1.6T DCT AWD"),
                                Mod(2.0, 261, 400, "AI95", "DCT", "AWD", 8.6, "2.0T DCT AWD")],
    ("exeed", "lx"):           [Mod(1.6, 197, 290, "AI95", "DCT", "FWD", 7.5, "1.6T DCT")],
    ("exeed", "vx"):           [Mod(2.0, 249, 390, "AI95", "AT",  "AWD", 9.0, "2.0T AT AWD")],
    ("omoda", "c5"):           [Mod(1.5, 150, 230, "AI95", "CVT", "FWD", 6.9, "1.5T CVT")],
    ("jaecoo", "j7"):          [Mod(1.6, 186, 290, "AI95", "DCT", "AWD", 7.5, "1.6T DCT AWD")],
    ("tank", "300"):           [Mod(2.0, 220, 380, "AI95", "AT",  "4WD_PARTTIME", 9.5, "2.0T AT 4WD")],
    ("tank", "500"):           [Mod(3.0, 354, 500, "AI95", "AT",  "4WD_PARTTIME", 12.0, "3.0T AT 4WD")],
    # ── Lexus / Land Rover ────────────────────────────────
    ("lexus", "rx"):           [Mod(2.5, 250, 460, "HYBRID","CVT", "AWD", 6.5, "350h AWD"),
                                Mod(3.5, 295, 380, "AI95", "AT",  "AWD", 9.5, "350 AT AWD")],
    ("lexus", "lx"):           [Mod(3.4, 415, 650, "AI98", "AT",  "4WD_PARTTIME", 12.4, "LX 600 AT 4WD")],
    ("lexus", "nx"):           [Mod(2.5, 244, 240, "HYBRID","CVT", "AWD", 5.7, "NX 350h AWD")],
    ("landrover", "defender"): [Mod(3.0, 400, 550, "AI98", "AT",  "AWD", 11.0, "P400 AT"),
                                Mod(3.0, 300, 650, "DIESEL","AT", "AWD", 7.5, "D300 AT")],
    ("landrover", "rangerover"): [Mod(3.0, 400, 550, "AI98", "AT", "AWD", 10.5, "P400 AT"),
                                  Mod(4.4, 530, 750, "AI98", "AT", "AWD", 12.5, "P530 AT")],
    ("landrover", "rangeroversport"): [Mod(3.0, 400, 550, "AI98", "AT", "AWD", 10.0, "P400 AT")],
    # ── Porsche / Ferrari / etc. ─────────────────────────
    ("porsche", "cayenne"):    [Mod(3.0, 340, 450, "AI98", "AT",  "AWD", 9.7, "3.0 AT"),
                                Mod(4.0, 460, 620, "AI98", "AT",  "AWD", 11.5, "GTS 4.0 AT"),
                                Mod(4.0, 631, 850, "AI98", "AT",  "AWD", 13.5, "Turbo GT 4.0 AT")],
    ("porsche", "macan"):      [Mod(2.0, 265, 400, "AI98", "DCT", "AWD", 8.5, "2.0 DCT AWD"),
                                Mod(2.9, 440, 550, "AI98", "DCT", "AWD", 10.5, "GTS 2.9 DCT AWD")],
    ("porsche", "panamera"):   [Mod(2.9, 353, 500, "AI98", "DCT", "AWD", 8.5, "4 2.9 DCT AWD"),
                                Mod(4.0, 630, 820, "AI98", "DCT", "AWD", 12.0, "Turbo S 4.0 DCT AWD")],
    ("porsche", "911"):        [Mod(3.0, 385, 450, "AI98", "DCT", "RWD", 9.0, "Carrera 3.0 PDK"),
                                Mod(3.7, 580, 750, "AI98", "DCT", "AWD", 11.0, "Turbo S 3.7 PDK")],
    # ── Misc — popular but not top ───────────────────────
    ("subaru", "forester"):    [Mod(2.0, 150, 196, "AI95", "CVT", "AWD", 7.0, "2.0 CVT AWD"),
                                Mod(2.5, 184, 239, "AI95", "CVT", "AWD", 7.4, "2.5 CVT AWD")],
    ("subaru", "outback"):     [Mod(2.5, 188, 245, "AI95", "CVT", "AWD", 7.4, "2.5 CVT AWD")],
    ("mitsubishi", "outlander"): [Mod(2.0, 150, 195, "AI95", "CVT", "FWD", 7.0, "2.0 CVT FWD"),
                                  Mod(2.4, 167, 222, "AI95", "CVT", "AWD", 7.7, "2.4 CVT AWD")],
    ("mitsubishi", "pajerosport"): [Mod(2.4, 181, 430, "DIESEL","AT","4WD_PARTTIME", 8.1, "2.4d AT 4WD"),
                                    Mod(3.0, 220, 281, "AI95", "AT", "4WD_PARTTIME", 11.5, "3.0 AT 4WD")],
    ("mitsubishi", "l200"):    [Mod(2.4, 181, 430, "DIESEL","MT","4WD_PARTTIME", 7.6, "2.4d MT 4WD"),
                                Mod(2.4, 181, 430, "DIESEL","AT","4WD_PARTTIME", 8.1, "2.4d AT 4WD")],
    ("ford", "kuga"):          [Mod(1.6, 150, 240, "AI95", "AT", "FWD", 7.5, "1.6 EcoBoost AT"),
                                Mod(2.5, 150, 240, "AI95", "AT", "AWD", 8.5, "2.5 AT AWD")],
    ("ford", "explorer"):      [Mod(3.0, 365, 515, "AI95", "AT", "AWD", 11.0, "3.0 EcoBoost AT")],
    ("jeep", "grandcherokee"): [Mod(3.6, 286, 347, "AI95", "AT", "AWD", 11.5, "3.6 AT")],
    ("jeep", "wrangler"):      [Mod(3.6, 285, 347, "AI95", "AT", "4WD_PARTTIME", 12.5, "3.6 AT 4WD")],
    ("honda", "crv"):          [Mod(1.5, 193, 243, "AI95", "CVT", "AWD", 7.5, "1.5T CVT AWD")],
    ("honda", "civic"):        [Mod(1.5, 182, 240, "AI95", "CVT", "FWD", 6.5, "1.5T CVT")],
    ("honda", "accord"):       [Mod(1.5, 192, 260, "AI95", "CVT", "FWD", 6.5, "1.5T CVT")],
    ("infiniti", "qx80"):      [Mod(5.6, 405, 560, "AI95", "AT", "AWD", 14.5, "5.6 AT AWD")],
    ("infiniti", "qx60"):      [Mod(3.5, 295, 365, "AI95", "CVT","AWD", 10.5, "3.5 CVT AWD")],
    # ── AURUS / Volga ────────────────────────────────────
    ("aurus", "senat"):        [Mod(4.4, 598, 880, "AI98", "AT", "AWD", 16.0, "4.4 AT AWD")],
    ("aurus", "komendant"):    [Mod(4.4, 598, 880, "AI98", "AT", "AWD", 17.0, "4.4 AT AWD")],
    ("volga", "k30"):          [Mod(2.0, 184, 300, "AI95", "AT", "AWD", 9.5, "2.0T AT AWD")],
    ("volga", "s40"):          [Mod(2.0, 184, 300, "AI95", "AT", "FWD", 8.5, "2.0T AT FWD")],
    ("moskvich", "3"):         [Mod(1.5, 150, 230, "AI95", "CVT", "FWD", 7.0, "1.5T CVT")],
    ("moskvich", "5"):         [Mod(1.5, 150, 230, "AI95", "CVT", "FWD", 7.5, "1.5T CVT")],
    ("moskvich", "6"):         [Mod(1.5, 150, 230, "AI95", "CVT", "FWD", 7.0, "1.5T CVT")],
    ("moskvich", "8"):         [Mod(1.5, 150, 230, "AI95", "CVT", "FWD", 7.5, "1.5T CVT")],
}


def main() -> int:
    if not all(p.is_file() for p in (MAKES_CSV, MODELS_CSV, GENS_CSV)):
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

    rows: list[dict[str, object]] = []
    next_id = 1
    overrides_used = 0
    ev_used = 0
    defaults_used = 0

    with GENS_CSV.open(encoding="utf-8", newline="") as f:
        for gr in csv.DictReader(f):
            gen_id = int(gr["id"])
            model_id = int(gr["model_id"])
            mr = models_by_id[model_id]
            make_id = int(mr["make_id"])
            make_norm = norm_by_make_id[make_id]
            model_norm = mr["name_normalized"]
            segment = mr["segment"]

            key = (make_norm, model_norm)
            if key in EV_OVERRIDES:
                mods = EV_OVERRIDES[key]
                ev_used += 1
            elif key in ICE_OVERRIDES:
                mods = ICE_OVERRIDES[key]
                overrides_used += 1
            else:
                mods = SEGMENT_DEFAULTS.get(segment, SEGMENT_DEFAULTS["OTHER"])
                defaults_used += 1

            for m in mods:
                rows.append({
                    "id": next_id,
                    "generation_id": gen_id,
                    "trim_name": m.trim_name,
                    "engine_volume_l": float(m.engine_volume_l),
                    "power_hp": int(m.power_hp),
                    "torque_nm": (None if m.torque_nm is None else int(m.torque_nm)),
                    "fuel_type": m.fuel_type,
                    "transmission": m.transmission,
                    "drive": m.drive,
                    "fuel_consumption_combined_l_100km": float(m.fuel_consumption_combined_l_100km),
                    "fuel_consumption_city_l_100km": None,
                    "fuel_consumption_highway_l_100km": None,
                    "length_mm": None,
                    "width_mm": None,
                    "height_mm": None,
                    "curb_weight_kg": None,
                    "seats": None,
                    "msrp_new_rub": None,
                })
                next_id += 1

    df = pd.DataFrame(rows)

    df = df.astype({
        "id": "int32",
        "generation_id": "int32",
        "engine_volume_l": "float32",
        "power_hp": "int32",
        "torque_nm": "Int32",
        "fuel_consumption_combined_l_100km": "float32",
        "fuel_consumption_city_l_100km": "Float32",
        "fuel_consumption_highway_l_100km": "Float32",
        "length_mm": "Int32",
        "width_mm": "Int32",
        "height_mm": "Int32",
        "curb_weight_kg": "Int32",
        "seats": "Int8",
        "msrp_new_rub": "Int64",
    })

    OUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT_PARQUET, index=False, engine="pyarrow", compression="snappy")

    print(
        f"OK — wrote {len(df)} rows -> {OUT_PARQUET.relative_to(REPO)} "
        f"(EV overrides: {ev_used}, ICE overrides: {overrides_used}, segment defaults: {defaults_used})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
