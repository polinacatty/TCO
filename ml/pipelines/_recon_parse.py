"""Throwaway: parse the saved fedstat indicator HTML and inventory all fields.

This validates the regex-based extractor before we promote it to the
production client. The script runs against ml/data/raw/_recon_31074.html.
"""

from __future__ import annotations

import io
import re
import sys
from pathlib import Path


def _resolve_paths(indicator_id: str) -> tuple[Path, Path]:
    base = Path(__file__).resolve().parents[1] / "data" / "raw"
    return (base / f"_recon_{indicator_id}.html", base / f"_recon_parse_output_{indicator_id}.txt")

GRID_START_MARKER = "new FGrid({"
GRID_END_MARKER = "});"

FIELD_HEAD_RE = re.compile(
    r"(\d+)\s*:\s*\{\s*title\s*:\s*'((?:[^'\\]|\\.)*)'\s*,\s*all\s*:",
    re.MULTILINE,
)

VALUE_RE = re.compile(
    r"(\d+)\s*:\s*\{\s*title\s*:\s*'((?:[^'\\]|\\.)*)'\s*,\s*order\s*:\s*-?\d+\s*,\s*checked\s*:\s*(?:true|false)\s*\}",
    re.MULTILINE,
)

ARRAY_RE = re.compile(
    r"(left_columns|top_columns|filterObjectIds)\s*:\s*\[\s*([\d,\s]*)\s*\]"
)


_JS_UNICODE_RE = re.compile(r"\\u([0-9a-fA-F]{4})")


def _decode_js_string(s: str) -> str:
    """Decode \\uXXXX, \\', \\\", \\/, \\\\ from a JS string literal into a Python str.

    Handles the case when the source mixes raw UTF-8 chars and \\u-escapes,
    which is exactly what we observe on fedstat.ru pages.
    """
    s = _JS_UNICODE_RE.sub(lambda m: chr(int(m.group(1), 16)), s)
    s = s.replace("\\'", "'").replace('\\"', '"').replace("\\/", "/").replace("\\\\", "\\")
    return s


def find_balanced(text: str, start: int) -> int:
    """Return the index of the closing brace that matches the opening brace at `start`."""
    assert text[start] == "{"
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
    raise ValueError("unbalanced braces")


def main(indicator_id: str = "31448") -> Path:
    html_path, _ = _resolve_paths(indicator_id)
    text = html_path.read_text(encoding="utf-8")

    grid_start = text.index(GRID_START_MARKER)
    obj_open = text.index("{", grid_start)
    obj_close = find_balanced(text, obj_open)
    grid_text = text[obj_open : obj_close + 1]
    print(f"Grid({{}}) block: offset {obj_open}..{obj_close}, length {obj_close - obj_open + 1}")

    arrays = {}
    for m in ARRAY_RE.finditer(grid_text):
        arr_name = m.group(1)
        arr_body = m.group(2).strip()
        arrays[arr_name] = (
            [int(x) for x in arr_body.split(",") if x.strip()] if arr_body else []
        )
    print("\n=== Top-level arrays ===")
    for k, v in arrays.items():
        print(f"  {k}: {v}")

    fields: dict[int, dict] = {}
    for m in FIELD_HEAD_RE.finditer(grid_text):
        field_id = int(m.group(1))
        title_raw = m.group(2)
        title = _decode_js_string(title_raw)
        head_pos = m.start()
        values_kw = grid_text.find("values", m.end())
        if values_kw == -1:
            continue
        brace_open = grid_text.index("{", values_kw)
        try:
            brace_close = find_balanced(grid_text, brace_open)
        except ValueError:
            continue
        values_text = grid_text[brace_open + 1 : brace_close]

        values: list[tuple[int, str]] = []
        for vm in VALUE_RE.finditer(values_text):
            vid = int(vm.group(1))
            vtitle = _decode_js_string(vm.group(2))
            values.append((vid, vtitle))

        if field_id in fields and len(fields[field_id]["values"]) >= len(values):
            continue
        fields[field_id] = {"title": title, "values": values, "head_pos": head_pos}

    print(f"\n=== Discovered {len(fields)} fields ===")
    for fid, info in sorted(fields.items()):
        nv = len(info["values"])
        print(f"  field {fid}: '{info['title']}' — {nv} value(s)")
        for vid, vtitle in info["values"][:3]:
            print(f"      {vid}: {vtitle!r}")
        if nv > 3:
            print(f"      ... ({nv - 3} more)")
        if nv > 0:
            last_vid, last_title = info["values"][-1]
            print(f"      [last] {last_vid}: {last_title!r}")
        print()

    print("=== Looking for fuel-related values ===")
    fuel_keywords = ["бенз", "АИ-9", "АИ-92", "АИ-95", "АИ-98", "дизел", "топлив"]
    for fid, info in sorted(fields.items()):
        matches = [
            (vid, title)
            for vid, title in info["values"]
            if any(kw.lower() in title.lower() for kw in fuel_keywords)
        ]
        if matches:
            print(f"  field {fid} '{info['title']}' -> fuel-like values:")
            for vid, title in matches[:20]:
                print(f"      {vid}: {title!r}")
            if len(matches) > 20:
                print(f"      ... ({len(matches) - 20} more)")

    print("\n=== Looking for region-related values (sample) ===")
    region_keywords = ["Москва", "Санкт-Петербург", "Татарстан", "Российская Федерация"]
    for fid, info in sorted(fields.items()):
        if len(info["values"]) < 50:
            continue
        matches = [
            (vid, title)
            for vid, title in info["values"]
            if any(kw in title for kw in region_keywords)
        ]
        if matches:
            print(f"  field {fid} '{info['title']}' (total {len(info['values'])} values) -> region samples:")
            for vid, title in matches[:5]:
                print(f"      {vid}: {title!r}")


if __name__ == "__main__":
    indicator_id = sys.argv[1] if len(sys.argv) > 1 else "31448"
    _, out_path = _resolve_paths(indicator_id)
    buf = io.StringIO()
    saved_stdout = sys.stdout
    sys.stdout = buf
    try:
        main(indicator_id)
    finally:
        sys.stdout = saved_stdout
    out_path.write_text(buf.getvalue(), encoding="utf-8")
    print(f"output written to {out_path}")
