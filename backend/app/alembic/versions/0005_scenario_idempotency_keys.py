from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scenario_idempotency_keys",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("scenario_id", sa.String(length=36), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_scenario_idempotency_keys_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["scenario_id"],
            ["saved_scenarios.id"],
            name="fk_scenario_idempotency_keys_scenario_id_saved_scenarios",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "idempotency_key", name="pk_scenario_idempotency_keys"),
    )


def downgrade() -> None:
    op.drop_table("scenario_idempotency_keys")
