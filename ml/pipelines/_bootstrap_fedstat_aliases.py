"""Generate seed alias files mapping our region/fuel ids to fedstat codes.

This script runs **once** during sprint 1 to materialise:

* ``ml/data/seed/fedstat_region_aliases.csv`` — for each of our 85
  subjects of the Russian Federation, the fedstat-side identifiers we
  need to (a) request data from fedstat, and (b) attach data we received
  back to our internal ``region_id``.
* ``ml/data/seed/fedstat_fuel_aliases.csv`` — same, but for the 4
  fuel types we care about (АИ-92, АИ-95, АИ-98+, ДТ).

Why a separate bootstrap step?  The high-level ingest script
(``ingest_fuel_prices.py``) needs **stable** mappings.  If we re-derived
them on every run, the ETL would silently break the day fedstat changes
a name; with seed CSVs in the repo, schema drift is caught by code
review.

How the mapping is derived
--------------------------

1. ``GET /indicator/31448`` → :class:`IndicatorMeta` with all FGrid
   filter values (448 territories, 885 goods, etc.).
2. ``POST /indicator/data.do?format=sdmx`` requesting **all**
   territories × four fuels × January 2024 — single small payload that
   carries the full ``<CodeLists>`` block describing every OKATO /
   grtov code with its canonical Rosstat name.
3. Match names between FGrid (UI side) and CodeList (SDMX side) — they
   usually agree byte-for-byte.
4. Match again from FGrid name to our short ``regions.csv`` names via
   a small set of substring rules (one rule per region; we keep them
   explicit to make any mismatch obvious).
5. Emit two CSV files; print a summary report so the human can confirm
   nothing is missing.

Run::

    python ml\\pipelines\\_bootstrap_fedstat_aliases.py
"""

from __future__ import annotations

