"""Full-text mentor search, favorites, notification links."""

import sqlalchemy as sa
from alembic import op
from studymate.models import Favorite

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    Favorite.__table__.create(bind, checkfirst=True)
    columns = {c["name"] for c in sa.inspect(bind).get_columns("notifications")}
    if "link" not in columns:
        op.add_column("notifications", sa.Column("link", sa.String(200), nullable=True))
    from studymate.search import create_index, fts_available, reindex_all

    if fts_available(bind):
        create_index(bind)
        reindex_all(bind)


def downgrade():
    raise RuntimeError("Restore a backup instead: downgrading would delete favorites")
