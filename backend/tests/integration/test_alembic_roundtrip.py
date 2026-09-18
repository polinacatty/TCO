from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

pytestmark = pytest.mark.integration

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _make_cfg(db_url: str) -> Config:
    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "app" / "alembic"))
    return cfg


def test_upgrade_and_downgrade_roundtrip(tmp_path: Path) -> None:

    db_path = tmp_path / "rt.db"
    db_url = f"sqlite+aiosqlite:///{db_path.as_posix()}"
    sync_url = f"sqlite:///{db_path.as_posix()}"

    cfg = _make_cfg(db_url)

    command.upgrade(cfg, "head")

    engine = create_engine(sync_url)
    insp = inspect(engine)
    tables_after_upgrade = set(insp.get_table_names())
    assert "alembic_version" in tables_after_upgrade
    assert "fuel_price_forecast" in tables_after_upgrade
    assert "ml_models_registry" in tables_after_upgrade
    assert len(tables_after_upgrade - {"alembic_version"}) == 35
    engine.dispose()

    command.downgrade(cfg, "base")

    engine = create_engine(sync_url)
    insp = inspect(engine)
    tables_after_downgrade = set(insp.get_table_names())
    assert tables_after_downgrade <= {"alembic_version"}
    engine.dispose()

    command.upgrade(cfg, "head")
    engine = create_engine(sync_url)
    insp = inspect(engine)
    tables_after_reupgrade = set(insp.get_table_names())
    assert (
        len(tables_after_reupgrade - {"alembic_version"}) == 35
    ), tables_after_reupgrade
    engine.dispose()
