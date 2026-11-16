"""Initial local schema, availability constraint and persistent outbox."""

from alembic import op
from studymate.models import Base

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    Base.metadata.create_all(
        op.get_bind(),
        tables=[
            table for table in Base.metadata.sorted_tables if table.name != "payment_simulations"
        ],
    )


def downgrade():
    Base.metadata.drop_all(
        op.get_bind(),
        tables=[
            table for table in Base.metadata.sorted_tables if table.name != "payment_simulations"
        ],
    )
