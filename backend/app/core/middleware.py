"""HTTP middleware: request-id + access log."""

from __future__ import annotations

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import get_logger, request_id_var
from app.core.metrics import metrics_registry

log = get_logger(__name__)

_HEADER = "x-request-id"


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Прокинуть/сгенерировать X-Request-ID и положить в contextvar."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        rid = request.headers.get(_HEADER) or uuid.uuid4().hex
        token = request_id_var.set(rid)
        start = time.perf_counter()
        response: Response | None = None
        try:
            response = await call_next(request)
            return response
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            status_code = response.status_code if response is not None else 500
            log.info(
                "http_request",
                method=request.method,
                path=request.url.path,
                status_code=status_code,
                duration_ms=round(elapsed_ms, 2),
            )
            metrics_registry.observe_http(
                method=request.method,
                path=request.url.path,
                status_code=status_code,
                duration_ms=elapsed_ms,
            )
            request_id_var.reset(token)
            if response is not None:
                response.headers[_HEADER] = rid
