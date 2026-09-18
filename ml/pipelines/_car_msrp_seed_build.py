"""Build car_msrp_seed.csv from a curated list of anchor models.

Why a build-script (not pure CSV):
- We pin MSRP by (make_name, model_name, year_anchor), but the seed table
  references generation_id (FK). The mapping make+model+year -> generation_id
  must be resolved at build time against car_generations.csv to avoid drift if
  generation IDs ever change.

Output schema (car_msrp_seed.csv):
    generation_id, year, msrp_base_rub, trim_high_rub, source_url, source_note

Strategy:
- We hand-curate ~60-90 anchor entries that cover the most-sold cars on
  the Russian market 2018-2024 (top by AvtoStat: Lada Granta/Vesta/Largus,
  Hyundai Solaris, Kia Rio, Toyota Camry, VW Tiguan, etc.) plus
  representative premium and Chinese examples.
- Each anchor entry is (make_name, model_name, year_anchor, msrp_base_rub,
  trim_high_rub, source_url, source_note).
- The script joins to car_makes/models/generations to resolve generation_id
  for the year_anchor (chooses the generation whose [year_from, year_to]
  contains year_anchor).

This file is the SOURCE OF TRUTH for MSRP anchors.
The CSV (car_msrp_seed.csv) is the build artifact, regenerated on every run.
"""

import sys
from pathlib import Path
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "data" / "seed"


