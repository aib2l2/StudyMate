"""Slot series, lesson rescheduling, slot-bound reminders."""

import sqlalchemy as sa
from alembic import op
from studymate.models import RescheduleRequest

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def _add(table, column):
    existing = {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}
    if column.name not in existing:
        op.add_column(table, column)


def upgrade():
    _add("slots", sa.Column("series_id", sa.String(36), nullable=True))
    _add(
        "bookings", sa.Column("reschedule_count", sa.Integer(), nullable=False, server_default="0")
    )
    _add("notifications", sa.Column("slot_id", sa.Integer(), nullable=True))
    bind = op.get_bind()
    indexes = {i["name"] for i in sa.inspect(bind).get_indexes("slots")}
    if "ix_slots_series_id" not in indexes:
        op.create_index("ix_slots_series_id", "slots", ["series_id"])
    RescheduleRequest.__table__.create(bind, checkfirst=True)


def downgrade():
    raise RuntimeError("Restore a backup instead: downgrading would delete reschedule history")
