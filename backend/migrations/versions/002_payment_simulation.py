"""Store demo payment calculations without any payment provider."""

from alembic import op
from studymate.models import PaymentSimulation

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade():
    PaymentSimulation.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    PaymentSimulation.__table__.drop(op.get_bind(), checkfirst=True)