# (make_name, model_name, year_anchor, msrp_base_rub, trim_high_rub, source_url, source_note)
ANCHORS: list[tuple] = [
    # === RUSSIAN BRANDS — Lada ===
    ("Lada", "Granta", 2020, 540_000, 720_000,
     "https://www.lada.ru/cars/granta/",
     "Median 3 sources: lada.ru/2020-Q1, archive.org/auto.ru/2020-04, drom.ru/catalog/lada/granta"),
    ("Lada", "Granta", 2024, 850_000, 1_120_000,
     "https://www.lada.ru/cars/granta/",
     "lada.ru/2024-Q1 + drom.ru/catalog/lada/granta + autostat.ru/news/2024"),
    ("Lada", "Vesta", 2020, 690_000, 950_000,
     "https://www.lada.ru/cars/vesta/",
     "lada.ru/2020-Q1 + archive auto.ru + drom catalog"),
    ("Lada", "Vesta", 2024, 1_270_000, 1_730_000,
     "https://www.lada.ru/cars/vesta/",
     "lada.ru/2024-Q4 (NG generation) + drom + autostat"),
    ("Lada", "Largus", 2020, 760_000, 980_000,
     "https://www.lada.ru/cars/largus/",
     "lada.ru/2020-Q1 + archive auto.ru + drom"),
    ("Lada", "Largus", 2024, 1_350_000, 1_650_000,
     "https://www.lada.ru/cars/largus/",
     "lada.ru/2024 + drom catalog (post-2022 prices)"),
    ("Lada", "Niva Legend", 2024, 850_000, 1_050_000,
     "https://www.lada.ru/cars/niva-legend/",
     "lada.ru/2024-Q1 + drom catalog"),
    ("Lada", "Niva Travel", 2024, 1_100_000, 1_400_000,
     "https://www.lada.ru/cars/niva-travel/",
     "lada.ru/2024-Q1 (rebadged Chevrolet Niva) + drom"),
    ("Lada", "Iskra", 2025, 1_250_000, 1_750_000,
     "https://www.lada.ru/cars/iskra/",
     "lada.ru/2025 announcement + drom early reviews"),

    # UAZ
    ("UAZ", "Patriot", 2024, 1_550_000, 2_100_000,
     "https://uaz.ru/cars/patriot/",
     "uaz.ru/2024-Q1 + drom catalog + autostat"),
    ("UAZ", "Hunter", 2024, 1_300_000, 1_550_000,
     "https://uaz.ru/cars/hunter/",
     "uaz.ru/2024-Q1 + drom catalog"),

    # === KOREAN MASS — Hyundai/Kia ===
    ("Hyundai", "Solaris", 2020, 850_000, 1_200_000,
     "https://www.hyundai.ru/models/solaris.html",
     "hyundai.ru/2020-Q1 (pre-2022 prices) + archive auto.ru + drom"),
    ("Hyundai", "Solaris", 2022, 1_400_000, 1_800_000,
     "https://web.archive.org/web/2022*/hyundai.ru/solaris",
     "Pre-exit hyundai.ru/2022-02 + archive.org snapshots + drom 2022 listings"),
    ("Hyundai", "Creta", 2020, 950_000, 1_350_000,
     "https://www.hyundai.ru/models/creta.html",
     "hyundai.ru/2020-Q1 + archive auto.ru + drom catalog"),
    ("Hyundai", "Creta", 2022, 1_700_000, 2_300_000,
     "https://web.archive.org/web/2022*/hyundai.ru/creta",
     "hyundai.ru/2022-02 (pre-exit) + drom 2022 archives"),
    ("Hyundai", "Tucson", 2022, 2_500_000, 3_500_000,
     "https://web.archive.org/web/2022*/hyundai.ru/tucson",
     "Pre-exit hyundai.ru/2022-Q1 + drom catalog 2022"),
    ("Hyundai", "Sonata", 2022, 2_250_000, 3_200_000,
     "https://web.archive.org/web/2022*/hyundai.ru/sonata",
     "hyundai.ru/2022-Q1 + drom + autostat"),
    ("Hyundai", "Palisade", 2022, 4_000_000, 5_500_000,
     "https://web.archive.org/web/2022*/hyundai.ru/palisade",
     "hyundai.ru/2022-Q1 + drom premium SUV + autostat"),
    ("Kia", "Rio", 2020, 850_000, 1_250_000,
     "https://www.kia.ru/cars/rio/",
     "kia.ru/2020-Q1 + archive auto.ru + drom"),
    ("Kia", "Rio", 2022, 1_350_000, 1_750_000,
     "https://web.archive.org/web/2022*/kia.ru/rio",
     "kia.ru/2022-Q1 (pre-exit) + drom 2022"),
    ("Kia", "Sportage", 2022, 2_700_000, 3_800_000,
     "https://web.archive.org/web/2022*/kia.ru/sportage",
     "kia.ru/2022-Q1 + drom catalog"),
    ("Kia", "K5", 2022, 2_400_000, 3_300_000,
     "https://web.archive.org/web/2022*/kia.ru/k5",
     "kia.ru/2022-Q1 + drom + autostat"),
    ("Kia", "Sorento", 2022, 3_500_000, 4_900_000,
     "https://web.archive.org/web/2022*/kia.ru/sorento",
     "kia.ru/2022-Q1 + drom catalog"),
    ("Kia", "Soul", 2020, 1_150_000, 1_650_000,
     "https://www.kia.ru/cars/soul/",
     "kia.ru/2020-Q1 + archive auto.ru + drom"),
    ("Genesis", "G70", 2022, 3_900_000, 5_200_000,
     "https://www.genesis.com/ru/",
     "genesis.com/2022-Q1 + drom premium"),
    ("Genesis", "GV70", 2022, 4_500_000, 6_500_000,
     "https://www.genesis.com/ru/",
     "genesis.com/2022-Q1 + drom + autostat"),

    # === JAPANESE MASS — Toyota/Honda/Nissan/Mazda ===
    ("Toyota", "Camry", 2020, 1_950_000, 2_950_000,
     "https://web.archive.org/web/2020*/toyota.ru/camry",
     "toyota.ru/2020-Q1 + archive.org + drom catalog (XV70 generation)"),
    ("Toyota", "Camry", 2024, 3_500_000, 5_200_000,
     "https://www.drom.ru/catalog/toyota/camry/",
     "Drom catalog 2024 (post-exit, parallel imports) + autostat"),
    ("Toyota", "RAV4", 2022, 2_500_000, 3_600_000,
     "https://web.archive.org/web/2022*/toyota.ru/rav4",
     "toyota.ru/2022-Q1 (pre-exit) + drom catalog"),
    ("Toyota", "Land Cruiser Prado", 2024, 7_500_000, 11_000_000,
     "https://www.drom.ru/catalog/toyota/land_cruiser_prado/",
     "Drom catalog 2024 (250-series new gen, parallel imports) + autostat 2024"),
    ("Toyota", "Highlander", 2022, 4_300_000, 5_800_000,
     "https://web.archive.org/web/2022*/toyota.ru/highlander",
     "toyota.ru/2022-Q1 + drom + autostat"),
    ("Honda", "CR-V", 2022, 2_700_000, 3_800_000,
     "https://web.archive.org/web/2022*/honda.co.ru/crv",
     "honda.co.ru/2022 + drom catalog"),
    ("Nissan", "Qashqai", 2021, 1_900_000, 2_500_000,
     "https://web.archive.org/web/2021*/nissan.ru/qashqai",
     "nissan.ru/2021-Q4 (new J12 gen launch) + drom catalog"),
    ("Nissan", "X-Trail", 2022, 2_400_000, 3_400_000,
     "https://web.archive.org/web/2022*/nissan.ru/xtrail",
     "nissan.ru/2022-Q1 + drom catalog"),
    ("Mazda", "CX-5", 2022, 2_600_000, 3_700_000,
     "https://web.archive.org/web/2022*/mazda.ru/cx5",
     "mazda.ru/2022-Q1 + drom catalog"),
    ("Mazda", "6", 2022, 2_400_000, 3_300_000,
     "https://web.archive.org/web/2022*/mazda.ru/6",
     "mazda.ru/2022-Q1 + drom + autostat"),
    ("Lexus", "RX", 2024, 6_500_000, 9_500_000,
     "https://www.drom.ru/catalog/lexus/rx/",
     "Drom catalog 2024 (parallel imports) + autostat premium"),
    ("Lexus", "NX", 2024, 5_500_000, 7_800_000,
     "https://www.drom.ru/catalog/lexus/nx/",
     "Drom catalog 2024 + autostat"),
    ("Lexus", "ES", 2022, 4_300_000, 5_900_000,
     "https://web.archive.org/web/2022*/lexus.ru/es",
     "lexus.ru/2022-Q1 + drom + autostat premium"),

    # === VAG (mass premium) — VW/Skoda/Audi ===
    ("Volkswagen", "Polo", 2020, 800_000, 1_300_000,
     "https://web.archive.org/web/2020*/volkswagen.ru/polo",
     "volkswagen.ru/2020-Q1 + archive auto.ru + drom (Polo sedan, RU-build)"),
    ("Volkswagen", "Polo", 2022, 1_550_000, 2_100_000,
     "https://web.archive.org/web/2022*/volkswagen.ru/polo",
     "volkswagen.ru/2022-Q1 + drom 2022 (last year before exit)"),
    ("Volkswagen", "Tiguan", 2024, 4_700_000, 6_500_000,
     "https://www.drom.ru/catalog/volkswagen/tiguan/",
     "Drom catalog 2024 (3rd gen MQB-evo, parallel imports) + autostat"),
    ("Skoda", "Rapid", 2020, 880_000, 1_300_000,
     "https://web.archive.org/web/2020*/skoda-auto.ru/rapid",
     "skoda-auto.ru/2020-Q1 + archive auto.ru + drom"),
    ("Skoda", "Rapid", 2022, 1_500_000, 2_000_000,
     "https://web.archive.org/web/2022*/skoda-auto.ru/rapid",
     "skoda-auto.ru/2022-Q1 + drom 2022"),
    ("Skoda", "Octavia", 2020, 1_400_000, 2_100_000,
     "https://web.archive.org/web/2020*/skoda-auto.ru/octavia",
     "skoda-auto.ru/2020-Q1 + archive + drom"),
    ("Skoda", "Karoq", 2022, 2_200_000, 3_100_000,
     "https://web.archive.org/web/2022*/skoda-auto.ru/karoq",
     "skoda-auto.ru/2022-Q1 + drom catalog"),
    ("Audi", "A4", 2022, 4_000_000, 5_700_000,
     "https://web.archive.org/web/2022*/audi.ru/a4",
     "audi.ru/2022-Q1 + drom premium catalog"),
    ("Audi", "A6", 2022, 5_200_000, 7_500_000,
     "https://web.archive.org/web/2022*/audi.ru/a6",
     "audi.ru/2022-Q1 + drom"),
    ("Audi", "Q5", 2022, 4_500_000, 6_500_000,
     "https://web.archive.org/web/2022*/audi.ru/q5",
     "audi.ru/2022-Q1 + drom"),
    ("Audi", "Q7", 2022, 6_500_000, 9_500_000,
     "https://web.archive.org/web/2022*/audi.ru/q7",
     "audi.ru/2022-Q1 + drom premium SUV"),

    # === BMW ===
    ("BMW", "3 Series", 2022, 4_200_000, 6_800_000,
     "https://web.archive.org/web/2022*/bmw.ru/3-series",
     "bmw.ru/2022-Q1 + drom premium catalog (G20)"),
    ("BMW", "5 Series", 2024, 8_500_000, 13_000_000,
     "https://www.drom.ru/catalog/bmw/5-series/",
     "Drom catalog 2024 (G60 new gen, parallel imports) + autostat 2024"),
    ("BMW", "X3", 2024, 7_200_000, 10_500_000,
     "https://www.drom.ru/catalog/bmw/x3/",
     "Drom catalog 2024 (G45 new gen, parallel imports) + autostat 2024"),
    ("BMW", "X5", 2022, 7_500_000, 12_000_000,
     "https://web.archive.org/web/2022*/bmw.ru/x5",
     "bmw.ru/2022-Q1 + drom premium SUV (G05)"),
    ("BMW", "X7", 2022, 10_500_000, 16_000_000,
     "https://web.archive.org/web/2022*/bmw.ru/x7",
     "bmw.ru/2022-Q1 + drom"),

    # === MERCEDES ===
    ("Mercedes-Benz", "C-Class", 2022, 4_500_000, 7_000_000,
     "https://web.archive.org/web/2022*/mercedes-benz.ru/cclass",
     "mercedes-benz.ru/2022-Q1 + drom catalog (W206)"),
    ("Mercedes-Benz", "E-Class", 2024, 9_500_000, 14_000_000,
     "https://www.drom.ru/catalog/mercedes-benz/e_class/",
     "Drom catalog 2024 (W214 new gen, parallel imports) + autostat 2024"),
    ("Mercedes-Benz", "GLC", 2022, 5_500_000, 8_500_000,
     "https://web.archive.org/web/2022*/mercedes-benz.ru/glc",
     "mercedes-benz.ru/2022-Q1 + drom"),
    ("Mercedes-Benz", "GLE", 2022, 7_500_000, 11_500_000,
     "https://web.archive.org/web/2022*/mercedes-benz.ru/gle",
     "mercedes-benz.ru/2022-Q1 + drom premium SUV"),
    ("Mercedes-Benz", "S-Class", 2022, 11_500_000, 18_000_000,
     "https://web.archive.org/web/2022*/mercedes-benz.ru/sclass",
     "mercedes-benz.ru/2022-Q1 + drom"),

    # === CHINESE BRANDS ===
    ("Geely", "Coolray", 2022, 1_750_000, 2_350_000,
     "https://www.geely-motors.com/ru/coolray/",
     "geely-motors.com/2022 + drom catalog + autostat"),
    ("Geely", "Coolray", 2024, 2_300_000, 2_950_000,
     "https://www.geely-motors.com/ru/coolray/",
     "geely-motors.com/2024-Q1 + drom + autostat 2024 sales rank"),
    ("Geely", "Atlas", 2024, 2_950_000, 3_950_000,
     "https://www.geely-motors.com/ru/atlas/",
     "geely-motors.com/2024-Q1 (Atlas Pro / 2nd gen) + drom + autostat"),
    ("Geely", "Monjaro", 2024, 3_650_000, 4_450_000,
     "https://www.geely-motors.com/ru/monjaro/",
     "geely-motors.com/2024-Q1 + drom + autostat (top crossover for Geely RU)"),
    ("Geely", "Tugella", 2024, 3_750_000, 4_650_000,
     "https://www.geely-motors.com/ru/tugella/",
     "geely-motors.com/2024-Q1 + drom"),
    ("Chery", "Tiggo 7 Pro", 2024, 2_350_000, 3_050_000,
     "https://chery.ru/tiggo7pro/",
     "chery.ru/2024-Q1 + drom + autostat"),
    ("Chery", "Tiggo 8 Pro", 2024, 3_200_000, 4_000_000,
     "https://chery.ru/tiggo8pro/",
     "chery.ru/2024-Q1 + drom + autostat"),
    ("Chery", "Tiggo 4 Pro", 2024, 1_750_000, 2_300_000,
     "https://chery.ru/tiggo4pro/",
     "chery.ru/2024-Q1 + drom"),
    ("Haval", "Jolion", 2024, 1_850_000, 2_550_000,
     "https://www.haval.ru/jolion/",
     "haval.ru/2024-Q1 + drom + autostat"),
    ("Haval", "F7", 2022, 2_100_000, 2_950_000,
     "https://www.haval.ru/f7/",
     "haval.ru/2022-Q1 + drom"),
    ("Haval", "Dargo", 2024, 2_750_000, 3_650_000,
     "https://www.haval.ru/dargo/",
     "haval.ru/2024-Q1 + drom + autostat"),
    ("Haval", "H9", 2024, 4_100_000, 5_350_000,
     "https://www.haval.ru/h9/",
     "haval.ru/2024-Q1 + drom (premium SUV from Haval)"),
    ("Changan", "CS35 Plus", 2024, 1_950_000, 2_550_000,
     "https://changan-auto.ru/cs35plus/",
     "changan-auto.ru/2024-Q1 + drom"),
    ("Changan", "CS55 Plus", 2024, 2_400_000, 3_100_000,
     "https://changan-auto.ru/cs55plus/",
     "changan-auto.ru/2024-Q1 + drom + autostat"),
    ("Changan", "CS75 Plus", 2024, 2_950_000, 3_850_000,
     "https://changan-auto.ru/cs75plus/",
     "changan-auto.ru/2024-Q1 + drom"),
    ("Changan", "UNI-K", 2024, 3_950_000, 4_750_000,
     "https://changan-auto.ru/uni-k/",
     "changan-auto.ru/2024-Q1 + drom premium Chinese"),
    ("BAIC", "X35", 2024, 1_650_000, 2_150_000,
     "https://baic.ru/x35/",
     "baic.ru/2024-Q1 + drom"),
    ("BAIC", "X55", 2024, 2_450_000, 3_100_000,
     "https://baic.ru/x55/",
     "baic.ru/2024-Q1 + drom"),
    ("BYD", "Han", 2024, 5_950_000, 7_500_000,
     "https://www.byd.com/ru/han/",
     "byd.com/ru/2024-Q1 + drom EV catalog (electric flagship)"),
    ("BYD", "Song Plus", 2024, 3_150_000, 4_050_000,
     "https://www.byd.com/ru/songplus/",
     "byd.com/ru/2024-Q1 + drom (DM-i hybrid SUV)"),

    # === FRENCH/EUROPEAN MASS ===
    ("Renault", "Logan", 2020, 720_000, 1_080_000,
     "https://web.archive.org/web/2020*/renault.ru/logan",
     "renault.ru/2020-Q1 + archive auto.ru + drom"),
    ("Renault", "Duster", 2021, 1_300_000, 1_800_000,
     "https://web.archive.org/web/2021*/renault.ru/duster",
     "renault.ru/2021-Q4 (new 2nd gen launch) + drom catalog"),
    ("Renault", "Sandero", 2020, 690_000, 980_000,
     "https://web.archive.org/web/2020*/renault.ru/sandero",
     "renault.ru/2020-Q1 + archive + drom"),

    # === EV (modern Russian/Chinese examples) ===
    ("Moskvich", "3", 2024, 2_350_000, 3_100_000,
     "https://moskvich-auto.ru/3/",
     "moskvich-auto.ru/2024-Q1 (rebadged JAC JS4) + drom + autostat"),
    ("Moskvich", "3e", 2024, 3_500_000, 4_300_000,
     "https://moskvich-auto.ru/3e/",
     "moskvich-auto.ru/2024-Q1 (electric variant) + drom"),

    # === PORSCHE / FERRARI / EXOTIC PREMIUM (small samples for tail) ===
    ("Porsche", "Cayenne", 2022, 8_500_000, 14_500_000,
     "https://web.archive.org/web/2022*/porsche.com/russia/cayenne",
     "porsche.com/russia/2022-Q1 + drom premium SUV"),
    ("Porsche", "Macan", 2022, 6_500_000, 10_000_000,
     "https://web.archive.org/web/2022*/porsche.com/russia/macan",
     "porsche.com/russia/2022-Q1 + drom"),
    ("Land Rover", "Discovery", 2022, 7_500_000, 11_500_000,
     "https://web.archive.org/web/2022*/landrover.ru/discovery",
     "landrover.ru/2022-Q1 + drom premium SUV"),
    ("Land Rover", "Range Rover Sport", 2022, 9_500_000, 14_500_000,
     "https://web.archive.org/web/2022*/landrover.ru/range-rover-sport",
     "landrover.ru/2022-Q1 + drom"),
    ("Volvo", "XC60", 2022, 4_500_000, 6_700_000,
     "https://web.archive.org/web/2022*/volvocars.ru/xc60",
     "volvocars.ru/2022-Q1 + drom"),
    ("Volvo", "XC90", 2022, 6_500_000, 9_500_000,
     "https://web.archive.org/web/2022*/volvocars.ru/xc90",
     "volvocars.ru/2022-Q1 + drom premium 7-seat SUV"),
]


