from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session

from .config import ROOT, Settings


class ReadOnlySessionError(RuntimeError):
    """Raised when code tries to write through a read-only session."""


def is_readonly(session: Session) -> bool:
    return bool(session.info.get("readonly"))


@event.listens_for(Session, "before_flush")
def _guard_readonly(session, _flush_context, _instances):
    if is_readonly(session) and (session.new or session.dirty or session.deleted):
        raise ReadOnlySessionError("Попытка записи через сессию только для чтения")


class Database:
    def __init__(self, settings: Settings):
        from .events import EventBus

        self.settings = settings
        self.bus = EventBus()
        Path(settings.database).parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(
            f"sqlite:///{settings.database}",
            connect_args={"check_same_thread": False, "timeout": 15},
        )

        @event.listens_for(self.engine, "connect")
        def pragmas(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=15000")
            connection.execute("PRAGMA journal_mode=WAL")

    def migrate(self):
        config = Config(str(ROOT / "backend" / "alembic.ini"))
        config.set_main_option("script_location", str(ROOT / "backend" / "migrations"))
        config.set_main_option("sqlalchemy.url", str(self.engine.url))
        command.upgrade(config, "head")

    @contextmanager
    def write(self) -> Iterator[Session]:
        """Serialized write transaction.

        ``BEGIN IMMEDIATE`` takes SQLite's write lock before any check runs, so
        "is the slot free?" and "reserve the slot" happen atomically.
        """
        with Session(self.engine, expire_on_commit=False) as session:
            session.info["bus"] = self.bus
            session.execute(text("BEGIN IMMEDIATE"))
            try:
                yield session
                session.commit()
            except BaseException:
                session.rollback()
                raise

    # Backwards-compatible name used by seed, CLI and tests.
    transaction = write

    @contextmanager
    def read(self) -> Iterator[Session]:
        """Snapshot read without the write lock. Always rolled back."""
        with Session(self.engine, expire_on_commit=False) as session:
            session.info["readonly"] = True
            try:
                session.execute(text("BEGIN"))
                yield session
            finally:
                session.rollback()
