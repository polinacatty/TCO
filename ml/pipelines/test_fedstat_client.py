"""Offline tests for _fedstat_client.

These run without any network access: they reuse the saved
``ml/data/raw/_recon_31448.html`` fixture that we downloaded during
recon.

To run::

    python -m pytest ml/pipelines/test_fedstat_client.py -v

(if pytest is not installed, ``python ml/pipelines/test_fedstat_client.py``
works too — we provide a tiny ``__main__`` runner at the bottom).
"""

from __future__ import annotations

from pathlib import Path

from _fedstat_client import (  # type: ignore[import-not-found]
    FedstatClient,
    FilterField,
    IndicatorMeta,
    parse_indicator_html,
    parse_sdmx_codelists,
    parse_sdmx_to_df,
)


RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"
HTML_FIXTURE = RAW_DIR / "_recon_31448.html"
SDMX_FIXTURE = next(
    iter(sorted((RAW_DIR / "fedstat").glob("_smoke_31448_*.sdmx.xml"), reverse=True)),
    None,
)


def test_parse_indicator_html_has_expected_fields() -> None:
    html = HTML_FIXTURE.read_text(encoding="utf-8")
    fields, top, left, filt, token, title = parse_indicator_html(html)

    assert "31448" in title or "Средние" in title, f"unexpected title: {title!r}"
    assert len(token) >= 16, f"CSRF token too short: {token!r}"

    assert "3" in fields, "missing field 3 (Год)"
    assert "33560" in fields, "missing field 33560 (Период)"
    assert "57831" in fields, "missing field 57831 (Территория)"
    assert "58273" in fields, "missing field 58273 (Виды товаров и услуг)"

    god = fields["3"]
    assert god.title == "Год", f"expected 'Год', got {god.title!r}"
    assert "2024" in god.values

    period = fields["33560"]
    assert len(period.values) == 12, f"expected 12 months, got {len(period.values)}"

    fuel = fields["58273"]
    ai95 = fuel.find_value_ids("АИ-95")
    assert "1709750" in ai95, f"expected AI-95 id 1709750 in {ai95}"

    diesel = fuel.find_value_ids("Дизельное топливо")
    assert "1755196" in diesel, f"expected diesel id 1755196 in {diesel}"

    territory = fields["57831"]
    moscow = territory.find_value_ids("Город Москва")
    assert "1688506" in moscow, f"expected Moscow id 1688506 in {moscow}"

    assert top == ["3", "33560"], f"unexpected top_columns: {top}"
    assert left == ["57831", "58273"], f"unexpected left_columns: {left}"
    assert filt == ["30611"], f"unexpected filterObjectIds: {filt}"


def test_build_body_shapes_request_correctly() -> None:
    html = HTML_FIXTURE.read_text(encoding="utf-8")
    fields, top, left, filt, token, title = parse_indicator_html(html)
    meta = IndicatorMeta(
        indicator_id="31448",
        title=title,
        csrf_token=token,
        fields=fields,
        top_columns=top,
        left_columns=left,
        filter_object_ids=filt,
    )

    body = FedstatClient._build_body(
        meta,
        {
            "3": ["2024"],
            "33560": ["1540283"],
            "57831": ["1688506"],
            "58273": ["1709750"],
            "30611": "*",
        },
        "sdmx",
    )

    body_dict = dict(body)
    assert body_dict["id"] == "31448"
    assert "title" in body_dict and body_dict["title"]

    line_ids = [v for k, v in body if k == "lineObjectIds"]
    assert line_ids == ["57831", "58273"], f"unexpected lineObjectIds: {line_ids}"

    col_ids = [v for k, v in body if k == "columnObjectIds"]
    assert col_ids == ["3", "33560"], f"unexpected columnObjectIds: {col_ids}"

    filt_ids = [v for k, v in body if k == "filterObjectIds"]
    assert filt_ids == ["30611"], f"unexpected filterObjectIds: {filt_ids}"

    selected = [v for k, v in body if k == "selectedFilterIds"]
    assert "3_2024" in selected
    assert "33560_1540283" in selected
    assert "57831_1688506" in selected
    assert "58273_1709750" in selected
    assert "30611_950351" in selected


def test_build_body_rejects_unknown_field_id() -> None:
    html = HTML_FIXTURE.read_text(encoding="utf-8")
    fields, top, left, filt, token, title = parse_indicator_html(html)
    meta = IndicatorMeta(
        indicator_id="31448",
        title=title,
        csrf_token=token,
        fields=fields,
        top_columns=top,
        left_columns=left,
        filter_object_ids=filt,
    )
    try:
        FedstatClient._build_body(meta, {"99999": ["123"]}, "sdmx")
    except ValueError as exc:
        assert "99999" in str(exc)
    else:
        raise AssertionError("expected ValueError for unknown field id")


