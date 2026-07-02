"""Initial schema: users, cameras, zones, detections, alerts, audit_logs.

Revision ID: 0001_init
Revises:
Create Date: 2026-07-01
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_init"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("user_id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(32), nullable=False, server_default="viewer"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "cameras",
        sa.Column("camera_id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("stream_url", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="inactive"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "zones",
        sa.Column("zone_id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("camera_id", sa.Uuid(), nullable=False),
        sa.Column("severity", sa.String(32), nullable=False),
        sa.Column("line_y", sa.Float(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["camera_id"], ["cameras.camera_id"], ondelete="CASCADE"),
    )
    op.create_index("ix_zones_camera_id", "zones", ["camera_id"])

    op.create_table(
        "detections",
        sa.Column("detection_id", sa.Uuid(), primary_key=True),
        sa.Column("camera_id", sa.Uuid(), nullable=False),
        sa.Column("zone_id", sa.Uuid(), nullable=True),
        sa.Column("worker_id", sa.Integer(), nullable=False),
        sa.Column("violation_type", sa.String(32), nullable=False),
        sa.Column("severity", sa.String(32), nullable=False),
        sa.Column("crossed_line", sa.String(16), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("bbox", sa.JSON(), nullable=True),
        sa.Column("foot_x", sa.Float(), nullable=True),
        sa.Column("foot_y", sa.Float(), nullable=True),
        sa.Column("screenshot_path", sa.Text(), nullable=True),
        sa.Column("message", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["camera_id"], ["cameras.camera_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["zone_id"], ["zones.zone_id"], ondelete="SET NULL"),
    )
    op.create_index("ix_detections_camera_id", "detections", ["camera_id"])
    op.create_index("ix_detections_zone_id", "detections", ["zone_id"])
    op.create_index("ix_detections_violation_type", "detections", ["violation_type"])
    op.create_index("ix_detections_created_at", "detections", ["created_at"])

    op.create_table(
        "alerts",
        sa.Column("alert_id", sa.Uuid(), primary_key=True),
        sa.Column("detection_id", sa.Uuid(), nullable=False),
        sa.Column("level", sa.String(32), nullable=False),
        sa.Column("message", sa.String(512), nullable=True),
        sa.Column("acknowledged", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("acked_by", sa.Uuid(), nullable=True),
        sa.Column("acked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["detection_id"], ["detections.detection_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["acked_by"], ["users.user_id"], ondelete="SET NULL"),
    )
    op.create_index("ix_alerts_detection_id", "alerts", ["detection_id"])
    op.create_index("ix_alerts_acknowledged", "alerts", ["acknowledged"])
    op.create_index("ix_alerts_created_at", "alerts", ["created_at"])

    op.create_table(
        "audit_logs",
        sa.Column("log_id", sa.Uuid(), primary_key=True),
        sa.Column("action", sa.String(255), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="SET NULL"),
    )
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("alerts")
    op.drop_table("detections")
    op.drop_table("zones")
    op.drop_table("cameras")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
