"""Add per-camera detection mode (restricted_area | helmet).

Revision ID: 0002_detection_mode
Revises: 0001_init
Create Date: 2026-07-01
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_detection_mode"
down_revision: str | None = "0001_init"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "cameras",
        sa.Column(
            "detection_mode",
            sa.String(32),
            nullable=False,
            server_default="restricted_area",
        ),
    )


def downgrade() -> None:
    op.drop_column("cameras", "detection_mode")
