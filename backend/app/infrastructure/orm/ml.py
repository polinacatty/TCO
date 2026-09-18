"""ML registries ORM."""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Numeric,
    PrimaryKeyConstraint,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.orm.base import Base


class MlModelRegistry(Base):
    """Каталог обученных моделей."""

    __tablename__ = "ml_models_registry"

    model_type: Mapped[str] = mapped_column(String(32), nullable=False)
    region_id: Mapped[int] = mapped_column(
        ForeignKey("regions.id", ondelete="RESTRICT"), nullable=False
    )
    region_name: Mapped[str] = mapped_column(String(128), nullable=False)
    fuel_type: Mapped[str] = mapped_column(String(16), nullable=False)
    version: Mapped[str] = mapped_column(String(16), nullable=False)

    artifact_path: Mapped[str] = mapped_column(Text, nullable=False)

    train_mape_pct: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    train_rmse: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    train_mae: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    train_coverage_95_pct: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)

    train_window_start: Mapped[str | None] = mapped_column(String(10), nullable=True)
    train_window_end: Mapped[str | None] = mapped_column(String(10), nullable=True)
    test_window_start: Mapped[str | None] = mapped_column(String(10), nullable=True)
    test_window_end: Mapped[str | None] = mapped_column(String(10), nullable=True)

    order_p: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    order_d: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    order_q: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    seasonal_p: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    seasonal_d: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    seasonal_q: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    seasonal_period: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    aic: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    bic: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    fallback: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    fit_seconds: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    fitted_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")

    __table_args__ = (
        PrimaryKeyConstraint(
            "model_type", "region_id", "fuel_type", "version", name="pk_ml_models_registry"
        ),
    )


class MlStrategyRegistry(Base):
    """Реестр стратегий подбора."""

    __tablename__ = "ml_strategies_registry"

    model_type: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[str] = mapped_column(String(16), nullable=False)
    algorithm: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    criteria_count: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    has_artifact: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    artifact_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    ndcg_at_10_median: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    diversity_at_10_median: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    coverage_pct: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    stability_median: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)

    target_ndcg: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    target_diversity: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    target_coverage_pct: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    target_stability: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)

    validator_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    methodology_doc: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_set_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_validated_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")

    __table_args__ = (
        PrimaryKeyConstraint("model_type", "version", name="pk_ml_strategies_registry"),
    )


__all__ = ["MlModelRegistry", "MlStrategyRegistry"]
