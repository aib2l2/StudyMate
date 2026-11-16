"""Website accounts, protected moderation and lesson workspaces."""

import sqlalchemy as sa
from alembic import op
from studymate.models import LessonNote

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade():
    tables = {
        "users": [
            sa.Column("email", sa.String(254), nullable=True),
            sa.Column("password_hash", sa.Text(), nullable=True),
        ],
        "mentors": [
            sa.Column("suspended", sa.Boolean(), nullable=False, server_default=sa.false())
        ],
        "slots": [sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true())],
        "bookings": [
            sa.Column("meeting_url", sa.Text(), nullable=False, server_default=""),
            sa.Column("meeting_place", sa.Text(), nullable=False, server_default=""),
            sa.Column("materials", sa.Text(), nullable=False, server_default=""),
            sa.Column("mentor_completed_at", sa.Integer(), nullable=True),
        ],
    }
    for name, columns in tables.items():
        existing = {c["name"] for c in sa.inspect(op.get_bind()).get_columns(name)}
        for column in columns:
            if column.name not in existing:
                op.add_column(name, column)
    inspector = sa.inspect(op.get_bind())
    constraints = inspector.get_unique_constraints("users") + inspector.get_indexes("users")
    if not any(c.get("column_names") == ["email"] and c.get("unique", True) for c in constraints):
        op.create_index("uq_users_email", "users", ["email"], unique=True)
    LessonNote.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    raise RuntimeError("Restore the pre-upgrade backup to preserve website account and lesson data")
