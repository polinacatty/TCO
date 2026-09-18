"""Download key policy rate and FX reference rates from the Bank of Russia (XML APIs).

Sources
-------

* **FX dynamics:** ``GET https://www.cbr.ru/scripts/XML_dynamic.asp``
  (parameters ``date_req1``, ``date_req2`` in ``DD/MM/YYYY``, ``VAL_NM_RQ`` — internal
  currency id: ``R01235`` USD, ``R01239`` EUR, ``R01375`` CNY).

* **Key rate:** ``POST https://www.cbr.ru/DailyInfoWebServ/DailyInfo.asmx`` SOAP
  ``KeyRateXML`` (``fromDate``, ``ToDate``).

Output:

* ``ml/data/processed/cbr_rates.parquet`` — long format:
  ``metric_date``, ``metric_type``, ``value``, ``source``.
* Raw XML snapshots under ``ml/data/raw/cbr/<ingest-date>/`` for audit.

Run::

    python ml\\pipelines\\ingest_cbr_rates.py
    python ml\\pipelines\\ingest_cbr_rates.py --start-date 2014-01-01 --end-date 2026-04-28

"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import httpx
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DIR = REPO_ROOT / "ml" / "data" / "processed"
RAW_BASE = REPO_ROOT / "ml" / "data" / "raw" / "cbr"

SOURCE_TAG = "cbr_xml"

CBR_DYNAMIC = "https://www.cbr.ru/scripts/XML_dynamic.asp"
CBR_SOAP = "https://www.cbr.ru/DailyInfoWebServ/DailyInfo.asmx"

CURRENCIES: tuple[tuple[str, str], ...] = (
    ("R01235", "usd_rub"),
    ("R01239", "eur_rub"),
    ("R01375", "cny_rub"),
)

SOAP_KEYRATE_BODY = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <KeyRateXML xmlns="http://web.cbr.ru/">
      <fromDate>{from_iso}</fromDate>
      <ToDate>{to_iso}</ToDate>
    </KeyRateXML>
  </soap:Body>
</soap:Envelope>
"""


def _parse_float_ru(s: str) -> float:
    return float(s.strip().replace(",", ".").replace(" ", ""))


def fetch_currency_dynamic(
    client: httpx.Client,
    date_from: dt.date,
    date_to: dt.date,
    val_nm_rq: str,
) -> bytes:
    params = {
        "date_req1": date_from.strftime("%d/%m/%Y"),
        "date_req2": date_to.strftime("%d/%m/%Y"),
        "VAL_NM_RQ": val_nm_rq,
    }
    r = client.get(CBR_DYNAMIC, params=params, timeout=120.0)
    r.raise_for_status()
    return r.content


def parse_dynamic_currency_xml(xml_bytes: bytes) -> list[tuple[dt.date, float]]:
    root = ET.fromstring(xml_bytes)
    out: list[tuple[dt.date, float]] = []
    for rec in root.findall(".//Record"):
        ds = rec.get("Date")
        if not ds:
            continue
        day, month, year = (int(x) for x in ds.split("."))
        d = dt.date(year, month, day)
        vr = rec.findtext("VunitRate") or rec.findtext("Value")
        if not vr:
            continue
        out.append((d, _parse_float_ru(vr)))
    return out


def fetch_key_rate_soap(client: httpx.Client, date_from: dt.date, date_to: dt.date) -> bytes:
    body = SOAP_KEYRATE_BODY.format(
        from_iso=f"{date_from.isoformat()}T00:00:00",
        to_iso=f"{date_to.isoformat()}T00:00:00",
    )
    r = client.post(
        CBR_SOAP,
        content=body.encode("utf-8"),
        headers={
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": "http://web.cbr.ru/KeyRateXML",
        },
        timeout=120.0,
    )
    r.raise_for_status()
    return r.content


