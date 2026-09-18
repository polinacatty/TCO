from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "saved_scenarios",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("profile_snapshot", sa.JSON(), nullable=False),
        sa.Column("horizon_years", sa.SmallInteger(), nullable=False),
        sa.Column("options_json", sa.JSON(), nullable=False),
        sa.Column("summary_total_tco_rub", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_saved_scenarios_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_saved_scenarios"),
    )
    op.create_index("ix_saved_scenarios_user_id", "saved_scenarios", ["user_id"], unique=False)

    op.create_table(
        "scenario_cars",
        sa.Column("scenario_id", sa.String(length=36), nullable=False),
        sa.Column("modification_id", sa.Integer(), nullable=False),
        sa.Column("order_index", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("custom_purchase_price_rub", sa.Integer(), nullable=True),
        sa.Column("age_at_purchase_months", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(
            ["scenario_id"],
            ["saved_scenarios.id"],
            name="fk_scenario_cars_scenario_id_saved_scenarios",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["modification_id"],
            ["car_modifications.id"],
            name="fk_scenario_cars_modification_id_car_modifications",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("scenario_id", "modification_id", name="pk_scenario_cars"),
    )
    op.create_index(
        "ix_scenario_cars_scenario_id", "scenario_cars", ["scenario_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_scenario_cars_scenario_id", table_name="scenario_cars")
    op.drop_table("scenario_cars")
    op.drop_index("ix_saved_scenarios_user_id", table_name="saved_scenarios")
    op.drop_table("saved_scenarios")
