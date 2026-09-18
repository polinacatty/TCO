"""ORM models for saved comparisons."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, PrimaryKeyConstraint, SmallInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.infrastructure.orm.base import Base


class SavedScenario(Base):
    __tablename__ = "saved_comparisons"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    signature: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    __table_args__ = (UniqueConstraint("user_id", "signature", name="uq_saved_comparisons_user_signature"),)


class ScenarioCar(Base):
    __tablename__ = "saved_comparison_cars"

    scenario_id: Mapped[str] = mapped_column(
        ForeignKey("saved_comparisons.id", ondelete="CASCADE"),
        nullable=False,
    )
    modification_id: Mapped[int] = mapped_column(
        ForeignKey("car_modifications.id", ondelete="RESTRICT"),
        nullable=False,
    )
    order_index: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    __table_args__ = (
        PrimaryKeyConstraint("scenario_id", "modification_id", name="pk_scenario_cars"),
    )
__all__ = ["SavedScenario", "ScenarioCar"]