def parse_key_rate_soap_xml(xml_bytes: bytes) -> list[tuple[dt.date, float]]:
    root = ET.fromstring(xml_bytes)
    out: list[tuple[dt.date, float]] = []
    for kr in root.iter():
        if not kr.tag.endswith("KR"):
            continue
        dt_el = rate_el = None
        for ch in kr:
            if ch.tag.endswith("DT"):
                dt_el = ch
            elif ch.tag.endswith("Rate"):
                rate_el = ch
        if dt_el is None or rate_el is None or not dt_el.text or not rate_el.text:
            continue
        ts = pd.to_datetime(dt_el.text)
        d = ts.date() if hasattr(ts, "date") else ts
        out.append((d, float(rate_el.text.replace(",", "."))))
    return out


def build_long_frame(
    rows_fx: dict[str, list[tuple[dt.date, float]]],
    rows_kr: list[tuple[dt.date, float]],
) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for mtype, pairs in rows_fx.items():
        for d, v in pairs:
            records.append(
                {
                    "metric_date": pd.Timestamp(d),
                    "metric_type": mtype,
                    "value": float(v),
                    "source": SOURCE_TAG,
                }
            )
    for d, v in rows_kr:
        records.append(
            {
                "metric_date": pd.Timestamp(d),
                "metric_type": "key_rate",
                "value": float(v),
                "source": SOURCE_TAG,
            }
        )
    df = pd.DataFrame.from_records(records)
    if df.empty:
        return df
    df = df.sort_values(["metric_date", "metric_type"])
    df = df.drop_duplicates(subset=["metric_date", "metric_type"], keep="last")
    return df.reset_index(drop=True)


def check_quality(df: pd.DataFrame) -> None:
    if df.empty:
        raise ValueError("empty frame")
    exp_types = {"usd_rub", "eur_rub", "cny_rub", "key_rate"}
    got = set(df["metric_type"].unique())
    if not exp_types <= got:
        raise ValueError(f"missing metric_type: {exp_types - got}")
    kr = df.loc[df["metric_type"] == "key_rate", "value"]
    if kr.min() <= 0 or kr.max() >= 200:
        raise ValueError(f"key_rate out of plausible range: {kr.min()}..{kr.max()}")
    fx = df.loc[df["metric_type"].isin(["usd_rub", "eur_rub", "cny_rub"]), "value"]
    if fx.min() <= 0 or fx.max() > 2000:
        raise ValueError(f"FX out of plausible range: {fx.min()}..{fx.max()}")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="Ingest CBR key rate + FX into parquet.")
    p.add_argument("--start-date", type=str, default="2014-01-01")
    p.add_argument("--end-date", type=str, default=None, help="ISO date; default: today")
    args = p.parse_args()

    d0 = dt.date.fromisoformat(args.start_date)
    d1 = dt.date.fromisoformat(args.end_date) if args.end_date else dt.date.today()

    ingest_day = dt.date.today()
    raw_dir = RAW_BASE / ingest_day.isoformat()
    raw_dir.mkdir(parents=True, exist_ok=True)

    headers = {"User-Agent": "diplom-tco-ingest/1.0 (educational; +https://cbr.ru/development/SXML/)"}

    rows_fx: dict[str, list[tuple[dt.date, float]]] = {}
    with httpx.Client(headers=headers, follow_redirects=True) as client:
        for val_id, mtype in CURRENCIES:
            logging.info("Fetching %s (%s) …", mtype, val_id)
            xml_bytes = fetch_currency_dynamic(client, d0, d1, val_id)
            (raw_dir / f"dynamic_{val_id}.xml").write_bytes(xml_bytes)
            rows_fx[mtype] = parse_dynamic_currency_xml(xml_bytes)
            logging.info("  %s rows: %d", mtype, len(rows_fx[mtype]))

        logging.info("Fetching key rate (SOAP) …")
        kr_xml = fetch_key_rate_soap(client, d0, d1)
        (raw_dir / "key_rate_KeyRateXML_response.xml").write_bytes(kr_xml)
        rows_kr = parse_key_rate_soap_xml(kr_xml)
        logging.info("  key_rate rows: %d", len(rows_kr))

    df = build_long_frame(rows_fx, rows_kr)
    check_quality(df)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = PROCESSED_DIR / "cbr_rates.parquet"
    df.to_parquet(out_path, index=False, compression="snappy")
    logging.info("Wrote %s (%d rows)", out_path.relative_to(REPO_ROOT), len(df))
    return 0


if __name__ == "__main__":
    sys.exit(main())
