from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.config import get_settings
from app.infrastructure.orm import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _get_url() -> str:
    """URL подключения: сперва из ``-x url=`` или ``sqlalchemy.url`` в cfg,
    иначе — из настроек приложения (``DATABASE_URL`` в env)."""

    x_args = context.get_x_argument(as_dictionary=True) or {}
    cli_url = x_args.get("url")
    if cli_url:
        return str(cli_url)

    cfg_url = config.get_main_option("sqlalchemy.url")
    if cfg_url:
        return cfg_url

    return get_settings().database_url


def run_migrations_offline() -> None:
    """Offline mode: вывод SQL без подключения к БД."""

    context.configure(
        url=_get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        compare_server_default=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def _run_async_migrations() -> None:
    cfg = config.get_section(config.config_ini_section) or {}
    cfg["sqlalchemy.url"] = _get_url()

    engine = async_engine_from_config(
        cfg,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with engine.connect() as connection:
        await connection.run_sync(_do_run_migrations)

    await engine.dispose()


def run_migrations_online() -> None:
    asyncio.run(_run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
