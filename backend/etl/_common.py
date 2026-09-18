from __future__ import annotations

import csv
import logging
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from sqlalchemy import Connection, Engine, create_engine, text

from app.config import get_settings

logger = logging.getLogger("etl")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)-5s | %(name)s | %(message)s")
    )
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


# --------------------------------------------------------------------------- #
# Engine                                                                      #
# --------------------------------------------------------------------------- #


def get_sync_engine() -> Engine:

    settings = get_settings()
    url = settings.database_url
    if url.startswith("postgresql+asyncpg://"):
        url = "postgresql+psycopg://" + url.removeprefix("postgresql+asyncpg://")
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return create_engine(url, future=True)


# --------------------------------------------------------------------------- #
# CSV loader                                                                  #
# --------------------------------------------------------------------------- #


def read_csv_rows(path: Path) -> list[dict[str, str]]:

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def _none_if_empty(value: str | None) -> str | None:
    if value is None:
        return None
    v = value.strip()
    return v if v else None


def coerce(
    rows: list[dict[str, str]],
    *,
    int_cols: tuple[str, ...] = (),
    float_cols: tuple[str, ...] = (),
    bool_cols: tuple[str, ...] = (),
    date_cols: tuple[str, ...] = (),
    nullable: tuple[str, ...] = (),
) -> list[dict[str, Any]]:

    out: list[dict[str, Any]] = []
    for r in rows:
        d: dict[str, Any] = {}
        for k, v in r.items():
            raw = _none_if_empty(v)
            if raw is None:
                if k in nullable:
                    d[k] = None
                    continue
                if k in int_cols or k in float_cols:
                    # пустое значение в non-nullable числе — ошибка
                    raise ValueError(f"empty value for non-nullable column {k!r}")
                d[k] = None
                continue
            if k in int_cols:
                d[k] = int(float(raw))  # допускаем '100.0' для int-столбцов
            elif k in float_cols:
                d[k] = float(raw)
            elif k in bool_cols:
                d[k] = raw.lower() in {"true", "1", "yes"}
            elif k in date_cols:
                d[k] = raw  # пусть PG парсит ISO-строку
            else:
                d[k] = raw
        out.append(d)
    return out


# --------------------------------------------------------------------------- #
# Batch insert                                                                #
# --------------------------------------------------------------------------- #


def truncate(conn: Connection, table: str) -> None:

    conn.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE"))


def insert_rows(
    conn: Connection,
    table: str,
    columns: Iterable[str],
    rows: Sequence[Mapping[str, Any]],
) -> int:

    cols = list(columns)
    if not rows:
        return 0
    placeholders = ", ".join(f":{c}" for c in cols)
    col_list = ", ".join(cols)
    stmt = text(f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})")
    conn.execute(stmt, [dict(r) for r in rows])
    return len(rows)


# --------------------------------------------------------------------------- #
# Paths                                                                       #
# --------------------------------------------------------------------------- #


def repo_root() -> Path:

    return Path(__file__).resolve().parents[2]


def seed_dir() -> Path:
    return repo_root() / "ml" / "data" / "seed"


def processed_dir() -> Path:
    return repo_root() / "ml" / "data" / "processed"


def sarima_dir() -> Path:

    return repo_root() / "ml" / "models" / "fuel_sarima"


__all__ = [
    "coerce",
    "get_sync_engine",
    "insert_rows",
    "logger",
    "processed_dir",
    "read_csv_rows",
    "repo_root",
    "sarima_dir",
    "seed_dir",
    "truncate",
]
