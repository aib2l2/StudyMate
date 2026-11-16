"""Upgrade a real 2.1 demo database (created by the 2.1 code, revision 004) to head."""

import shutil
import sqlite3
from contextlib import closing
from pathlib import Path

from fastapi.testclient import TestClient
from studymate.api import create_app
from studymate.config import Settings

FIXTURE = Path(__file__).parent / "fixtures" / "v2_1-demo.sqlite3"
TABLES = ("users", "mentors", "slots", "bookings", "reviews", "lesson_notes", "progress_events")


def counts(path):
    with closing(sqlite3.connect(path)) as raw:
        return {t: raw.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in TABLES}


def test_v21_database_upgrades_to_head_without_losing_data(tmp_path):
    path = tmp_path / "upgrade-demo.sqlite3"
    shutil.copy(FIXTURE, path)
    before = counts(path)
    with closing(sqlite3.connect(path)) as raw:
        assert raw.execute("SELECT version_num FROM alembic_version").fetchone() == ("004",)
    app = create_app(Settings(database=str(path), worker_enabled=False))
    with TestClient(app) as client:
        # Old data is usable through the new API.
        token = client.post("/api/auth/demo", json={"user_id": 3}).json()["token"]
        lesson = client.get(
            "/api/bookings/demo-incoming", headers={"Authorization": f"Bearer {token}"}
        )
        assert lesson.status_code == 200 and lesson.json()["notes"] == "заметка из 2.1"
        assert lesson.json()["group"] is None and lesson.json()["slot"]["capacity"] == 1
        assert client.get("/api/public/mentors?q=sql").json()  # search index was built
    after = counts(path)
    # Nothing is lost; a demo database additionally gets the 2.2 examples.
    assert all(after[k] >= before[k] for k in before)
    assert after["users"] == before["users"] and after["reviews"] == before["reviews"]
    with closing(sqlite3.connect(FIXTURE)) as old, closing(sqlite3.connect(path)) as new:
        # Status may legitimately move on (a pending demo request expires after 15 minutes).
        old_rows = old.execute("SELECT id, student_id, slot_id, price FROM bookings").fetchall()
        new_rows = set(
            new.execute("SELECT id, student_id, slot_id, price FROM bookings").fetchall()
        )
        assert set(old_rows) <= new_rows
    with closing(sqlite3.connect(path)) as raw:
        assert raw.execute("SELECT version_num FROM alembic_version").fetchone() == ("008",)
        assert raw.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert raw.execute("PRAGMA foreign_key_check").fetchall() == []
        names = {r[0] for r in raw.execute("SELECT name FROM sqlite_master")}
        assert "one_active_booking_per_slot" not in names
        assert {
            "one_active_seat_per_student",
            "slot_capacity_insert",
            "slot_capacity_update",
        } <= names
        assert {"chat_messages", "favorites", "reschedule_requests", "slot_meetings"} <= names
        assert "mentor_search" in names
        old_slots = raw.execute(
            "SELECT COUNT(*) FROM slots WHERE capacity != 1 AND id <= ?", (before["slots"],)
        ).fetchone()
        assert old_slots == (0,)  # every pre-existing slot stays one-to-one


def test_upgrade_is_idempotent(tmp_path):
    path = tmp_path / "twice-demo.sqlite3"
    shutil.copy(FIXTURE, path)
    for _ in range(2):
        with TestClient(create_app(Settings(database=str(path), worker_enabled=False))):
            pass
    with closing(sqlite3.connect(path)) as raw:
        assert raw.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert raw.execute("SELECT COUNT(*) FROM slot_meetings").fetchone() == (1,)