def fail(msg: str) -> None:
    print(f"  FAIL  {msg}")
    sys.exit(1)


def ok(msg: str) -> None:
    print(f"  OK    {msg}")


def main() -> None:
    print("=" * 70)
    print("car_msrp_seed.csv — BUILD")
    print("=" * 70)

    makes = pd.read_csv(SEED / "car_makes.csv").rename(columns={"id": "make_id"})
    models = pd.read_csv(SEED / "car_models.csv").rename(columns={"id": "model_id"})
    gens = pd.read_csv(SEED / "car_generations.csv").rename(columns={"id": "generation_id"})

    print(f"  loaded: {len(makes)} makes, {len(models)} models, {len(gens)} gens")
    print(f"  ANCHORS: {len(ANCHORS)} hand-curated entries")

    catalog = (
        gens.merge(models[["model_id", "make_id", "name"]].rename(columns={"name": "model_name"}),
                   on="model_id", how="left")
        .merge(makes[["make_id", "name"]].rename(columns={"name": "make_name"}),
               on="make_id", how="left")
    )

    rows = []
    misses = []
    for make_name, model_name, year_anchor, base, high, url, note in ANCHORS:
        cand = catalog[
            (catalog["make_name"] == make_name)
            & (catalog["model_name"] == model_name)
        ]
        if len(cand) == 0:
            misses.append((make_name, model_name, year_anchor, "no model in catalog"))
            continue

        cand_year = cand[
            (cand["year_from"] <= year_anchor)
            & ((cand["year_to"].isna()) | (cand["year_to"] >= year_anchor))
        ]
        if len(cand_year) == 0:
            cand_sorted = cand.sort_values("year_from", ascending=False)
            picked = cand_sorted.iloc[0]
            note_extra = f" [auto-pick: latest gen year_from={int(picked['year_from'])}]"
            generation_id = int(picked["generation_id"])
        elif len(cand_year) > 1:
            cand_sorted = cand_year.sort_values("year_from", ascending=False)
            picked = cand_sorted.iloc[0]
            note_extra = f" [auto-pick: latest of {len(cand_year)} gens]"
            generation_id = int(picked["generation_id"])
        else:
            generation_id = int(cand_year.iloc[0]["generation_id"])
            note_extra = ""

        if base > high:
            fail(f"msrp_base > trim_high for {make_name} {model_name} {year_anchor}: {base} > {high}")

        rows.append({
            "generation_id": generation_id,
            "year": year_anchor,
            "msrp_base_rub": base,
            "trim_high_rub": high,
            "source_url": url,
            "source_note": note + note_extra,
        })

    if misses:
        print()
        print("  WARN  unresolved anchors:")
        for m in misses:
            print(f"        {m}")
        if len(misses) > len(ANCHORS) * 0.10:
            fail(f"too many misses ({len(misses)} > 10% of {len(ANCHORS)})")

    out = pd.DataFrame(rows).sort_values(["generation_id", "year"]).reset_index(drop=True)
    out_path = SEED / "car_msrp_seed.csv"
    out.to_csv(out_path, index=False)

    ok(f"wrote {out_path} with {len(out)} rows ({len(misses)} unresolved)")
    print()
    print("  Stats:")
    print(f"    unique generations: {out['generation_id'].nunique()}")
    print(f"    year range:         {out['year'].min()}–{out['year'].max()}")
    print(f"    msrp_base range:    {out['msrp_base_rub'].min():,} – {out['msrp_base_rub'].max():,} RUB")
    print(f"    trim_high range:    {out['trim_high_rub'].min():,} – {out['trim_high_rub'].max():,} RUB")
    avg_premium = (out['trim_high_rub'] / out['msrp_base_rub']).mean()
    print(f"    avg trim premium:   x{avg_premium:.2f}  (high vs base)")
    print()
    print("=" * 70)
    print("OK  car_msrp_seed.csv built")
    print("=" * 70)


if __name__ == "__main__":
    main()
