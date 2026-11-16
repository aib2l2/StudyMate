import asyncio
import time

import pytest
from sqlalchemy import select
from studymate.config import Settings
from studymate.db import Database
from studymate.inbox import outbox_tick
from studymate.models import Notification, SessionToken, User
from studymate.service import notify


@pytest.fixture
def site_database(tmp_path):
    db = Database(
        Settings(mode="site", database=str(tmp_path / "site.sqlite3"), worker_enabled=False)
    )
    db.migrate()
    with db.transaction() as session:
        session.add(User(id=1, name="Test", registered=True))
        session.flush()
        notify(session, 1, None, "test", "Local inbox notification", "unique-test-event")
    yield db
    db.engine.dispose()


def test_inbox_delivery_persists_and_is_not_duplicated(site_database):
    asyncio.run(outbox_tick(site_database))
    reopened = Database(site_database.settings)
    asyncio.run(outbox_tick(reopened))
    with reopened.transaction() as session:
        rows = list(session.scalars(select(Notification)))
        assert len(rows) == 1 and rows[0].status == "in_app"
        assert rows[0].sent_at is not None
    reopened.engine.dispose()


def test_queue_migrates_legacy_uncertain_delivery_to_local_inbox(site_database):
    with site_database.transaction() as session:
        session.scalar(select(Notification)).status = "uncertain"
    asyncio.run(outbox_tick(site_database))
    with site_database.transaction() as session:
        assert session.scalar(select(Notification)).status == "in_app"


def test_expired_sessions_are_removed_without_touching_valid_sessions(site_database):
    with site_database.transaction() as session:
        session.add_all(
            [
                SessionToken(token_hash="expired", user_id=1, expires_at=int(time.time()) - 1),
                SessionToken(token_hash="valid", user_id=1, expires_at=int(time.time()) + 3600),
            ]
        )
    asyncio.run(outbox_tick(site_database))
    with site_database.transaction() as session:
        assert session.get(SessionToken, "expired") is None
        assert session.get(SessionToken, "valid") is not None


def test_waiting_for_database_does_not_block_event_loop(site_database):
    async def scenario():
        with site_database.transaction():
            task = asyncio.create_task(outbox_tick(site_database))
            started = time.monotonic()
            await asyncio.sleep(0.05)
            assert time.monotonic() - started < 1
        await task

    asyncio.run(scenario())
