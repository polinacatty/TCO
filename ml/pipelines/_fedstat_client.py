"""Low-level client for the EMISS / fedstat.ru reporting API.

The public site is the only entry point: there is no documented API.
The flow we implement here is the one used by R-package `fedstatAPIr`,
adapted for what the live HTML actually contains in 2026.

Two stages:

1. ``get_filter_ids(indicator_id)`` — GETs the human-facing indicator page
   (``https://www.fedstat.ru/indicator/<id>``), extracts the inline
   ``new FGrid({...})`` JavaScript literal that lists every filter field
   and its values, and pulls the Apache Struts CSRF token from the hidden
   form fields.  Returns an :class:`IndicatorMeta`.
2. ``post_filtered(indicator_id, meta, filters, fmt)`` — sends an
   ``application/x-www-form-urlencoded`` POST to ``/indicator/data.do``
   carrying the CSRF token, repeated ``selectedFilterIds`` entries and
   the desired output format (``sdmx`` | ``excel``).  Wrapped in
   tenacity retries with exponential backoff.
3. ``parse_sdmx_to_df(raw_bytes, meta=None)`` — turns an SDMX 2.0
   ``GenericData`` document into a long ``pandas.DataFrame``.

The client is *not* asynchronous: ETL jobs are batch processes that run
once a day at most, and a single client with cookie persistence is the
simplest robust shape.

Why curl_cffi rather than httpx/requests
----------------------------------------

fedstat.ru's WAF performs **TLS fingerprinting** (JA3) and blocks
clients whose handshake does not match a real browser, returning a
plain ``403 Forbidden`` regardless of HTTP-level headers.  curl_cffi
delegates the TLS handshake to libcurl with Chrome's exact cipher
suites, ALPN and extension order, so the WAF lets us through.  This
was discovered empirically during sprint 1 reconnaissance — see
``docs/03_data_collection/03_fuel_data_recon.md``.

This module is internal: ``ingest_fuel_prices.py`` (and similar
high-level scripts) compose it.  Tests live in
``ml/pipelines/test_fedstat_client.py``.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd
from curl_cffi import requests as cf_requests
from curl_cffi.requests.errors import RequestsError
from lxml import etree
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)


BASE_URL = "https://www.fedstat.ru"
INDICATOR_URL = BASE_URL + "/indicator/{id}"
DATA_URL = BASE_URL + "/indicator/data.do"

DEFAULT_IMPERSONATE = "chrome120"
DEFAULT_EXTRA_HEADERS = {
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.5,en;q=0.3",
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FilterField:
    """A single dimension of an indicator (``Год``, ``Период``, ``Виды`` ...).

    Attributes
    ----------
    field_id:
        Numeric identifier of the dimension (e.g. ``3`` = ``Год``).
        Always represented as a string because that is how it appears in
        POST bodies.
    title:
        Human-readable label, taken verbatim from the page.
    values:
        Mapping ``value_id -> value_title`` for every allowed value.  The
        order from the page is preserved (Python 3.7+ dict ordering).
    """

    field_id: str
    title: str
    values: dict[str, str] = field(default_factory=dict)

    def find_value_ids(self, query: str | Iterable[str]) -> list[str]:
        """Return value ids whose title contains *query* (case-insensitive).

        Accepts either a single substring or an iterable of substrings (any
        match wins).  Useful for the high-level ETL: instead of hard-coding
        ``"1709750"`` for ``"АИ-95"``, write
        ``meta.fields["58273"].find_value_ids("АИ-95")``.
        """
        if isinstance(query, str):
            queries = [query]
        else:
            queries = list(query)
        out: list[str] = []
        for vid, vtitle in self.values.items():
            low = vtitle.lower()
            if any(q.lower() in low for q in queries):
                out.append(vid)
        return out


@dataclass(frozen=True)
class IndicatorMeta:
    """All information we need to build a POST request for a given indicator."""

    indicator_id: str
    title: str
    csrf_token: str
    fields: dict[str, FilterField]
    top_columns: list[str]
    left_columns: list[str]
    filter_object_ids: list[str]


# ---------------------------------------------------------------------------
# HTML / JS parsing helpers (kept tightly scoped to fedstat.ru's layout)
# ---------------------------------------------------------------------------


_GRID_START_MARKER = "new FGrid({"

_FIELD_HEAD_RE = re.compile(
    r"(\d+)\s*:\s*\{\s*title\s*:\s*'((?:[^'\\]|\\.)*)'\s*,\s*all\s*:",
    re.MULTILINE,
)
_VALUE_RE = re.compile(
    r"(\d+)\s*:\s*\{\s*title\s*:\s*'((?:[^'\\]|\\.)*)'\s*,\s*"
    r"order\s*:\s*-?\d+\s*,\s*checked\s*:\s*(?:true|false)\s*\}",
    re.MULTILINE,
)
_ARRAY_RE = re.compile(
    r"(left_columns|top_columns|filterObjectIds)\s*:\s*\[\s*([\d,\s]*)\s*\]"
)
_JS_UNICODE_RE = re.compile(r"\\u([0-9a-fA-F]{4})")

_TITLE_RE = re.compile(r"<title>([^<]*)</title>", re.IGNORECASE)
_TOKEN_RE = re.compile(
    r'<input[^>]*\bname\s*=\s*["\']token["\'][^>]*\bvalue\s*=\s*["\']([0-9A-Z]{16,})["\']',
    re.IGNORECASE,
)


def _decode_js_string(s: str) -> str:
    """Turn a fedstat-style JS string literal body into a Python ``str``.

    The page mixes raw UTF-8 Cyrillic and ``\\uXXXX`` escapes (escape
    sequences are emitted by their templating engine for some characters
    only).  We expand the escapes first, then unescape the standard JS
    quote/slash/backslash forms.
    """
    s = _JS_UNICODE_RE.sub(lambda m: chr(int(m.group(1), 16)), s)
    s = s.replace("\\'", "'").replace('\\"', '"').replace("\\/", "/").replace("\\\\", "\\")
    return s


def _find_balanced_brace(text: str, start: int) -> int:
    """Index of the ``}`` matching the ``{`` at ``start`` in JS source.

    Walks the text, tracking single-quoted strings (the only kind fedstat
    uses inside FGrid) and respecting backslash escapes inside them.
    """
    if text[start] != "{":
        raise ValueError("expected '{' at start position")
    depth = 0
    in_string = False
    escape = False
    i = start
    while i < len(text):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == "'":
                in_string = False
        else:
            if ch == "'":
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    raise ValueError("unbalanced braces in FGrid literal")


def _extract_csrf_token(html: str) -> str:
    m = _TOKEN_RE.search(html)
    if not m:
        raise FedstatParseError("CSRF token not found on indicator page")
    return m.group(1)


def _extract_indicator_title(html: str, fields: dict[str, "FilterField"]) -> str:
    """Best-effort title extraction.

    The HTML ``<title>`` is just "ЕМИСС" everywhere, so we prefer the
    canonical name fedstat puts into FGrid field ``0`` ("Показатель") —
    its single value is the indicator's display title.  Falls back to
    ``<title>`` and finally to ``"(unknown)"``.
    """
    indicator_field = fields.get("0")
    if indicator_field is not None and indicator_field.values:
        first_title = next(iter(indicator_field.values.values()))
        if first_title.strip():
            return first_title.strip()
    m = _TITLE_RE.search(html)
    return (m.group(1).strip() if m else "").strip() or "(unknown)"


def parse_indicator_html(html: str) -> tuple[
    dict[str, FilterField], list[str], list[str], list[str], str, str
]:
    """Parse fedstat indicator HTML page.

    Returns ``(fields, top_columns, left_columns, filter_object_ids,
    csrf_token, indicator_title)``.

    Exposed at module level so unit tests can feed it a stored HTML
    fixture without doing any network I/O.
    """
    grid_start = html.find(_GRID_START_MARKER)
    if grid_start == -1:
        raise FedstatParseError(
            f"marker {_GRID_START_MARKER!r} not found; indicator page layout changed?"
        )
    obj_open = html.index("{", grid_start)
    obj_close = _find_balanced_brace(html, obj_open)
    grid_text = html[obj_open : obj_close + 1]

    arrays: dict[str, list[str]] = {}
    for m in _ARRAY_RE.finditer(grid_text):
        arr_name = m.group(1)
        arr_body = m.group(2).strip()
        arrays[arr_name] = (
            [x.strip() for x in arr_body.split(",") if x.strip()] if arr_body else []
        )

    fields: dict[str, FilterField] = {}
    for m in _FIELD_HEAD_RE.finditer(grid_text):
        field_id = m.group(1)
        title = _decode_js_string(m.group(2))
        values_kw = grid_text.find("values", m.end())
        if values_kw == -1:
            continue
        try:
            brace_open = grid_text.index("{", values_kw)
            brace_close = _find_balanced_brace(grid_text, brace_open)
        except ValueError:
            continue
        values_text = grid_text[brace_open + 1 : brace_close]
        values: dict[str, str] = {}
        for vm in _VALUE_RE.finditer(values_text):
            vid = vm.group(1)
            vtitle = _decode_js_string(vm.group(2))
            values.setdefault(vid, vtitle)

        existing = fields.get(field_id)
        if existing is not None and len(existing.values) >= len(values):
            continue
        fields[field_id] = FilterField(field_id=field_id, title=title, values=values)

    csrf_token = _extract_csrf_token(html)
    title = _extract_indicator_title(html, fields)
    return (
        fields,
        arrays.get("top_columns", []),
        arrays.get("left_columns", []),
        arrays.get("filterObjectIds", []),
        csrf_token,
        title,
    )


# ---------------------------------------------------------------------------
# SDMX 1.0 GenericData parser (fedstat dialect)
# ---------------------------------------------------------------------------


_SDMX_NS = {
    "msg": "http://www.SDMX.org/resources/SDMXML/schemas/v1_0/message",
    "generic": "http://www.SDMX.org/resources/SDMXML/schemas/v1_0/generic",
    "structure": "http://www.SDMX.org/resources/SDMXML/schemas/v1_0/structure",
}


def parse_sdmx_codelists(raw_bytes: bytes) -> dict[str, dict[str, str]]:
    """Extract the CodeLists section as ``{codelist_id: {code: name}}``.

    fedstat embeds a ``<CodeLists>`` block at the top of every SDMX
    response; it maps internal Rosstat codes (``s_grtov=7803``,
    ``s_OKATO=45000000000``...) to human-readable Russian names.
    Without this map, ``parse_sdmx_to_df`` rows look opaque.
    """
    parser = etree.XMLParser(huge_tree=True, recover=False)
    try:
        root = etree.fromstring(raw_bytes, parser)
    except etree.XMLSyntaxError as exc:
        raise FedstatParseError(f"invalid XML: {exc}") from exc

    out: dict[str, dict[str, str]] = {}
    for cl in root.iterfind(".//structure:CodeList", namespaces=_SDMX_NS):
        cl_id = cl.get("id", "")
        if not cl_id:
            continue
        codes: dict[str, str] = {}
        for code in cl.iterfind("structure:Code", namespaces=_SDMX_NS):
            value = code.get("value", "")
            desc_el = code.find("structure:Description", namespaces=_SDMX_NS)
            desc = (desc_el.text or "").strip() if desc_el is not None else ""
            if value:
                codes[value] = desc
        if codes:
            out[cl_id] = codes
    return out


def _parse_obs_value(raw: str | None) -> float | None:
    """fedstat encodes decimals with a comma (``"56,87"``)."""
    if raw in (None, ""):
        return None
    text = raw.replace(",", ".") if isinstance(raw, str) else raw
    try:
        return float(text)
    except ValueError:
        return None


def parse_sdmx_to_df(
    raw_bytes: bytes,
    *,
    concept_renames: Mapping[str, str] | None = None,
) -> pd.DataFrame:
    """Decode a fedstat SDMX 1.0 ``GenericData`` document into a long DataFrame.

    The fedstat dialect represents each combination of dimensions on
    the row/column axes as one ``<generic:Series>``.  Inside:

    - ``<generic:SeriesKey>`` holds the **left-axis** dimensions
      (``lineObjectIds`` from the request) — typically things like
      region, goods.
    - ``<generic:Attributes>`` holds the *single-value filters*
      (``filterObjectIds`` from the request) — e.g. unit of measure
      (``EI``) and, in this indicator, the period within the year
      (``PERIOD``).  We flatten them into the same row.
    - ``<generic:Obs>`` holds one value per top-axis bucket — for
      ``31448`` that's *year*: each Obs has ``<Time>2024</Time>`` and
      ``<ObsValue value="56,87"/>``.

    The returned DataFrame has columns:

    - one column per ``concept`` from the SeriesKey and Attributes
      (e.g. ``s_OKATO``, ``s_grtov``, ``EI``, ``PERIOD``);
    - ``TIME_PERIOD`` — the contents of ``<Time>``;
    - ``OBS_VALUE`` — the parsed observation as ``float`` (``NaN`` for
      missing or unparseable values).

    Parameters
    ----------
    raw_bytes:
        The raw response body from ``data.do?format=sdmx``.
    concept_renames:
        Optional mapping ``original_concept_name -> new_column_name``.
        Useful for the high-level ingest script to translate concept
        names like ``s_OKATO`` to ``region_okato`` etc.

    Raises
    ------
    FedstatParseError
        If the payload is empty or not well-formed XML.
    """
    if not raw_bytes:
        raise FedstatParseError("empty SDMX payload")
    parser = etree.XMLParser(huge_tree=True, recover=False)
    try:
        root = etree.fromstring(raw_bytes, parser)
    except etree.XMLSyntaxError as exc:
        raise FedstatParseError(f"invalid XML: {exc}") from exc

    rows: list[dict[str, str | float | None]] = []
    for series in root.iterfind(".//generic:Series", namespaces=_SDMX_NS):
        base: dict[str, str | None] = {}
        skey = series.find("generic:SeriesKey", namespaces=_SDMX_NS)
        if skey is not None:
            for v in skey.iterfind("generic:Value", namespaces=_SDMX_NS):
                base[v.get("concept", "")] = v.get("value")
        attrs = series.find("generic:Attributes", namespaces=_SDMX_NS)
        if attrs is not None:
            for v in attrs.iterfind("generic:Value", namespaces=_SDMX_NS):
                base[v.get("concept", "")] = v.get("value")

        for obs in series.iterfind("generic:Obs", namespaces=_SDMX_NS):
            row: dict[str, str | float | None] = dict(base)
            time_el = obs.find("generic:Time", namespaces=_SDMX_NS)
            row["TIME_PERIOD"] = time_el.text if time_el is not None else None
            val_el = obs.find("generic:ObsValue", namespaces=_SDMX_NS)
            row["OBS_VALUE"] = _parse_obs_value(
                val_el.get("value") if val_el is not None else None
            )
            rows.append(row)

    if not rows:
        logger.warning("parse_sdmx_to_df: no Series/Obs found in payload")
        return pd.DataFrame(columns=["OBS_VALUE"])

    df = pd.DataFrame(rows)
    if concept_renames:
        df = df.rename(columns=dict(concept_renames))
    return df


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class FedstatError(RuntimeError):
    """Base class for all fedstat client errors."""


class FedstatParseError(FedstatError):
    """Raised when the indicator page or response cannot be parsed."""


class FedstatHttpError(FedstatError):
    """Raised when fedstat returns a non-2xx response we should not retry."""


_RETRIABLE_HTTP = (RequestsError,)


# ---------------------------------------------------------------------------
# The client itself
# ---------------------------------------------------------------------------


class FedstatClient:
    """Thin wrapper around ``curl_cffi.requests.Session`` for the fedstat API.

    Use as a context manager so the underlying connection pool and
    cookie jar are cleaned up on exit::

        with FedstatClient() as fs:
            meta = fs.get_filter_ids("31448")
            raw = fs.post_filtered("31448", meta, filters)

    The same session must be reused for the GET that mints the CSRF
    token and the POST that consumes it: fedstat ties the token to the
    ``JSESSIONID`` cookie.

    The session imitates Chrome 120's TLS fingerprint via
    ``impersonate=...``; that is what gets us past fedstat's WAF (see
    module docstring).
    """

    def __init__(
        self,
        *,
        timeout: float = 180.0,
        impersonate: str = DEFAULT_IMPERSONATE,
        extra_headers: Mapping[str, str] | None = None,
        session: Any | None = None,
    ) -> None:
        self._timeout = timeout
        self._impersonate = impersonate
        self._extra_headers = {**DEFAULT_EXTRA_HEADERS, **(extra_headers or {})}
        self._owns_session = session is None
        self._session: Any | None = session

    def __enter__(self) -> "FedstatClient":
        if self._session is None:
            self._session = cf_requests.Session(
                impersonate=self._impersonate,
                timeout=self._timeout,
            )
            if self._extra_headers:
                self._session.headers.update(self._extra_headers)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._owns_session and self._session is not None:
            self._session.close()
            self._session = None

    @property
    def session(self) -> Any:
        if self._session is None:
            raise FedstatError(
                "FedstatClient must be used as a context manager (with statement)"
            )
        return self._session

    # ------------------------------------------------------------------
    # Stage 1: get filter IDs + CSRF
    # ------------------------------------------------------------------
    def get_filter_ids(self, indicator_id: str | int) -> IndicatorMeta:
        """Download the indicator page and return its parsed metadata.

        Raises :class:`FedstatParseError` if the HTML layout is
        unexpected (e.g. the ``new FGrid({`` literal disappeared) and
        :class:`FedstatHttpError` if the page returns 4xx/5xx.
        """
        indicator_id = str(indicator_id)
        url = INDICATOR_URL.format(id=indicator_id)
        logger.info("GET %s", url)
        r = self._do_get(url)
        if r.status_code != 200:
            raise FedstatHttpError(
                f"GET {url} returned {r.status_code}: {r.text[:200]!r}"
            )

        html = r.text
        fields, top, left, filt, token, title = parse_indicator_html(html)
        meta = IndicatorMeta(
            indicator_id=indicator_id,
            title=title,
            csrf_token=token,
            fields=fields,
            top_columns=top,
            left_columns=left,
            filter_object_ids=filt,
        )
        logger.info(
            "indicator %s parsed: %d fields, csrf-token len=%d",
            indicator_id,
            len(fields),
            len(token),
        )
        return meta

    @retry(
        reraise=True,
        retry=retry_if_exception_type(_RETRIABLE_HTTP),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def _do_get(self, url: str) -> Any:
        return self.session.get(url, timeout=self._timeout)

    # ------------------------------------------------------------------
    # Stage 2: POST filtered data request
    # ------------------------------------------------------------------
    def post_filtered(
        self,
        indicator_id: str | int,
        meta: IndicatorMeta,
        filters: Mapping[str, str | Sequence[str]],
        *,
        fmt: str = "sdmx",
    ) -> bytes:
        """POST a filtered query and return the raw response body.

        Parameters
        ----------
        indicator_id:
            Numeric indicator id (must match ``meta.indicator_id``).
        meta:
            Result of :meth:`get_filter_ids` — supplies the CSRF token
            and the universe of valid value ids per field.
        filters:
            Mapping ``field_id -> value_ids``.  ``value_ids`` may be
            ``"*"`` to select **all** known values for that field, a
            single id string, or any sequence of id strings.  Every
            field present in ``meta.fields`` should be specified
            (otherwise fedstat may return 500).
        fmt:
            Output format.  Currently ``"sdmx"`` (returns XML bytes)
            and ``"excel"`` (returns ``.xls`` bytes) are accepted.

        Raises
        ------
        FedstatHttpError
            On non-retriable HTTP errors (4xx) or once retries are
            exhausted.
        """
        indicator_id = str(indicator_id)
        if indicator_id != meta.indicator_id:
            raise ValueError(
                f"indicator_id mismatch: {indicator_id} vs meta.indicator_id={meta.indicator_id}"
            )
        if fmt not in {"sdmx", "excel"}:
            raise ValueError(f"unsupported format: {fmt!r}")

        body = self._build_body(meta, filters, fmt)
        logger.info(
            "POST %s?format=%s with %d selectedFilterIds entries",
            DATA_URL,
            fmt,
            sum(1 for k, _ in body if k == "selectedFilterIds"),
        )
        r = self._do_post(DATA_URL, params={"format": fmt}, data=body)
        if r.status_code != 200:
            raise FedstatHttpError(
                f"POST {DATA_URL} returned {r.status_code}: {r.text[:200]!r}"
            )
        return r.content

    @retry(
        reraise=True,
        retry=retry_if_exception_type(_RETRIABLE_HTTP),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def _do_post(
        self, url: str, *, params: Mapping[str, str], data: list[tuple[str, str]]
    ) -> Any:
        return self.session.post(
            url,
            params=params,
            data=data,
            timeout=self._timeout,
        )

    # ------------------------------------------------------------------
    # Body construction
    # ------------------------------------------------------------------
    @staticmethod
    def _build_body(
        meta: IndicatorMeta,
        filters: Mapping[str, str | Sequence[str]],
        fmt: str,
        *,
        title: str | None = None,
    ) -> list[tuple[str, str]]:
        """Materialise the form-encoded body as a list of (key, value) tuples.

        We mirror the body produced by ``FGrid.savePreview(true)`` +
        ``downloadFile(format)`` in the page's ``FGrid.js``:

        - ``title`` = display caption (free-form).
        - ``id`` = indicator id.
        - ``lineObjectIds`` = each left-column axis field id (rows).
        - ``columnObjectIds`` = each top-column axis field id (columns).
        - ``filterObjectIds`` = each filter-only field id (knobs).
        - ``selectedFilterIds`` = ``"<field_id>_<value_id>"`` for every
          checked value across **all** fields (axes + filters).

        Without the three ``*ObjectIds`` lists fedstat cannot reconstruct
        the grid layout and silently returns the regular HTML page
        instead of the requested SDMX/Excel payload.

        Returns a list of tuples (not a dict) because keys repeat.

        Note: ``fmt`` is passed in the URL query string by the caller
        (matching FGrid.js: ``action="/indicator/data.do?format=..."``);
        we do **not** add it to the body.
        """
        del fmt  # not used in body; kept for API symmetry / future use
        body: list[tuple[str, str]] = [
            ("id", meta.indicator_id),
            ("title", title if title is not None else meta.title),
        ]
        for field_id in meta.left_columns:
            body.append(("lineObjectIds", field_id))
        for field_id in meta.top_columns:
            body.append(("columnObjectIds", field_id))
        for field_id in meta.filter_object_ids:
            body.append(("filterObjectIds", field_id))

        for field_id, raw_values in filters.items():
            ff = meta.fields.get(field_id)
            if ff is None:
                raise ValueError(
                    f"filter for unknown field_id {field_id!r}; "
                    f"known: {sorted(meta.fields)}"
                )
            if raw_values == "*":
                value_ids: list[str] = list(ff.values.keys())
            elif isinstance(raw_values, str):
                value_ids = [raw_values]
            else:
                value_ids = list(raw_values)
            for vid in value_ids:
                body.append(("selectedFilterIds", f"{field_id}_{vid}"))
        return body
