"""bot sessions and message log

Revision ID: 0002_bot_sessions
Revises: 0001_initial
Create Date: 2026-05-03 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0002_bot_sessions"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bot_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("platform", sa.String(length=64), nullable=False),
        sa.Column("chat_id", sa.String(length=255), nullable=False),
        sa.Column("session_key", sa.String(length=500), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_bot_sessions_session_key", "bot_sessions", ["session_key"], unique=True)
    op.create_index("ix_bot_sessions_user_id", "bot_sessions", ["user_id"])

    op.create_table(
        "bot_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "session_id",
            sa.Integer(),
            sa.ForeignKey("bot_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("message_type", sa.String(length=64), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("command", sa.String(length=128), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_bot_messages_session_id", "bot_messages", ["session_id"])
    op.create_index("ix_bot_messages_created_at", "bot_messages", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_bot_messages_created_at", table_name="bot_messages")
    op.drop_index("ix_bot_messages_session_id", table_name="bot_messages")
    op.drop_table("bot_messages")
    op.drop_index("ix_bot_sessions_user_id", table_name="bot_sessions")
    op.drop_index("ix_bot_sessions_session_key", table_name="bot_sessions")
    op.drop_table("bot_sessions")
