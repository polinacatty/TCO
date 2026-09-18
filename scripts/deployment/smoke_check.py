from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request


def fetch(url: str) -> tuple[int, str]:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=15) as response:
        body = response.read().decode("utf-8", errors="replace")
        return response.status, body


def check_http(name: str, url: str, expected_status: int = 200) -> bool:
    try:
        status, _ = fetch(url)
    except urllib.error.URLError as exc:
        print(f"[FAIL] {name}: {url} unreachable ({exc})")
        return False
    if status != expected_status:
        print(f"[FAIL] {name}: expected {expected_status}, got {status}")
        return False
    print(f"[OK]   {name}: {url} -> {status}")
    return True


def check_json_key(name: str, url: str, key: str) -> bool:
    try:
        status, body = fetch(url)
        payload = json.loads(body)
    except Exception as exc:  # noqa: BLE001 - smoke script, broad error is fine
        print(f"[FAIL] {name}: cannot parse JSON ({exc})")
        return False

    if status != 200:
        print(f"[FAIL] {name}: expected 200, got {status}")
        return False
    if key not in payload:
        print(f"[FAIL] {name}: key '{key}' not found")
        return False
    print(f"[OK]   {name}: key '{key}' present")
    return True


def main() -> int:
    backend = "http://localhost:8000"
    frontend = "http://localhost:4173"

    checks = [
        check_http("frontend-home", frontend),
        check_json_key("backend-version", f"{backend}/version", "version"),
        check_http("backend-live", f"{backend}/health/live"),
        check_http("backend-ready", f"{backend}/health/ready"),
        check_http("backend-docs", f"{backend}/docs"),
        check_http("catalog-makes", f"{backend}/api/catalog/makes?q=to"),
    ]

    if all(checks):
        print("\nSmoke check passed.")
        return 0

    print("\nSmoke check failed.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
