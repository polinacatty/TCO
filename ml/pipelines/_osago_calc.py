"""Reference implementation of the OSAGO premium formula.

Sprint 1, step 1.3.4.  This module is the first piece of executable
"product code" in the repo: it loads the seven seed CSVs produced in
step 1.3.2 and computes the OSAGO premium for an arbitrary policy
profile, exactly as Annex 4 of Bank of Russia Directive 7204-У
prescribes.  Once the backend service is built (sprint 2+), this
function will be lifted out of ``ml/pipelines`` into the backend.

Formula for ordinary vehicles (categories B/BE and similar) — used
by every realistic profile our diploma sample covers:

    P = TB · KT · KBM · KVS · KO · KM · KS

Special rules from Annex 4 implemented here:

* If the policy is unrestricted (``restricted=False``), KVS does **not**
  apply (treated as 1.0 — "не применяется") — Annex 4 § 10.
* If there are several allowed drivers, the **maximum** KVS across them
  is used — Annex 4 § 11.
* If the owner is a legal entity, KVS is multiplied by **1.8** —
  Annex 2 § 5.3.

What is **not** implemented in this MVP:

* Foreign vehicles temporarily used in RF (uses KP instead of KS / KT).
* Short-term policies (3 mo – 1 yr) — Annex 4 § 13.
* Mid-term recalculation upon profile change — Annex 4 § 15.

Run::

    python ml\\pipelines\\_osago_calc.py            # prints all 3 canonical profiles
    python ml\\pipelines\\_osago_calc.py --profile A
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
SEED_DIR = REPO_ROOT / "ml" / "data" / "seed"


# ----------------------------------------------------------------------------
# Profile data structures
# ----------------------------------------------------------------------------


@dataclass
class Driver:
    """One person allowed to drive the vehicle under the policy."""

    age: int
    experience_years: float


@dataclass
class Profile:
    """Everything we need to compute the premium for one policy."""

    region_id: int
    power_hp: int
    drivers: list[Driver]
    kbm_class: str  # "M", "0", "1", ..., "13"
    restricted: bool = True
    period_months: int = 12
    vehicle_family: str = "B_BE"  # "B_BE" | "A_M_A1_B1"
    owner_type: str = "physical"  # "physical" | "legal"
    tb_strategy: str = "mid"  # "min" | "max" | "mid"
    label: str = ""  # human-friendly name for logs


@dataclass
class Breakdown:
    """Per-coefficient breakdown of a single premium calculation."""

    profile: Profile
    tb_min: float = 0.0
    tb_max: float = 0.0
    tb: float = 0.0
    kt: float = 0.0
    kbm: float = 0.0
    kvs: float = 0.0
    ko: float = 0.0
    km: float = 0.0
    ks: float = 0.0
    premium_min: float = 0.0
    premium_max: float = 0.0
    premium: float = 0.0
    notes: list[str] = field(default_factory=list)


# ----------------------------------------------------------------------------
# Calculator
# ----------------------------------------------------------------------------


class OsagoCalculator:
    """Loads the seven seed CSVs and computes OSAGO premium per Annex 4."""

    def __init__(self, seed_dir: Path = SEED_DIR) -> None:
        self.seed_dir = seed_dir
        self.tariffs = pd.read_csv(seed_dir / "osago_base_tariffs.csv", dtype={"category_id": str})
        self.kbm = pd.read_csv(seed_dir / "osago_kbm.csv", dtype={"kbm_class": str})
        self.power = pd.read_csv(seed_dir / "osago_power.csv")
        self.drivers = pd.read_csv(seed_dir / "osago_drivers.csv", dtype={"restricted": str})
        self.seasonal = pd.read_csv(seed_dir / "osago_seasonal.csv")
        self.age_exp = pd.read_csv(seed_dir / "osago_age_exp.csv")
        self.territory = pd.read_csv(seed_dir / "osago_territory_coefs.csv")

    # --- per-coefficient lookups -------------------------------------------

    def _tb_row(self, vehicle_family: str, owner_type: str) -> pd.Series:
        if vehicle_family == "A_M_A1_B1":
            return self.tariffs[self.tariffs["category_id"] == "1"].iloc[0]
        if vehicle_family != "B_BE":
            raise ValueError(f"unsupported vehicle_family={vehicle_family}")
        cat = "2.1" if owner_type == "legal" else "2.2"
        return self.tariffs[self.tariffs["category_id"] == cat].iloc[0]

    def _tb(self, vehicle_family: str, owner_type: str, strategy: str) -> tuple[float, float, float]:
        row = self._tb_row(vehicle_family, owner_type)
        tb_min = float(row["tb_min_rub"])
        tb_max = float(row["tb_max_rub"])
        if strategy == "min":
            tb = tb_min
        elif strategy == "max":
            tb = tb_max
        elif strategy == "mid":
            tb = (tb_min + tb_max) / 2
        else:
            raise ValueError(f"unknown tb_strategy={strategy}")
        return tb_min, tb_max, tb

    def _kt(self, region_id: int) -> float:
        rows = self.territory[self.territory["region_id"] == region_id]
        if rows.empty:
            raise ValueError(f"unknown region_id={region_id}")
        return float(rows.iloc[0]["kt_general"])

    def _kbm(self, kbm_class: str) -> float:
        rows = self.kbm[self.kbm["kbm_class"] == kbm_class]
        if rows.empty:
            raise ValueError(f"unknown kbm_class={kbm_class}")
        return float(rows.iloc[0]["kbm_value"])

    def _kvs_one(self, vehicle_family: str, age: int, experience_years: float) -> float:
        family = "B_BE_other" if vehicle_family == "B_BE" else vehicle_family
        sub = self.age_exp[self.age_exp["vehicle_family"] == family]
        sub = sub[(sub["age_min_incl"] <= age) & (sub["age_max_incl"] >= age)]
        sub = sub[(sub["exp_min_years_incl"] <= experience_years) & (sub["exp_max_years_excl"] > experience_years)]
        if sub.empty:
            raise ValueError(
                f"no KVS row for vehicle_family={vehicle_family}, age={age}, "
                f"experience_years={experience_years} (impossible age × experience combo)"
            )
        return float(sub.iloc[0]["kvs_value"])

    def _kvs(self, profile: Profile) -> tuple[float, list[str]]:
        notes: list[str] = []
        if not profile.restricted:
            notes.append("KVS не применяется (полис без ограничения списка водителей) — Annex 4 § 10")
            return 1.0, notes
        per_driver = [self._kvs_one(profile.vehicle_family, d.age, d.experience_years) for d in profile.drivers]
        kvs = max(per_driver)
        if len(per_driver) > 1:
            notes.append(f"KVS = max({per_driver}) = {kvs} (несколько водителей, Annex 4 § 11)")
        if profile.owner_type == "legal":
            kvs *= 1.8
            notes.append("KVS × 1.8 (юр. лицо) — Annex 2 § 5.3")
        return kvs, notes

    def _ko(self, restricted: bool, owner_type: str) -> float:
        rows = self.drivers[
            (self.drivers["restricted"] == ("true" if restricted else "false"))
            & (self.drivers["owner_type"] == owner_type)
        ]
        if rows.empty:
            raise ValueError(f"no KO row for restricted={restricted}, owner_type={owner_type}")
        return float(rows.iloc[0]["ko_value"])

    def _km(self, vehicle_family: str, power_hp: int) -> float:
        sub = self.power[self.power["vehicle_family"] == vehicle_family]
        sub = sub[(sub["power_min_hp_excl"] < power_hp) & (sub["power_max_hp_incl"] >= power_hp)]
        if sub.empty:
            raise ValueError(f"no KM row for vehicle_family={vehicle_family}, power_hp={power_hp}")
        return float(sub.iloc[0]["km_value"])

    def _ks(self, period_months: int) -> float:
        sub = self.seasonal
        sub = sub[(sub["period_min_months_excl"] < period_months) & (sub["period_max_months_incl"] >= period_months)]
        if sub.empty:
            raise ValueError(f"no KS row for period_months={period_months}")
        return float(sub.iloc[0]["ks_value"])

    # --- top-level ---------------------------------------------------------

    def compute(self, profile: Profile) -> Breakdown:
        b = Breakdown(profile=profile)
        b.tb_min, b.tb_max, b.tb = self._tb(profile.vehicle_family, profile.owner_type, profile.tb_strategy)
        b.kt = self._kt(profile.region_id)
        b.kbm = self._kbm(profile.kbm_class)
        b.kvs, kvs_notes = self._kvs(profile)
        b.notes.extend(kvs_notes)
        b.ko = self._ko(profile.restricted, profile.owner_type)
        b.km = self._km(profile.vehicle_family, profile.power_hp)
        b.ks = self._ks(profile.period_months)

        multiplier = b.kt * b.kbm * b.kvs * b.ko * b.km * b.ks
        b.premium = b.tb * multiplier
        b.premium_min = b.tb_min * multiplier
        b.premium_max = b.tb_max * multiplier
        return b


# ----------------------------------------------------------------------------
# Canonical profiles for cross-verification with the RSA calculator
# ----------------------------------------------------------------------------


CANONICAL_PROFILES: dict[str, Profile] = {
    "A": Profile(
        label="A — Молодой водитель в Москве, недорогая машина (Lada Granta)",
        region_id=1,             # Москва
        power_hp=87,             # Lada Granta 1.6 — 87 л.с.
        drivers=[Driver(age=24, experience_years=4)],
        kbm_class="4",           # новичок без аварий, 3 года стажа без выплат
        restricted=True,
    ),
    "B": Profile(
        label="B — Опытный водитель в СПб, средний авто (Toyota Camry 2.5)",
        region_id=19,            # СПб
        power_hp=181,            # Camry 2.5 — 181 л.с.
        drivers=[Driver(age=35, experience_years=10)],
        kbm_class="13",          # 13 лет без аварий — глубокая скидка
        restricted=True,
    ),
    "C": Profile(
        label="C — Пенсионер в Уфе (Башкортостан), Hyundai Solaris",
        region_id=45,            # Республика Башкортостан, столица Уфа
        power_hp=107,            # Solaris 1.6 — 107 л.с.
        drivers=[Driver(age=65, experience_years=30)],
        kbm_class="13",
        restricted=True,
    ),
}


# ----------------------------------------------------------------------------
# Pretty printer
# ----------------------------------------------------------------------------


def _print_breakdown(b: Breakdown) -> None:
    p = b.profile
    print(f"\n{'=' * 78}")
    print(p.label)
    print("-" * 78)
    print(f"  Регион     : id={p.region_id}  ({_region_name(p.region_id)})")
    print(f"  ТС         : {p.vehicle_family}, {p.power_hp} л.с., owner={p.owner_type}")
    print(f"  Водители   : {[(d.age, d.experience_years) for d in p.drivers]}")
    print(f"  Полис      : restricted={p.restricted}, период={p.period_months} мес, КБМ-класс={p.kbm_class}")
    print(f"  ТБ-страт.  : {p.tb_strategy}  (коридор [{b.tb_min:.0f}; {b.tb_max:.0f}] ₽)")
    print()
    print(f"  TB  = {b.tb:>7.2f} ₽")
    print(f"  KT  = {b.kt:>7.2f}")
    print(f"  KBM = {b.kbm:>7.2f}")
    print(f"  KVS = {b.kvs:>7.2f}")
    print(f"  KO  = {b.ko:>7.2f}")
    print(f"  KM  = {b.km:>7.2f}")
    print(f"  KS  = {b.ks:>7.2f}")
    multiplier = b.kt * b.kbm * b.kvs * b.ko * b.km * b.ks
    print(f"  Произведение коэффициентов: {multiplier:.4f}")
    print()
    print(f"  >>> Премия (mid TB)  : {b.premium:>9.2f} ₽")
    print(f"      Премия (min TB)  : {b.premium_min:>9.2f} ₽   ← дешёвый страховщик")
    print(f"      Премия (max TB)  : {b.premium_max:>9.2f} ₽   ← дорогой страховщик")
    if b.notes:
        print()
        print("  Примечания:")
        for n in b.notes:
            print(f"    * {n}")


def _region_name(region_id: int) -> str:
    df = pd.read_csv(SEED_DIR / "regions.csv", dtype={"id": int})
    rows = df[df["id"] == region_id]
    return rows.iloc[0]["name"] if len(rows) else "?"


# ----------------------------------------------------------------------------
# CLI entry point
# ----------------------------------------------------------------------------


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--profile",
        choices=sorted(CANONICAL_PROFILES.keys()),
        help="run only one of the canonical profiles (A, B or C); default is all",
    )
    args = parser.parse_args()

    calc = OsagoCalculator()

    profiles = (
        [CANONICAL_PROFILES[args.profile]]
        if args.profile
        else [CANONICAL_PROFILES[k] for k in sorted(CANONICAL_PROFILES)]
    )

    for p in profiles:
        b = calc.compute(p)
        _print_breakdown(b)

    print("\n" + "=" * 78)
    print(
        "Кросс-проверка с «внешним» калькулятором: на autoins.ru нет одного «единого» URL,"
    )
    print(
        "есть страница с таблицей ссылок на онлайн-калькуляторы страховщиков — членов РСА:"
    )
    print("  https://autoins.ru/osago/raschet-stoimosti-osago/kalkulyator/")
    print(
        "Открой любую СК из таблицы, введи те же параметры и сравни диапазон премии "
        "с нашим [premium_min; premium_max]."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
