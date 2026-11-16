"""Group lessons: slot capacity, shared meeting data and a capacity trigger.

The partial unique index "one active booking per slot" is replaced by:
* a partial unique index (slot_id, student_id): one seat per student;
* BEFORE INSERT / UPDATE triggers that abort when a slot is full.
For capacity = 1 the behaviour is exactly the old one.
"""

import sqlalchemy as sa
from alembic import op
from studymate.models import SlotMeeting

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None

ACTIVE = "('pending', 'confirmed')"
TRIGGERS = [
    f"""
    CREATE TRIGGER IF NOT EXISTS slot_capacity_insert
    BEFORE INSERT ON bookings
    WHEN NEW.status IN {ACTIVE}
     AND (SELECT COUNT(*) FROM bookings WHERE slot_id = NEW.slot_id AND status IN {ACTIVE})
         >= (SELECT capacity FROM slots WHERE id = NEW.slot_id)
    BEGIN SELECT RAISE(ABORT, 'slot_full'); END
    """,
    f"""
    CREATE TRIGGER IF NOT EXISTS slot_capacity_update
    BEFORE UPDATE OF status, slot_id ON bookings
    WHEN NEW.status IN {ACTIVE}
     AND (OLD.status NOT IN {ACTIVE} OR OLD.slot_id != NEW.slot_id)
     AND (SELECT COUNT(*) FROM bookings
          WHERE slot_id = NEW.slot_id AND status IN {ACTIVE} AND id != NEW.id)
         >= (SELECT capacity FROM slots WHERE id = NEW.slot_id)
    BEGIN SELECT RAISE(ABORT, 'slot_full'); END
    """,
]


def upgrade():
    bind = op.get_bind()
    existing = {c["name"] for c in sa.inspect(bind).get_columns("slots")}
    # Plain ADD COLUMN (no table rebuild): existing slots become capacity 1.
    for name, ddl in [
        ("capacity", "capacity INTEGER NOT NULL DEFAULT 1 CHECK (capacity BETWEEN 1 AND 5)"),
        ("topic_id", "topic_id INTEGER REFERENCES topics(id)"),
        ("price", "price INTEGER"),
        ("min_participants", "min_participants INTEGER NOT NULL DEFAULT 1"),
    ]:
        if name not in existing:
            bind.exec_driver_sql(f"ALTER TABLE slots ADD COLUMN {ddl}")
    SlotMeeting.__table__.create(bind, checkfirst=True)
    indexes = {i["name"] for i in sa.inspect(bind).get_indexes("bookings")}
    if "one_active_booking_per_slot" in indexes:
        op.drop_index("one_active_booking_per_slot", table_name="bookings")
    if "one_active_seat_per_student" not in indexes:
        op.create_index(
            "one_active_seat_per_student",
            "bookings",
            ["slot_id", "student_id"],
            unique=True,
            sqlite_where=sa.text(f"status IN {ACTIVE}"),
        )
    for ddl in TRIGGERS:
        bind.exec_driver_sql(ddl)


def downgrade():
    raise RuntimeError("Restore a backup instead: group bookings cannot fit the old index")
