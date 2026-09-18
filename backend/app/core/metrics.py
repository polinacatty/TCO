"""In-process Prometheus-like metrics registry."""

from __future__ import annotations

from collections import defaultdict
from threading import Lock


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = Lock()
        self._requests_total: dict[tuple[str, str, int], int] = defaultdict(int)
        self._duration_buckets: dict[tuple[str, str, str], int] = defaultdict(int)
        self._rate_limited_total: dict[str, int] = defaultdict(int)
        self._duration_sum: dict[tuple[str, str], float] = defaultdict(float)
        self._duration_count: dict[tuple[str, str], int] = defaultdict(int)
        self._service_calls_total: dict[tuple[str, str], int] = defaultdict(int)
        self._service_duration_ms_sum: dict[str, float] = defaultdict(float)
        self._service_duration_ms_count: dict[str, int] = defaultdict(int)
        self._bucket_edges = (5.0, 10.0, 25.0, 50.0, 100.0, 250.0, 500.0, 1000.0, 2500.0)

    def observe_http(self, *, method: str, path: str, status_code: int, duration_ms: float) -> None:
        with self._lock:
            m = method.upper()
            p = path
            self._requests_total[(m, p, status_code)] += 1
            self._duration_sum[(m, p)] += duration_ms
            self._duration_count[(m, p)] += 1
            bucket = self._bucket_key(duration_ms)
            self._duration_buckets[(m, p, bucket)] += 1

    def increment_rate_limited(self, action: str) -> None:
        with self._lock:
            self._rate_limited_total[action] += 1

    def observe_service(self, *, operation: str, success: bool, duration_ms: float) -> None:
        with self._lock:
            status = "ok" if success else "error"
            self._service_calls_total[(operation, status)] += 1
            self._service_duration_ms_sum[operation] += duration_ms
            self._service_duration_ms_count[operation] += 1

    def render_prometheus(self) -> str:
        lines: list[str] = [
            "# HELP http_requests_total Total HTTP requests",
            "# TYPE http_requests_total counter",
        ]
        with self._lock:
            for (method, path, status), req_total in sorted(self._requests_total.items()):
                lines.append(
                    f'http_requests_total{{method="{_esc(method)}",path="{_esc(path)}",'
                    f'status="{status}"}} {req_total}'
                )

            lines.extend(
                [
                    "# HELP http_request_duration_ms_bucket Request duration buckets in milliseconds",
                    "# TYPE http_request_duration_ms_bucket counter",
                ]
            )
            for (method, path, bucket), bucket_count in sorted(self._duration_buckets.items()):
                lines.append(
                    f'http_request_duration_ms_bucket{{method="{_esc(method)}",'
                    f'path="{_esc(path)}",le="{bucket}"}} {bucket_count}'
                )
            for (method, path), count_total in sorted(self._duration_count.items()):
                lines.append(
                    f'http_request_duration_ms_bucket{{method="{_esc(method)}",'
                    f'path="{_esc(path)}",le="+Inf"}} {count_total}'
                )

            lines.extend(
                [
                    "# HELP http_request_duration_ms_sum Sum of request durations in milliseconds",
                    "# TYPE http_request_duration_ms_sum counter",
                ]
            )
            for (method, path), duration_sum in sorted(self._duration_sum.items()):
                lines.append(
                    f'http_request_duration_ms_sum{{method="{_esc(method)}",'
                    f'path="{_esc(path)}"}} {duration_sum:.3f}'
                )

            lines.extend(
                [
                    "# HELP auth_rate_limited_total Total rate-limited auth actions",
                    "# TYPE auth_rate_limited_total counter",
                ]
            )
            for action, rate_limited in sorted(self._rate_limited_total.items()):
                lines.append(
                    f'auth_rate_limited_total{{action="{_esc(action)}"}} {rate_limited}'
                )

            lines.extend(
                [
                    "# HELP service_calls_total Total service calls grouped by operation and status",
                    "# TYPE service_calls_total counter",
                ]
            )
            for (operation, status_label), call_count in sorted(self._service_calls_total.items()):
                lines.append(
                    f'service_calls_total{{operation="{_esc(operation)}",status="{_esc(status_label)}"}} {call_count}'
                )

            lines.extend(
                [
                    "# HELP service_duration_ms_sum Sum of service call durations in milliseconds",
                    "# TYPE service_duration_ms_sum counter",
                ]
            )
            for operation, duration_sum in sorted(self._service_duration_ms_sum.items()):
                lines.append(
                    f'service_duration_ms_sum{{operation="{_esc(operation)}"}} {duration_sum:.3f}'
                )

            lines.extend(
                [
                    "# HELP service_duration_ms_count Total number of service calls by operation",
                    "# TYPE service_duration_ms_count counter",
                ]
            )
            for operation, count_total in sorted(self._service_duration_ms_count.items()):
                lines.append(
                    f'service_duration_ms_count{{operation="{_esc(operation)}"}} {count_total}'
                )

        return "\n".join(lines) + "\n"

    def reset(self) -> None:
        with self._lock:
            self._requests_total.clear()
            self._duration_buckets.clear()
            self._duration_sum.clear()
            self._duration_count.clear()
            self._rate_limited_total.clear()
            self._service_calls_total.clear()
            self._service_duration_ms_sum.clear()
            self._service_duration_ms_count.clear()

    def _bucket_key(self, duration_ms: float) -> str:
        for edge in self._bucket_edges:
            if duration_ms <= edge:
                return f"{edge:g}"
        return "+Inf"


def _esc(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


metrics_registry = MetricsRegistry()


__all__ = ["MetricsRegistry", "metrics_registry"]
