"""Add oriented line-segment endpoints to zones.

Revision ID: 0003_line_endpoints
Revises: 0002_detection_mode
Create Date: 2026-07-01
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_line_endpoints"
down_revision: str | None = "0002_detection_mode"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("zones", sa.Column("line_x1", sa.Float(), nullable=True))
    op.add_column("zones", sa.Column("line_y1", sa.Float(), nullable=True))
    op.add_column("zones", sa.Column("line_x2", sa.Float(), nullable=True))
    op.add_column("zones", sa.Column("line_y2", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("zones", "line_y2")
    op.drop_column("zones", "line_x2")
    op.drop_column("zones", "line_y1")
    op.drop_column("zones", "line_x1")
