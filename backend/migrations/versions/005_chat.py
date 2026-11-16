"""Lesson chat threads and read markers."""

from alembic import op
from studymate.models import ChatMessage, ChatRead

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    ChatMessage.__table__.create(bind, checkfirst=True)
    ChatRead.__table__.create(bind, checkfirst=True)


def downgrade():
    raise RuntimeError("Restore a backup instead: downgrading would delete chat history")