def test_build_body_wildcard_expands_all_values() -> None:
    html = HTML_FIXTURE.read_text(encoding="utf-8")
    fields, top, left, filt, token, title = parse_indicator_html(html)
    meta = IndicatorMeta(
        indicator_id="31448",
        title=title,
        csrf_token=token,
        fields=fields,
        top_columns=top,
        left_columns=left,
        filter_object_ids=filt,
    )

    body = FedstatClient._build_body(meta, {"33560": "*"}, "sdmx")
    months = [v for k, v in body if k == "selectedFilterIds"]
    assert len(months) == 12, f"expected 12 month entries, got {months}"


def test_parse_sdmx_to_df_handles_minimal_payload() -> None:
    sample = ("""<?xml version="1.0" encoding="UTF-8"?>
    <GenericData
        xmlns="http://www.SDMX.org/resources/SDMXML/schemas/v1_0/message"
        xmlns:generic="http://www.SDMX.org/resources/SDMXML/schemas/v1_0/generic">
      <DataSet>
        <generic:Series>
          <generic:SeriesKey>
            <generic:Value concept="s_OKATO" value="45000000000"/>
            <generic:Value concept="s_grtov" value="7803"/>
          </generic:SeriesKey>
          <generic:Attributes>
            <generic:Value concept="EI" value="рубль"/>
            <generic:Value concept="PERIOD" value="январь"/>
          </generic:Attributes>
          <generic:Obs>
            <generic:Time>2024</generic:Time>
            <generic:ObsValue value="56,87"/>
          </generic:Obs>
        </generic:Series>
      </DataSet>
    </GenericData>
    """).encode("utf-8")
    df = parse_sdmx_to_df(sample)
    assert len(df) == 1
    row = df.iloc[0]
    assert row["s_OKATO"] == "45000000000"
    assert row["s_grtov"] == "7803"
    assert row["EI"] == "рубль"
    assert row["PERIOD"] == "январь"
    assert row["TIME_PERIOD"] == "2024"
    assert row["OBS_VALUE"] == 56.87


def test_parse_sdmx_to_df_against_real_fixture() -> None:
    if SDMX_FIXTURE is None or not SDMX_FIXTURE.exists():
        print(f"  (skipped: no SDMX fixture; run _smoke_fedstat.py first)")
        return
    raw = SDMX_FIXTURE.read_bytes()
    df = parse_sdmx_to_df(raw)
    assert not df.empty, "expected at least 1 observation in real fixture"
    assert "OBS_VALUE" in df.columns
    assert df["OBS_VALUE"].notna().any(), "no numeric observations parsed"

    codelists = parse_sdmx_codelists(raw)
    assert codelists, "expected non-empty CodeLists"
    assert "s_grtov" in codelists or "s_OKATO" in codelists, (
        f"expected s_grtov / s_OKATO codelists; got: {sorted(codelists)[:5]}"
    )


def test_filter_field_find_value_ids_is_case_insensitive() -> None:
    ff = FilterField(
        field_id="58273",
        title="Виды товаров и услуг",
        values={"1709730": "Бензин автомобильный марки АИ-92, л",
                "1709750": "Бензин автомобильный марки АИ-95, л"},
    )
    assert ff.find_value_ids("аи-95") == ["1709750"]
    assert sorted(ff.find_value_ids("бензин")) == ["1709730", "1709750"]


def _run_all() -> int:
    tests = [
        test_parse_indicator_html_has_expected_fields,
        test_build_body_shapes_request_correctly,
        test_build_body_rejects_unknown_field_id,
        test_build_body_wildcard_expands_all_values,
        test_parse_sdmx_to_df_handles_minimal_payload,
        test_parse_sdmx_to_df_against_real_fixture,
        test_filter_field_find_value_ids_is_case_insensitive,
    ]
    failed = 0
    for t in tests:
        name = t.__name__
        try:
            t()
        except AssertionError as exc:
            failed += 1
            print(f"FAIL  {name}: {exc}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"ERROR {name}: {type(exc).__name__}: {exc}")
        else:
            print(f"ok    {name}")
    print()
    print(f"=== {len(tests) - failed} passed, {failed} failed ===")
    return failed


if __name__ == "__main__":
    import sys

    sys.exit(_run_all())
