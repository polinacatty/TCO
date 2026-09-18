"""Auth router"""

from __future__ import annotations

from typing import Literal, cast

from fastapi import APIRouter, Request, Response

from app.api.deps import (
    AuthLoginRateLimitDep,
    AuthPasswordResetRateLimitDep,
    AuthRegisterRateLimitDep,
    AuthServiceDep,
    CurrentUserIdDep,
    SettingsDep,
)
from app.api.schemas.auth import (
    AuthResponse,
    LoginRequest,
    MeResponse,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    RegisterRequest,
)
from app.config import Settings

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(
    request: RegisterRequest,
    service: AuthServiceDep,
    response: Response,
    settings: SettingsDep,
    _: AuthRegisterRateLimitDep,
) -> AuthResponse:
    payload, refresh_token = await service.register(request)
    _set_refresh_cookie(response, refresh_token, settings)
    return payload


@router.post("/login", response_model=AuthResponse)
async def login(
    request: LoginRequest,
    service: AuthServiceDep,
    response: Response,
    settings: SettingsDep,
    _: AuthLoginRateLimitDep,
) -> AuthResponse:
    payload, refresh_token = await service.login(request)
    _set_refresh_cookie(response, refresh_token, settings)
    return payload


@router.post("/refresh", response_model=AuthResponse)
async def refresh(
    http_request: Request,
    service: AuthServiceDep,
    response: Response,
    settings: SettingsDep,
) -> AuthResponse:
    payload, refresh_token = await service.refresh(
        http_request.cookies.get(settings.jwt_refresh_cookie_name)
    )
    _set_refresh_cookie(response, refresh_token, settings)
    return payload


@router.post("/logout", status_code=204)
async def logout(
    http_request: Request, service: AuthServiceDep, response: Response, settings: SettingsDep
) -> None:
    await service.logout(http_request.cookies.get(settings.jwt_refresh_cookie_name))
    response.delete_cookie(
        settings.jwt_refresh_cookie_name,
        path=settings.jwt_refresh_cookie_path,
        domain=settings.jwt_refresh_cookie_domain,
    )
    return None


@router.get("/me", response_model=MeResponse)
async def me(user_id: CurrentUserIdDep, service: AuthServiceDep) -> MeResponse:
    return await service.me(user_id)


@router.post("/password/reset/request", status_code=204)
async def password_reset_request(
    payload: PasswordResetRequest,
    service: AuthServiceDep,
    _: AuthPasswordResetRateLimitDep,
) -> None:
    await service.request_password_reset(payload)
    return None


@router.post("/password/reset/confirm")
async def password_reset_confirm(
    payload: PasswordResetConfirmRequest, service: AuthServiceDep
) -> dict[str, str]:
    await service.confirm_password_reset(payload)
    return {"status": "ok"}


def _set_refresh_cookie(response: Response, refresh_token: str, settings: Settings) -> None:
    samesite: Literal["lax", "strict", "none"] = "strict"
    if settings.jwt_refresh_cookie_samesite in {"lax", "strict", "none"}:
        samesite = cast(
            Literal["lax", "strict", "none"], settings.jwt_refresh_cookie_samesite
        )
    response.set_cookie(
        key=settings.jwt_refresh_cookie_name,
        value=refresh_token,
        httponly=True,
        samesite=samesite,
        secure=settings.jwt_refresh_cookie_secure,
        path=settings.jwt_refresh_cookie_path,
        domain=settings.jwt_refresh_cookie_domain,
        max_age=settings.jwt_refresh_ttl_days * 24 * 60 * 60,
    )

