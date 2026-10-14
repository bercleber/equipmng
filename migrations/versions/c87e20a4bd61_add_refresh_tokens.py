"""Add rotating refresh-token sessions.

Revision ID: c87e20a4bd61
Revises: 99bb21c9c1ea
"""

from alembic import op
import sqlalchemy as sa

revision = "c87e20a4bd61"
down_revision = "99bb21c9c1ea"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "refresh_session",
        sa.Column("id", sa.String(32), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_refresh_session_user_id", "refresh_session", ["user_id"])
    op.create_index("ix_refresh_session_expires_at", "refresh_session", ["expires_at"])
    op.create_table(
        "refresh_token",
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("session_id", sa.String(32), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["session_id"], ["refresh_session.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("token_hash"),
    )
    op.create_index("ix_refresh_token_session_id", "refresh_token", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_refresh_token_session_id", table_name="refresh_token")
    op.drop_table("refresh_token")
    op.drop_index("ix_refresh_session_expires_at", table_name="refresh_session")
    op.drop_index("ix_refresh_session_user_id", table_name="refresh_session")
    op.drop_table("refresh_session")
