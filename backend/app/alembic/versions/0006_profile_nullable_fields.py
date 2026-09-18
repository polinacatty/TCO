from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("user_profiles", "region_id", existing_type=sa.Integer(), nullable=True)
    op.alter_column(
        "user_profiles",
        "annual_mileage_km",
        existing_type=sa.Integer(),
        nullable=True,
        server_default=None,
    )
    op.alter_column(
        "user_profiles",
        "driver_age",
        existing_type=sa.Integer(),
        nullable=True,
        server_default=None,
    )
    op.alter_column(
        "user_profiles",
        "driver_experience_years",
        existing_type=sa.Integer(),
        nullable=True,
        server_default=None,
    )


def downgrade() -> None:
    op.execute("UPDATE user_profiles SET region_id = 1 WHERE region_id IS NULL")
    op.execute(
        "UPDATE user_profiles SET annual_mileage_km = 15000 WHERE annual_mileage_km IS NULL"
    )
    op.execute("UPDATE user_profiles SET driver_age = 35 WHERE driver_age IS NULL")
    op.execute(
        "UPDATE user_profiles SET driver_experience_years = 10 WHERE driver_experience_years IS NULL"
    )

    op.alter_column("user_profiles", "region_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column(
        "user_profiles",
        "annual_mileage_km",
        existing_type=sa.Integer(),
        nullable=False,
        server_default="15000",
    )
    op.alter_column(
        "user_profiles",
        "driver_age",
        existing_type=sa.Integer(),
        nullable=False,
        server_default="35",
    )
    op.alter_column(
        "user_profiles",
        "driver_experience_years",
        existing_type=sa.Integer(),
        nullable=False,
        server_default="10",
    )
