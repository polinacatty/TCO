"""Build ``luxury_car_list.csv`` from a plaintext snapshot of the official Minpromtorgs list.

Snapshot source (2026 edition): mirror text as published on ГАРАНТ hotlaw 2037378
(file ``ml/data/raw/minpromtorg_luxury_10m_2026_garant_snapshot.txt``).
Replace that file from https://www.garant.ru/hotlaw/federal/2037378/ or from the
XLS/PDF on minpromtorg.gov.ru (Перечни и реестры), then re-run::

    python ml/pipelines/_luxury_list_build.py

Источники и ссылки на перечень — в ``docs/03_data_collection/02_data_dictionary.md`` §5
(в CSV не дублируются). Колонка возраста из перечня в seed не попадает — окно 10/20 лет
по НК РФ задаётся в расчёте TCO (см. ``03_tco_calculation_methodology.md`` §2.3).
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RAW = REPO / "ml" / "data" / "raw" / "minpromtorg_luxury_10m_2026_garant_snapshot.txt"
OUT = REPO / "ml" / "data" / "seed" / "luxury_car_list.csv"

ROW_RE = re.compile(
    r"^\|\s*(\d+)\s*\|"  # №
    r"\s*([^|]*)\|"  # Марка
    r"\s*([^|]*)\|"  # Модель
    r"\s*([^|]*)\|"  # Тип двигателя
    r"\s*([^|]*)\|"  # Объём
    r"\s*([^|]*)"
    r"\|?\s*$"
)


def _cc_to_litres(cc: str) -> str:
    cc = cc.strip().replace(",", ".")
    if cc in {"", "-", "—", "любой"} or "/" in cc:
        return ""
    try:
        v = int(float(cc))
    except ValueError:
        return ""
    return f"{v / 1000:.1f}"


def parse_snapshot(path: Path) -> list[dict[str, str]]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    tier = ""
    rows: list[dict[str, str]] = []
    pending: dict[str, str] | None = None

    def flush():
        nonlocal pending
        if pending is not None:
            rows.append(pending)
            pending = None

    for line in lines:
        if "10 миллионов до 15" in line and "миллионов рублей" in line:
            tier = "10"
            continue
        if "от 15 миллионов рублей" in line and "не более 20" in line:
            tier = "15"
            continue

        if not line.startswith("|"):
            continue
        if "+---" in line or "+===" in line:
            continue

        m = ROW_RE.match(line)
        if m:
            flush()
            make, model, eng_t, vol_cc, _age = (
                m.group(2).strip(),
                m.group(3).strip(),
                m.group(4).strip(),
                m.group(5).strip(),
                m.group(6).strip(),
            )
            if not make and not model:
                continue
            min_price = "10000000" if tier == "10" else "15000000"
            vol_cc_n = vol_cc if vol_cc not in {"-", "—"} else ""
            pending = {
                "make": make,
                "model": model,
                "engine_type": eng_t,
                "engine_volume_l": _cc_to_litres(vol_cc_n),
                "price_tier_min_rub": min_price,
            }
            continue

        if not re.match(r"^\|\s+\|\s+", line):
            continue

        parts = [p.strip() for p in line.strip().strip("|").split("|")]
        if pending is None:
            continue
        if len(parts) >= 3 and parts[2].strip():
            pending["model"] = (pending["model"] + " " + parts[2].strip()).strip()

    flush()
    return rows


def main() -> None:
    recs = parse_snapshot(RAW)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "make",
        "model",
        "engine_type",
        "engine_volume_l",
        "price_tier_min_rub",
    ]
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in recs:
            w.writerow({k: r[k] for k in fields})
    print(f"Wrote {len(recs)} rows to {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
