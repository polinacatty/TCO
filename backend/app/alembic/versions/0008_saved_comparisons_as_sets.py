from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "saved_comparisons",
        sa.Column("signature", sa.String(length=255), nullable=True),
    )

    op.execute(
        """
        UPDATE saved_comparisons sc
        SET signature = sub.signature
        FROM (
            SELECT
                scenario_id,
                string_agg(modification_id::text, ',' ORDER BY modification_id) AS signature
            FROM saved_comparison_cars
            GROUP BY scenario_id
        ) AS sub
        WHERE sc.id = sub.scenario_id
        """
    )
    op.execute("UPDATE saved_comparisons SET signature = id WHERE signature IS NULL")

    with op.batch_alter_table("saved_comparisons") as batch:
        batch.alter_column("signature", nullable=False)
        batch.drop_column("profile_snapshot")
        batch.drop_column("horizon_years")
        batch.drop_column("options_json")
        batch.drop_column("summary_total_tco_rub")
        batch.drop_column("updated_at")
        batch.drop_column("deleted_at")

    with op.batch_alter_table("saved_comparison_cars") as batch:
        batch.drop_column("custom_purchase_price_rub")
        batch.drop_column("age_at_purchase_months")

    op.execute(
        """
        DELETE FROM saved_comparisons
        WHERE id IN (
            SELECT id
            FROM (
                SELECT
                    id,
                    row_number() OVER (
                        PARTITION BY user_id, signature
                        ORDER BY created_at DESC, id DESC
                    ) AS row_num
                FROM saved_comparisons
            ) ranked
            WHERE ranked.row_num > 1
        )
        """
    )
    op.execute("DROP TABLE IF EXISTS saved_comparison_idempotency_keys")
    op.create_unique_constraint(
        "uq_saved_comparisons_user_signature",
        "saved_comparisons",
        ["user_id", "signature"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_saved_comparisons_user_signature", "saved_comparisons", type_="unique")

    op.add_column(
        "saved_comparison_cars",
        sa.Column("age_at_purchase_months", sa.SmallInteger(), nullable=False, server_default="0"),
    )
    op.add_column(
        "saved_comparison_cars",
        sa.Column("custom_purchase_price_rub", sa.Integer(), nullable=True),
    )

    op.add_column(
        "saved_comparisons",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "saved_comparisons",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.add_column(
        "saved_comparisons",
        sa.Column("summary_total_tco_rub", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "saved_comparisons",
        sa.Column("options_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
    )
    op.add_column(
        "saved_comparisons",
        sa.Column("horizon_years", sa.SmallInteger(), nullable=False, server_default="5"),
    )
    op.add_column(
        "saved_comparisons",
        sa.Column("profile_snapshot", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
    )
    op.drop_column("saved_comparisons", "signature")

