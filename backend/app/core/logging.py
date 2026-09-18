"""Structured logging setup (structlog поверх stdlib).

Все логи — JSON; в dev добавляется человекочитаемый renderer.
Request-id прокидывается через contextvar в middleware.
"""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar

import structlog
from structlog.types import EventDict, Processor

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def _add_request_id(_: object, __: str, event_dict: EventDict) -> EventDict:
    rid = request_id_var.get()
    if rid is not None:
        event_dict.setdefault("request_id", rid)
    return event_dict


def configure_logging(level: str = "INFO", *, json_logs: bool = True) -> None:
    """Настроить stdlib logging + structlog единым форматом."""
    log_level = getattr(logging, level.upper(), logging.INFO)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    pre_chain: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        _add_request_id,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    renderer: Processor = (
        structlog.processors.JSONRenderer()
        if json_logs
        else structlog.dev.ConsoleRenderer(colors=False)
    )

    structlog.configure(
        processors=[*pre_chain, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    logger: structlog.stdlib.BoundLogger = structlog.get_logger(name)
    return logger
