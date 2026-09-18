"""Auth use-cases: register, login, refresh, me, logout."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.api.schemas.auth import (
    AuthResponse,
    LoginRequest,
    MeResponse,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    RegisterRequest,
    UserRead,
)
from app.core.exceptions import ConflictError, UnauthorizedError, ValidationAppError
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.domain.ports import AuthRepository
from app.infrastructure.notifier import PasswordResetNotifier


class AuthService:
    def __init__(self, repo: AuthRepository, notifier: PasswordResetNotifier) -> None:
        self._repo = repo
        self._notifier = notifier

    async def register(self, request: RegisterRequest) -> tuple[AuthResponse, str]:
        if not request.pdn_consent:
            raise ValidationAppError("pdn_consent must be true")
        existing = await self._repo.get_user_by_email(str(request.email))
        if existing is not None:
            raise ConflictError("email already registered")

        user = await self._repo.create_user(
            email=str(request.email),
            password_hash=hash_password(request.password),
            pdn_consent=True,
        )
        auth_response, refresh_raw = await self._issue_tokens(user_id=user.id, email=user.email)
        return auth_response, refresh_raw

    async def login(self, request: LoginRequest) -> tuple[AuthResponse, str]:
        user = await self._repo.get_user_by_email(str(request.email))
        if user is None or not verify_password(request.password, user.password_hash):
            raise UnauthorizedError("invalid email or password")
        if not user.is_active:
            raise UnauthorizedError("user is disabled")
        auth_response, refresh_raw = await self._issue_tokens(user_id=user.id, email=user.email)
        return auth_response, refresh_raw

    async def refresh(self, raw_refresh_token: str | None) -> tuple[AuthResponse, str]:
        if raw_refresh_token is None or raw_refresh_token == "":
            raise UnauthorizedError("refresh token not provided")
        token_hash = hash_refresh_token(raw_refresh_token)
        user = await self._repo.validate_refresh_token(token_hash)
        if user is None:
            raise UnauthorizedError("refresh token is invalid or expired")

        await self._repo.revoke_refresh_token(token_hash)
        auth_response, refresh_raw = await self._issue_tokens(user_id=user.id, email=user.email)
        return auth_response, refresh_raw

    async def logout(self, raw_refresh_token: str | None) -> None:
        if raw_refresh_token:
            await self._repo.revoke_refresh_token(hash_refresh_token(raw_refresh_token))

    async def me(self, user_id: str) -> MeResponse:
        user = await self._repo.get_user_by_id(user_id)
        if user is None:
            raise UnauthorizedError("user not found")
        profile = await self._repo.get_profile(user_id)
        return MeResponse(
            id=user.id,
            email=user.email,
            created_at=user.created_at,
            has_profile=profile is not None,
        )

    async def request_password_reset(self, request: PasswordResetRequest) -> None:
        user = await self._repo.get_user_by_email(request.email)
        # Don't leak whether account exists.
        if user is None:
            return
        raw_token = generate_refresh_token()
        token_hash = hash_refresh_token(raw_token)
        await self._repo.save_password_reset_token(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        await self._notifier.send_reset_token(user.email, raw_token)

    async def confirm_password_reset(self, request: PasswordResetConfirmRequest) -> None:
        token_hash = hash_refresh_token(request.token)
        user = await self._repo.consume_password_reset_token(token_hash)
        if user is None:
            raise ValidationAppError("reset token is invalid or expired")
        await self._repo.update_user_password(user.id, hash_password(request.new_password))
        await self._repo.revoke_all_refresh_tokens_for_user(user.id)

    async def _issue_tokens(self, *, user_id: str, email: str) -> tuple[AuthResponse, str]:
        access_token, expires_in = create_access_token(user_id=user_id, email=email)
        refresh_raw = generate_refresh_token()
        refresh_hash = hash_refresh_token(refresh_raw)
        await self._repo.save_refresh_token(
            user_id=user_id,
            token_hash=refresh_hash,
            expires_at=datetime.now(UTC) + timedelta(days=14),
        )
        user = await self._repo.get_user_by_id(user_id)
        if user is None:
            raise UnauthorizedError("user not found")
        return (
            AuthResponse(
                user=UserRead(id=user.id, email=user.email, created_at=user.created_at),
                access_token=access_token,
                expires_in=expires_in,
            ),
            refresh_raw,
        )


__all__ = ["AuthService"]
