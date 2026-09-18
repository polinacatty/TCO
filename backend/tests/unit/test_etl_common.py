from __future__ import annotations

import pytest

from etl._common import coerce

pytestmark = pytest.mark.unit


def test_coerce_basic_types() -> None:
    rows = [
        {"id": "1", "name": "Lada", "ratio": "0.42", "ok": "true"},
        {"id": "2", "name": "Kia",  "ratio": "1.00", "ok": "false"},
    ]
    out = coerce(
        rows,
        int_cols=("id",),
        float_cols=("ratio",),
        bool_cols=("ok",),
    )
    assert out == [
        {"id": 1, "name": "Lada", "ratio": 0.42, "ok": True},
        {"id": 2, "name": "Kia", "ratio": 1.0, "ok": False},
    ]


def test_coerce_empty_string_to_none_for_nullable() -> None:
    rows = [{"id": "1", "extra": ""}]
    out = coerce(rows, int_cols=("id",), nullable=("extra",))
    assert out[0]["extra"] is None


def test_coerce_empty_string_for_non_nullable_numeric_raises() -> None:
    rows = [{"x": ""}]
    with pytest.raises(ValueError):
        coerce(rows, int_cols=("x",))


def test_coerce_accepts_float_string_for_int_column() -> None:
    rows = [{"id": "100.0"}]
    out = coerce(rows, int_cols=("id",))
    assert out[0]["id"] == 100
    assert isinstance(out[0]["id"], int)


def test_coerce_strips_whitespace_around_values() -> None:
    rows = [{"x": "  hello  ", "y": "  3.14 "}]
    out = coerce(rows, float_cols=("y",))
    assert out[0] == {"x": "hello", "y": 3.14}