import csv
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from _fedstat_client import (  # type: ignore[import-not-found]
    FedstatClient,
    IndicatorMeta,
    parse_sdmx_codelists,
    parse_sdmx_to_df,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
SEED_DIR = REPO_ROOT / "ml" / "data" / "seed"
RAW_DIR = REPO_ROOT / "ml" / "data" / "raw" / "fedstat"

INDICATOR_ID = "31448"
FUEL_QUERY = {
    "AI92":   "марки АИ-92",
    "AI95":   "марки АИ-95",
    "AI98":   "марки АИ-98",
    "DIESEL": "Дизельное топливо",
}

# Each region from regions.csv has ONE substring that should appear in
# the fedstat-canonical name.  Keeping this table explicit (rather than
# auto-deriving from regions.name) means a typo or naming change is
# caught at review time.  Tokens are case-sensitive Russian.
REGION_MATCH_TOKENS: dict[str, str] = {
    "Москва":                                  "Город Москва столица",
    "Московская область":                      "Московская область",
    "Белгородская область":                    "Белгородская область",
    "Брянская область":                        "Брянская область",
    "Владимирская область":                    "Владимирская область",
    "Воронежская область":                     "Воронежская область",
    "Ивановская область":                      "Ивановская область",
    "Калужская область":                       "Калужская область",
    "Костромская область":                     "Костромская область",
    "Курская область":                         "Курская область",
    "Липецкая область":                        "Липецкая область",
    "Орловская область":                       "Орловская область",
    "Рязанская область":                       "Рязанская область",
    "Смоленская область":                      "Смоленская область",
    "Тамбовская область":                      "Тамбовская область",
    "Тверская область":                        "Тверская область",
    "Тульская область":                        "Тульская область",
    "Ярославская область":                     "Ярославская область",
    "Санкт-Петербург":                         "Город Санкт-Петербург",
    "Ленинградская область":                   "Ленинградская область",
    "Архангельская область":                   "Архангельская область",
    "Вологодская область":                     "Вологодская область",
    "Калининградская область":                 "Калининградская область",
    "Республика Карелия":                      "Республика Карелия",
    "Республика Коми":                         "Республика Коми",
    "Мурманская область":                      "Мурманская область",
    "Ненецкий АО":                             "Ненецкий автономный округ",
    "Новгородская область":                    "Новгородская область",
    "Псковская область":                       "Псковская область",
    "Республика Адыгея":                       "Республика Адыгея",
    "Республика Калмыкия":                     "Республика Калмыкия",
    "Республика Крым":                         "Республика Крым",
    "Краснодарский край":                      "Краснодарский край",
    "Астраханская область":                    "Астраханская область",
    "Волгоградская область":                   "Волгоградская область",
    "Ростовская область":                      "Ростовская область",
    "Севастополь":                             "значения Севастополь",
    "Республика Дагестан":                     "Республика Дагестан",
    "Республика Ингушетия":                    "Республика Ингушетия",
    "Кабардино-Балкарская Республика":         "Кабардино-Балкарская",
    "Карачаево-Черкесская Республика":         "Карачаево-Черкесская",
    "Республика Северная Осетия — Алания":     "Северная Осетия",
    "Чеченская Республика":                    "Чеченская Республика",
    "Ставропольский край":                     "Ставропольский край",
    "Республика Башкортостан":                 "Республика Башкортостан",
    "Республика Марий Эл":                     "Республика Марий Эл",
    "Республика Мордовия":                     "Республика Мордовия",
    "Республика Татарстан":                    "Республика Татарстан",
    "Удмуртская Республика":                   "Удмуртская Республика",
    "Чувашская Республика":                    "Чувашская Республика",
    "Кировская область":                       "Кировская область",
    "Нижегородская область":                   "Нижегородская область",
    "Оренбургская область":                    "Оренбургская область",
    "Пензенская область":                      "Пензенская область",
    "Пермский край":                           "Пермский край",
    "Самарская область":                       "Самарская область",
    "Саратовская область":                     "Саратовская область",
    "Ульяновская область":                     "Ульяновская область",
    "Курганская область":                      "Курганская область",
    "Свердловская область":                    "Свердловская область",
    "Тюменская область":                       "Тюменская область",
    "Ханты-Мансийский АО — Югра":              "Ханты-Мансийский автономный округ",
    "Челябинская область":                     "Челябинская область",
    "Ямало-Ненецкий АО":                       "Ямало-Ненецкий автономный округ",
    "Республика Алтай":                        "Республика Алтай",
    "Алтайский край":                          "Алтайский край",
    "Иркутская область":                       "Иркутская область",
    "Кемеровская область — Кузбасс":           "Кемеровская область",
    "Красноярский край":                       "Красноярский край",
    "Новосибирская область":                   "Новосибирская область",
    "Омская область":                          "Омская область",
    "Томская область":                         "Томская область",
    "Республика Тыва":                         "Республика Тыва",
    "Республика Хакасия":                      "Республика Хакасия",
    "Республика Бурятия":                      "Республика Бурятия",
    "Республика Саха (Якутия)":                "Республика Саха",
    "Забайкальский край":                      "Забайкальский край",
    "Камчатский край":                         "Камчатский край",
    "Приморский край":                         "Приморский край",
    "Хабаровский край":                        "Хабаровский край",
    "Амурская область":                        "Амурская область",
    "Магаданская область":                     "Магаданская область",
    "Сахалинская область":                     "Сахалинская область",
    "Еврейская АО":                            "Еврейская автономная область",
    "Чукотский АО":                            "Чукотский автономный округ",
}


@dataclass(frozen=True)
class RegionAlias:
    region_id: int
    region_name: str
    fgrid_value_id: str
    okato_code: str
    fedstat_name_fgrid: str
    fedstat_name_codelist: str


@dataclass(frozen=True)
class FuelAlias:
    fuel_label: str
    fgrid_value_id: str
    grtov_code: str
    fedstat_name_fgrid: str
    fedstat_name_codelist: str


def _read_regions_csv() -> list[dict[str, str]]:
    path = SEED_DIR / "regions.csv"
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _resolve_fuel_fgrid_ids(meta: IndicatorMeta) -> dict[str, tuple[str, str]]:
    """For each fuel label we want, find a single FGrid value_id + name.

    Returns ``{label: (fgrid_value_id, fgrid_name)}``.
    """
    goods = meta.fields["58273"]
    out: dict[str, tuple[str, str]] = {}
    for label, query in FUEL_QUERY.items():
        ids = goods.find_value_ids(query)
        if not ids:
            raise RuntimeError(f"no fedstat goods entry matches {query!r}")
        # Some queries (e.g. "марки АИ-92") match multiple entries; we
        # prefer the *shortest* canonical name as the most specific.
        pairs = [(vid, goods.values[vid]) for vid in ids]
        pairs.sort(key=lambda p: len(p[1]))
        vid, name = pairs[0]
        out[label] = (vid, name)
    return out


def _diagnose_missing(rname: str, token: str, name_to_id: dict[str, str]) -> str:
    """Return a debug string with FGrid candidates that *partially* match.

    Used when our REGION_MATCH_TOKENS entry yields zero hits — likely the
    canonical fedstat name differs from what we expected.  We probe with
    progressively shorter prefixes of the expected token to surface any
    near-misses for human inspection.
    """
    probes: list[str] = [token]
    # Last whitespace-delimited word as a fallback probe
    if " " in token:
        last_word = token.rsplit(" ", 1)[-1]
        if last_word and last_word != token:
            probes.append(last_word)
    # First word too (catches "Республика X" style)
    first_word = token.split()[0]
    if first_word and first_word not in probes:
        probes.append(first_word)

    seen: set[str] = set()
    hits: list[str] = []
    for probe in probes:
        for name in name_to_id:
            if probe.lower() in name.lower() and name not in seen:
                seen.add(name)
                hits.append(name)
                if len(hits) >= 10:
                    break
        if len(hits) >= 10:
            break
    if not hits:
        return f"no FGrid name contains any of {probes}"
    return f"closest FGrid candidates: {hits}"


def _match_regions_to_fgrid(
    meta: IndicatorMeta, regions: list[dict[str, str]]
) -> dict[int, tuple[str, str]]:
    """For each row of ``regions.csv``, find ``(fgrid_value_id, fgrid_name)``."""
    territory = meta.fields["57831"]
    name_to_id = {name: vid for vid, name in territory.values.items()}
    result: dict[int, tuple[str, str]] = {}
    missing: list[str] = []
    for row in regions:
        rid = int(row["id"])
        rname = row["name"]
        token = REGION_MATCH_TOKENS.get(rname)
        if token is None:
            missing.append(f"{rname!r}: no token in REGION_MATCH_TOKENS")
            continue
        candidates = [(name, vid) for name, vid in name_to_id.items() if token in name]
        if not candidates:
            diag = _diagnose_missing(rname, token, name_to_id)
            missing.append(f"{rname!r} (token={token!r}): {diag}")
            continue
        # Pick the SHORTEST canonical name — fedstat tends to add things
        # like " (с 01.01.2023)" / "город федерального значения" only on
        # composite "exclusion" entries; the plain subject name is shortest.
        candidates.sort(key=lambda p: len(p[0]))
        fname, fvid = candidates[0]
        result[rid] = (fvid, fname)
    if missing:
        raise RuntimeError("unmapped regions:\n  - " + "\n  - ".join(missing))
    return result


def _request_codelists(client: FedstatClient, meta: IndicatorMeta,
                       region_fgrid_ids: Iterable[str],
                       fuel_fgrid_ids: Iterable[str]) -> bytes:
    """Single small POST that produces a SDMX with full CodeLists."""
    period_jan = meta.fields["33560"].find_value_ids("январ")
    if not period_jan:
        raise RuntimeError("can't find 'январь' in period field 33560")
    filters = {
        "3":     ["2024"],
        "33560": [period_jan[0]],
        "57831": list(region_fgrid_ids),
        "58273": list(fuel_fgrid_ids),
        "30611": "*",
    }
    return client.post_filtered(INDICATOR_ID, meta, filters, fmt="sdmx")


def _match_codelist_to_fgrid(
    fgrid_name_to_vid: dict[str, str],
    codelist: dict[str, str],
) -> dict[str, str]:
    """Map fgrid_value_id → codelist key, by exact name equality.

    fedstat usually emits identical strings on both sides; we fall back
    to a case-insensitive match if the exact one fails.
    """
    fgrid_lc = {name.lower(): vid for name, vid in fgrid_name_to_vid.items()}
    out: dict[str, str] = {}
    for code, name in codelist.items():
        if name in fgrid_name_to_vid:
            out[fgrid_name_to_vid[name]] = code
            continue
        low = name.lower()
        if low in fgrid_lc:
            out[fgrid_lc[low]] = code
    return out


def _write_csv(path: Path, header: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s :: %(message)s",
    )
    log = logging.getLogger("bootstrap")
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    regions = _read_regions_csv()
    log.info("regions.csv: %d rows", len(regions))

    with FedstatClient() as fs:
        log.info("step 1: fetching IndicatorMeta for %s", INDICATOR_ID)
        meta = fs.get_filter_ids(INDICATOR_ID)
        log.info("title=%r, fields=%s", meta.title, sorted(meta.fields))

        log.info("step 2: matching regions.csv to FGrid territories")
        region_match = _match_regions_to_fgrid(meta, regions)
        log.info("matched %d/%d regions", len(region_match), len(regions))

        log.info("step 3: resolving fuel FGrid value_ids")
        fuel_match = _resolve_fuel_fgrid_ids(meta)
        for label, (vid, name) in fuel_match.items():
            log.info("  %s -> %s : %s", label, vid, name)

        log.info("step 4: requesting CodeLists via narrow POST")
        region_fgrid_ids = [vid for vid, _ in region_match.values()]
        fuel_fgrid_ids = [vid for vid, _ in fuel_match.values()]
        raw = _request_codelists(fs, meta, region_fgrid_ids, fuel_fgrid_ids)
        out_xml = RAW_DIR / "_bootstrap_31448.sdmx.xml"
        out_xml.write_bytes(raw)
        log.info("saved %d bytes to %s", len(raw), out_xml)

        df = parse_sdmx_to_df(raw)
        log.info("SDMX dataframe shape: %s", df.shape)
        codelists = parse_sdmx_codelists(raw)
        log.info("CodeLists found: %s", sorted(codelists))
        for cl_id, codes in codelists.items():
            log.info("  %s: %d entries", cl_id, len(codes))

        territory = meta.fields["57831"]
        goods = meta.fields["58273"]

        # CodeLists key naming: from inspection, fedstat uses
        #   's_OKATO' (territory), 's_grtov' (goods).
        if "s_OKATO" not in codelists:
            log.error("CodeList 's_OKATO' missing! got: %s", sorted(codelists))
            return 2
        if "s_grtov" not in codelists:
            log.error("CodeList 's_grtov' missing! got: %s", sorted(codelists))
            return 2

        territory_fgrid_to_okato = _match_codelist_to_fgrid(
            {name: vid for vid, name in territory.values.items()},
            codelists["s_OKATO"],
        )
        goods_fgrid_to_grtov = _match_codelist_to_fgrid(
            {name: vid for vid, name in goods.values.items()},
            codelists["s_grtov"],
        )

        log.info(
            "step 5: name-bridge resolved %d/%d territories, %d/%d goods",
            len(territory_fgrid_to_okato), len(territory.values),
            len(goods_fgrid_to_grtov), len(goods.values),
        )

        # Build region alias rows
        region_rows: list[dict[str, object]] = []
        unresolved: list[int] = []
        for row in regions:
            rid = int(row["id"])
            fvid, fname = region_match[rid]
            okato = territory_fgrid_to_okato.get(fvid, "")
            cl_name = codelists["s_OKATO"].get(okato, "") if okato else ""
            if not okato:
                unresolved.append(rid)
            region_rows.append({
                "region_id": rid,
                "region_name": row["name"],
                "fgrid_value_id": fvid,
                "okato_code": okato,
                "fedstat_name_fgrid": fname,
                "fedstat_name_codelist": cl_name,
            })

        if unresolved:
            log.warning("OKATO code missing for region_id(s): %s", unresolved)

        out_regions_csv = SEED_DIR / "fedstat_region_aliases.csv"
        _write_csv(
            out_regions_csv,
            header=["region_id", "region_name", "fgrid_value_id",
                    "okato_code", "fedstat_name_fgrid", "fedstat_name_codelist"],
            rows=region_rows,
        )
        log.info("wrote %s (%d rows)", out_regions_csv, len(region_rows))

        # Build fuel alias rows
        fuel_rows: list[dict[str, object]] = []
        unresolved_fuels: list[str] = []
        for label, (vid, fname) in fuel_match.items():
            grtov = goods_fgrid_to_grtov.get(vid, "")
            cl_name = codelists["s_grtov"].get(grtov, "") if grtov else ""
            if not grtov:
                unresolved_fuels.append(label)
            fuel_rows.append({
                "fuel_label": label,
                "fgrid_value_id": vid,
                "grtov_code": grtov,
                "fedstat_name_fgrid": fname,
                "fedstat_name_codelist": cl_name,
            })

        if unresolved_fuels:
            log.warning("grtov code missing for fuel(s): %s", unresolved_fuels)

        out_fuel_csv = SEED_DIR / "fedstat_fuel_aliases.csv"
        _write_csv(
            out_fuel_csv,
            header=["fuel_label", "fgrid_value_id", "grtov_code",
                    "fedstat_name_fgrid", "fedstat_name_codelist"],
            rows=fuel_rows,
        )
        log.info("wrote %s (%d rows)", out_fuel_csv, len(fuel_rows))

    log.info("bootstrap OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
