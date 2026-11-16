"""Local password reset codes."""

from alembic import op
from studymate.models import PasswordResetCode

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade():
    PasswordResetCode.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    op.drop_table("password_reset_codes")
