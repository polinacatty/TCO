"""FastAPI dependency factories shared across routers."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.auth_service import AuthService
from app.application.catalog_service import CatalogService
from app.application.favorites_service import FavoritesService
from app.application.profile_service import ProfileService
from app.application.recommendation_service import RecommendationService
from app.application.scenario_service import ScenarioService
from app.application.tco_service import TcoService
from app.config import Settings, get_settings
from app.core.exceptions import TooManyRequestsError
from app.core.metrics import metrics_registry
from app.core.rate_limit import RateLimitRule, rate_limiter
from app.core.security import decode_access_token
from app.domain.tco.calculator import TcoCalculator
from app.infrastructure.db import get_session
from app.infrastructure.notifier import PasswordResetNotifier, build_password_reset_notifier
from app.repositories.auth import SqlAuthRepository
from app.repositories.catalog import SqlCatalogRepository
from app.repositories.context_builder import TcoContextBuilder
from app.repositories.fuel import SqlFuelRepository
from app.repositories.pricing import SqlPricingRepository
from app.repositories.scenario import SqlScenarioRepository

SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_catalog_repository(session: SessionDep) -> SqlCatalogRepository:
    return SqlCatalogRepository(session)


def get_pricing_repository(session: SessionDep) -> SqlPricingRepository:
    return SqlPricingRepository(session)


def get_fuel_repository(session: SessionDep) -> SqlFuelRepository:
    return SqlFuelRepository(session)


def get_auth_repository(session: SessionDep) -> SqlAuthRepository:
    return SqlAuthRepository(session)


def get_scenario_repository(session: SessionDep) -> SqlScenarioRepository:
    return SqlScenarioRepository(session)


CatalogRepoDep = Annotated[SqlCatalogRepository, Depends(get_catalog_repository)]
PricingRepoDep = Annotated[SqlPricingRepository, Depends(get_pricing_repository)]
FuelRepoDep = Annotated[SqlFuelRepository, Depends(get_fuel_repository)]
AuthRepoDep = Annotated[SqlAuthRepository, Depends(get_auth_repository)]
ScenarioRepoDep = Annotated[SqlScenarioRepository, Depends(get_scenario_repository)]


def get_tco_context_builder(
    catalog: CatalogRepoDep,
    pricing: PricingRepoDep,
    fuel: FuelRepoDep,
) -> TcoContextBuilder:
    return TcoContextBuilder(catalog=catalog, pricing=pricing, fuel=fuel)


@lru_cache(maxsize=1)
def _calculator_singleton() -> TcoCalculator:
    """Stateless calculator — safe to share across requests."""
    return TcoCalculator()


def get_tco_calculator() -> TcoCalculator:
    return _calculator_singleton()


def get_catalog_service(catalog: CatalogRepoDep) -> CatalogService:
    return CatalogService(catalog)


def get_tco_service(
    builder: Annotated[TcoContextBuilder, Depends(get_tco_context_builder)],
    calculator: Annotated[TcoCalculator, Depends(get_tco_calculator)],
) -> TcoService:
    return TcoService(builder, calculator)


def get_recommendation_service(
    catalog: CatalogRepoDep,
    builder: Annotated[TcoContextBuilder, Depends(get_tco_context_builder)],
    calculator: Annotated[TcoCalculator, Depends(get_tco_calculator)],
) -> RecommendationService:
    return RecommendationService(catalog=catalog, context_builder=builder, calculator=calculator)


@lru_cache(maxsize=1)
def _password_reset_notifier_singleton() -> PasswordResetNotifier:
    return build_password_reset_notifier(get_settings())


def get_password_reset_notifier() -> PasswordResetNotifier:
    return _password_reset_notifier_singleton()


def get_auth_service(
    repo: AuthRepoDep,
    notifier: Annotated[PasswordResetNotifier, Depends(get_password_reset_notifier)],
) -> AuthService:
    return AuthService(repo, notifier)


def get_profile_service(repo: AuthRepoDep) -> ProfileService:
    return ProfileService(repo)


def get_favorites_service(
    auth_repo: AuthRepoDep,
    catalog_repo: CatalogRepoDep,
) -> FavoritesService:
    return FavoritesService(auth_repo=auth_repo, catalog_repo=catalog_repo)


def get_scenario_service(
    repo: ScenarioRepoDep,
    builder: Annotated[TcoContextBuilder, Depends(get_tco_context_builder)],
    calculator: Annotated[TcoCalculator, Depends(get_tco_calculator)],
) -> ScenarioService:
    return ScenarioService(repo=repo, context_builder=builder, calculator=calculator)


_bearer = HTTPBearer(auto_error=False)


def get_current_user_id(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> str:
    from app.core.exceptions import UnauthorizedError, ValidationAppError

    if credentials is None:
        raise UnauthorizedError("Authorization header is required")
    try:
        payload = decode_access_token(credentials.credentials)
    except ValidationAppError as exc:
        raise UnauthorizedError("invalid access token") from exc
    user_id = payload.get("sub")
    if not isinstance(user_id, str) or user_id == "":
        raise UnauthorizedError("invalid access token subject")
    return user_id


def _rate_limit_key(request: Request, *, action: str) -> str:
    client_ip = request.client.host if request.client is not None else "unknown"
    return f"{action}:{client_ip}"


def _check_rate_limit(request: Request, *, action: str, rule: RateLimitRule) -> None:
    if rate_limiter.allow(_rate_limit_key(request, action=action), rule):
        return
    metrics_registry.increment_rate_limited(action)
    raise TooManyRequestsError(f"rate limit exceeded for {action}")


def auth_login_rate_limit(request: Request, settings: SettingsDep) -> None:
    _check_rate_limit(
        request,
        action="auth.login",
        rule=RateLimitRule(
            count=settings.auth_login_rate_limit_count,
            window_seconds=settings.auth_login_rate_limit_window_sec,
        ),
    )


def auth_register_rate_limit(request: Request, settings: SettingsDep) -> None:
    _check_rate_limit(
        request,
        action="auth.register",
        rule=RateLimitRule(
            count=settings.auth_register_rate_limit_count,
            window_seconds=settings.auth_register_rate_limit_window_sec,
        ),
    )


def auth_password_reset_rate_limit(request: Request, settings: SettingsDep) -> None:
    _check_rate_limit(
        request,
        action="auth.password_reset",
        rule=RateLimitRule(
            count=settings.auth_password_reset_rate_limit_count,
            window_seconds=settings.auth_password_reset_rate_limit_window_sec,
        ),
    )


CatalogServiceDep = Annotated[CatalogService, Depends(get_catalog_service)]
TcoServiceDep = Annotated[TcoService, Depends(get_tco_service)]
RecommendationServiceDep = Annotated[
    RecommendationService, Depends(get_recommendation_service)
]
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
ProfileServiceDep = Annotated[ProfileService, Depends(get_profile_service)]
FavoritesServiceDep = Annotated[FavoritesService, Depends(get_favorites_service)]
ScenarioServiceDep = Annotated[ScenarioService, Depends(get_scenario_service)]
CurrentUserIdDep = Annotated[str, Depends(get_current_user_id)]
AuthLoginRateLimitDep = Annotated[None, Depends(auth_login_rate_limit)]
AuthRegisterRateLimitDep = Annotated[None, Depends(auth_register_rate_limit)]
AuthPasswordResetRateLimitDep = Annotated[
    None, Depends(auth_password_reset_rate_limit)
]


__all__ = [
    "SessionDep",
    "SettingsDep",
    "CatalogRepoDep",
    "PricingRepoDep",
    "FuelRepoDep",
    "AuthRepoDep",
    "ScenarioRepoDep",
    "CatalogServiceDep",
    "TcoServiceDep",
    "RecommendationServiceDep",
    "AuthServiceDep",
    "ProfileServiceDep",
    "FavoritesServiceDep",
    "ScenarioServiceDep",
    "CurrentUserIdDep",
    "AuthLoginRateLimitDep",
    "AuthRegisterRateLimitDep",
    "AuthPasswordResetRateLimitDep",
    "get_catalog_service",
    "get_tco_service",
    "get_recommendation_service",
    "get_auth_repository",
    "get_scenario_repository",
    "get_auth_service",
    "get_password_reset_notifier",
    "get_profile_service",
    "get_favorites_service",
    "get_scenario_service",
    "get_current_user_id",
    "auth_login_rate_limit",
    "auth_register_rate_limit",
    "auth_password_reset_rate_limit",
]
