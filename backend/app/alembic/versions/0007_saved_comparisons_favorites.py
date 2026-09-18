from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.rename_table("saved_scenarios", "saved_comparisons")
    op.rename_table("scenario_cars", "saved_comparison_cars")
    op.rename_table(
        "scenario_idempotency_keys",
        "saved_comparison_idempotency_keys",
    )

    op.create_table(
        "favorite_modifications",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("modification_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_favorite_modifications_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["modification_id"],
            ["car_modifications.id"],
            name="fk_favorite_modifications_modification_id_car_modifications",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "modification_id", name="pk_favorite_modifications"),
    )
    op.create_index(
        "ix_favorite_modifications_user_id",
        "favorite_modifications",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_favorite_modifications_modification_id",
        "favorite_modifications",
        ["modification_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_favorite_modifications_modification_id", table_name="favorite_modifications")
    op.drop_index("ix_favorite_modifications_user_id", table_name="favorite_modifications")
    op.drop_table("favorite_modifications")

    op.rename_table(
        "saved_comparison_idempotency_keys",
        "scenario_idempotency_keys",
    )
    op.rename_table("saved_comparison_cars", "scenario_cars")
    op.rename_table("saved_comparisons", "saved_scenarios")
