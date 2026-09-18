from __future__ import annotations

from fastapi.testclient import TestClient

from tests.support.stubs import StubAuthRepository, StubPasswordResetNotifier


def test_register_login_refresh_me_flow(api_client: TestClient) -> None:
    register = api_client.post(
        "/api/auth/register",
        json={
            "email": "user@example.com",
            "password": "StrongPass123!",
            "pdn_consent": True,
        },
    )
    assert register.status_code == 201, register.text
    body = register.json()
    assert body["user"]["email"] == "user@example.com"
    assert body["access_token"]
    assert "refresh_token=" in (register.headers.get("set-cookie") or "")

    me = api_client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["has_profile"] is False

    login = api_client.post(
        "/api/auth/login",
        json={"email": "user@example.com", "password": "StrongPass123!"},
    )
    assert login.status_code == 200, login.text
    refresh = api_client.post("/api/auth/refresh")
    assert refresh.status_code == 200, refresh.text


def test_register_duplicate_email_409(api_client: TestClient) -> None:
    payload = {
        "email": "dupe@example.com",
        "password": "StrongPass123!",
        "pdn_consent": True,
    }
    first = api_client.post("/api/auth/register", json=payload)
    second = api_client.post("/api/auth/register", json=payload)
    assert first.status_code == 201
    assert second.status_code == 409


def test_login_invalid_password_401(api_client: TestClient) -> None:
    api_client.post(
        "/api/auth/register",
        json={
            "email": "badpass@example.com",
            "password": "StrongPass123!",
            "pdn_consent": True,
        },
    )
    resp = api_client.post(
        "/api/auth/login",
        json={"email": "badpass@example.com", "password": "wrongpass123"},
    )
    assert resp.status_code == 401


def test_password_reset_request_and_confirm(
    api_client: TestClient,
    stub_auth: StubAuthRepository,
    stub_password_reset_notifier: StubPasswordResetNotifier,
) -> None:
    api_client.post(
        "/api/auth/register",
        json={
            "email": "reset@example.com",
            "password": "StrongPass123!",
            "pdn_consent": True,
        },
    )
    req = api_client.post(
        "/api/auth/password/reset/request", json={"email": "reset@example.com"}
    )
    assert req.status_code == 204
    token = stub_password_reset_notifier.last_token_by_email.get("reset@example.com")
    assert isinstance(token, str)

    confirm = api_client.post(
        "/api/auth/password/reset/confirm",
        json={"token": token, "new_password": "EvenStrongerPass456!"},
    )
    assert confirm.status_code == 200, confirm.text

    old_login = api_client.post(
        "/api/auth/login",
        json={"email": "reset@example.com", "password": "StrongPass123!"},
    )
    assert old_login.status_code == 401
    new_login = api_client.post(
        "/api/auth/login",
        json={"email": "reset@example.com", "password": "EvenStrongerPass456!"},
    )
    assert new_login.status_code == 200


def test_login_rate_limit_429(api_client: TestClient) -> None:
    api_client.post(
        "/api/auth/register",
        json={
            "email": "ratelimit@example.com",
            "password": "StrongPass123!",
            "pdn_consent": True,
        },
    )
    for _ in range(5):
        bad = api_client.post(
            "/api/auth/login",
            json={"email": "ratelimit@example.com", "password": "wrongpass123"},
        )
        assert bad.status_code in (401, 429)
    blocked = api_client.post(
        "/api/auth/login",
        json={"email": "ratelimit@example.com", "password": "wrongpass123"},
    )
    assert blocked.status_code == 429

