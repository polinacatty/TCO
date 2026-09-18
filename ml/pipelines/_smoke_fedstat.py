"""Live smoke test for the fedstat client.

Runs ONE narrow request to verify the full pipeline end-to-end:

  Indicator: 31448 (Средние потребительские цены)
  Year:      2024
  Period:    январь
  Territory: Город Москва
  Goods:     Бензин АИ-95
  Unit:      рубль (mandatory inclusion via *)

Saves the raw SDMX response to ``ml/data/raw/fedstat/_smoke_31448.sdmx.xml``
and prints the parsed DataFrame.

Run::

    python ml\\pipelines\\_smoke_fedstat.py

If you have no internet access, expect a connect error: that is OK,
just rerun later.  The unit tests in ``test_fedstat_client.py`` cover
the offline parts.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path

from _fedstat_client import FedstatClient  # type: ignore[import-not-found]


INDICATOR_ID = "31448"
RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw" / "fedstat"


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s :: %(message)s",
    )
    log = logging.getLogger("smoke")

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    with FedstatClient() as fs:
        log.info("step 1: GET indicator page %s", INDICATOR_ID)
        meta = fs.get_filter_ids(INDICATOR_ID)
        log.info("title: %s", meta.title)
        log.info("fields: %s", sorted(meta.fields.keys()))
        log.info("csrf token len: %d", len(meta.csrf_token))

        territory = meta.fields["57831"]
        moscow_ids = territory.find_value_ids("Город Москва столица")
        if not moscow_ids:
            log.error("Moscow not found in territory field; aborting")
            return 2
        moscow_id = moscow_ids[0]
        log.info("Moscow id resolved to %s", moscow_id)

        goods = meta.fields["58273"]
        ai95_ids = goods.find_value_ids("марки АИ-95")
        if not ai95_ids:
            log.error("AI-95 not found in goods field; aborting")
            return 2
        log.info("AI-95 candidate ids: %s", ai95_ids)
        ai95_id = "1709750" if "1709750" in ai95_ids else ai95_ids[0]

        period = meta.fields["33560"]
        january_ids = period.find_value_ids("январ")
        january_id = january_ids[0] if january_ids else "1540283"

        filters = {
            "3": ["2024"],
            "33560": [january_id],
            "57831": [moscow_id],
            "58273": [ai95_id],
            "30611": "*",
        }
        log.info("step 2: POST data.do with %s", filters)
        raw = fs.post_filtered(INDICATOR_ID, meta, filters, fmt="sdmx")
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = RAW_DIR / f"_smoke_{INDICATOR_ID}_{ts}.sdmx.xml"
        out_path.write_bytes(raw)
        log.info("saved %d bytes to %s", len(raw), out_path)

        head = raw[:400].decode("utf-8", errors="replace")
        log.info("response head:\n%s", head)

        log.info("step 3: parse SDMX")
        from _fedstat_client import parse_sdmx_to_df  # type: ignore[import-not-found]

        df = parse_sdmx_to_df(raw)
        log.info("parsed dataframe shape: %s", df.shape)
        log.info("columns: %s", list(df.columns))
        if not df.empty:
            log.info("first rows:\n%s", df.head(10).to_string())
            obs_col = df["OBS_VALUE"]
            log.info(
                "OBS_VALUE summary: min=%s max=%s mean=%.2f n=%d",
                obs_col.min(),
                obs_col.max(),
                float(obs_col.mean()),
                len(obs_col),
            )
        else:
            log.warning("empty dataframe — fedstat returned no observations for the requested filter")
            return 1

    log.info("smoke OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
