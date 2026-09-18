"""RFC 7807 Problem Details + центральные exception handlers.

Все ошибки наружу:

    {
      "type":   "https://tco.example.ru/errors/validation",
      "title":  "Validation error",
      "status": 422,
      "detail": "...",
      "errors": [...],
      "request_id": "..."
    }
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger, request_id_var

log = get_logger(__name__)

_PROBLEM_BASE = "https://tco.example.ru/errors"


class AppError(Exception):
    """Базовая бизнес-ошибка приложения.

    Использовать в services/domain вместо HTTPException, чтобы domain не
    зависел от FastAPI. Перевод в HTTP-ответ — в хендлере ниже.
    """

    status_code: int = 500
    code: str = "internal"
    title: str = "Internal error"

    def __init__(self, detail: str, *, errors: list[dict[str, Any]] | None = None):
        super().__init__(detail)
        self.detail = detail
        self.errors = errors or []


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"
    title = "Resource not found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"
    title = "Conflict"


class UnauthorizedError(AppError):
    status_code = 401
    code = "unauthorized"
    title = "Unauthorized"


class TooManyRequestsError(AppError):
    status_code = 429
    code = "rate_limited"
    title = "Too many requests"


class ValidationAppError(AppError):
    status_code = 422
    code = "validation"
    title = "Validation error"


def _problem(
    status: int,
    code: str,
    title: str,
    detail: str,
    errors: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "type": f"{_PROBLEM_BASE}/{code}",
        "title": title,
        "status": status,
        "detail": detail,
        "request_id": request_id_var.get(),
    }
    if errors:
        body["errors"] = errors
    return body


def register_exception_handlers(app: FastAPI) -> None:
    """Регистрация всех handlers — вызывается из ``main.create_app``."""

    @app.exception_handler(AppError)
    async def _app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        log.warning("app_error", code=exc.code, detail=exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content=_problem(exc.status_code, exc.code, exc.title, exc.detail, exc.errors),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {
                "field": ".".join(str(p) for p in err["loc"][1:]),
                "code": err["type"],
                "message": err["msg"],
            }
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=_problem(422, "validation", "Validation error", "request body invalid", errors),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_problem(exc.status_code, "http", exc.detail or "HTTP error", str(exc.detail)),
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled", error=str(exc))
        return JSONResponse(
            status_code=500,
            content=_problem(500, "internal", "Internal error", "unexpected server error"),
        )
