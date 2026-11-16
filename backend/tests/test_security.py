"""Transactions, rate limiting, headers, account security and access isolation."""

import sqlite3
import threading
import time
from contextlib import closing

import pytest
from conftest import book, login
from studymate.auth import RateLimiter, issue_reset_code
from studymate.db import ReadOnlySessionError
from studymate.models import Booking, PasswordResetCode, SessionToken, User

PASSWORD = "test-password-123"


def register(client, email="secure@example.test", password=PASSWORD):
    response = client.post(
        "/api/auth/register",
        json={"name": "Secure Student", "email": email, "password": password, "course": 2},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["token"]}, response.json()["user"]


def sign_in(client, email="secure@example.test", password=PASSWORD):
    return client.post("/api/auth/login", json={"email": email, "password": password})


# ------------------------------------------------------------ transactions


def test_reads_do_not_wait_for_the_write_lock(client):
    db = client.app.state.db
    holding, release = threading.Event(), threading.Event()

    def writer():
        with db.write():
            holding.set()
            release.wait(5)

    thread = threading.Thread(target=writer)
    thread.start()
    assert holding.wait(5)
    try:
        started = time.monotonic()
        assert client.get("/api/public/catalog").status_code == 200
        assert client.get("/api/public/mentors?topic_id=1").status_code == 200
        assert time.monotonic() - started < 2
    finally:
        release.set()
        thread.join()


def test_read_session_refuses_writes(client):
    with pytest.raises(ReadOnlySessionError), client.app.state.db.read() as session:
        session.get(User, 1).name = "Changed"
        session.flush()
    with client.app.state.db.read() as session:
        assert session.get(User, 1).name != "Changed"


def test_read_endpoint_still_expires_overdue_bookings(client):
    student = login(client)
    booking = book(client, student)
    with client.app.state.db.write() as session:
        session.get(Booking, booking["id"]).expires_at = int(time.time()) - 1
    assert (
        client.get(f"/api/bookings/{booking['id']}", headers=student).json()["status"] == "expired"
    )


def test_migration_004_upgrades_a_version_003_database(tmp_path):
    from alembic import command
    from alembic.config import Config
    from studymate.config import ROOT, Settings
    from studymate.db import Database

    database = Database(Settings(database=str(tmp_path / "old-demo.sqlite3")))
    config = Config(str(ROOT / "backend" / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "backend" / "migrations"))
    config.set_main_option("sqlalchemy.url", str(database.engine.url))
    command.upgrade(config, "003")
    with closing(sqlite3.connect(database.settings.database)) as raw:
        raw.execute("DROP TABLE IF EXISTS password_reset_codes")
        raw.commit()
    database.migrate()
    with closing(sqlite3.connect(database.settings.database)) as raw:
        from alembic.script import ScriptDirectory

        head = ScriptDirectory.from_config(config).get_current_head()
        assert raw.execute("SELECT version_num FROM alembic_version").fetchone() == (head,)
        assert raw.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        tables = {r[0] for r in raw.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "password_reset_codes" in tables
    database.engine.dispose()


# ----------------------------------------------------------- rate limiting


def test_rate_limit_is_per_account_not_per_shared_address(client):
    register(client, "victim@example.test")
    for _ in range(10):
        assert sign_in(client, "attacker@example.test", "wrong-password").status_code == 401
    assert sign_in(client, "attacker@example.test", "wrong-password").status_code == 429
    # Another person behind the same 127.0.0.1 can still sign in.
    assert sign_in(client, "victim@example.test").status_code == 200


def test_rate_limiter_client_window_and_pruning():
    limiter = RateLimiter(per_account=100, per_client=3, window=60, max_keys=2)
    assert all(limiter.hit("1.1.1.1", f"user{i}@x.test") for i in range(3))
    assert not limiter.hit("1.1.1.1", "user9@x.test")
    expired = RateLimiter(per_account=5, per_client=5, window=0, max_keys=1)
    for i in range(5):
        expired.hit(f"10.0.0.{i}", "a@x.test")
    assert len(expired) <= 4  # stale keys are dropped instead of growing forever


# ----------------------------------------------------------------- headers


def test_security_headers(client):
    for path in ("/", "/api/public/catalog"):
        headers = client.get(path).headers
        assert "default-src 'self'" in headers["Content-Security-Policy"]
        assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
        assert headers["X-Frame-Options"] == "DENY"
        assert headers["X-Content-Type-Options"] == "nosniff"


def test_expired_token_is_deleted_on_use(client):
    h, _ = register(client)
    with client.app.state.db.write() as session:
        for token in session.query(SessionToken).all():
            token.expires_at = int(time.time()) - 1
    assert client.get("/api/me", headers=h).status_code == 401
    assert client.post("/api/notifications/read", headers=h).status_code == 401
    with client.app.state.db.read() as session:
        assert session.query(SessionToken).count() == 0


def test_password_length_is_validated_by_schema(client):
    response = client.post(
        "/api/auth/register",
        json={"name": "A", "email": "long@example.test", "password": "x" * 129},
    )
    assert response.status_code == 422


# --------------------------------------------------------- account security


def test_change_password_revokes_other_sessions(client):
    first, _ = register(client)
    second = {"Authorization": "Bearer " + sign_in(client).json()["token"]}
    wrong = client.post(
        "/api/auth/password",
        headers=first,
        json={"current_password": "not-the-password", "new_password": "brand-new-pass-1"},
    )
    assert wrong.status_code == 403
    same = client.post(
        "/api/auth/password",
        headers=first,
        json={"current_password": PASSWORD, "new_password": PASSWORD},
    )
    assert same.status_code == 422
    ok = client.post(
        "/api/auth/password",
        headers=first,
        json={"current_password": PASSWORD, "new_password": "brand-new-pass-1"},
    )
    assert ok.status_code == 200
    assert client.get("/api/me", headers=first).status_code == 200
    assert client.get("/api/me", headers=second).status_code == 401
    assert sign_in(client).status_code == 401
    assert sign_in(client, password="brand-new-pass-1").status_code == 200


def test_demo_account_without_password_cannot_change_it(client):
    response = client.post(
        "/api/auth/password",
        headers=login(client),
        json={"current_password": "anything", "new_password": "brand-new-pass-1"},
    )
    assert response.status_code == 409


def test_logout_everywhere(client):
    first, _ = register(client)
    second = {"Authorization": "Bearer " + sign_in(client).json()["token"]}
    assert client.post("/api/auth/logout-all", headers=first).status_code == 200
    assert client.get("/api/me", headers=first).status_code == 401
    assert client.get("/api/me", headers=second).status_code == 401


def test_local_reset_code_is_single_use_and_expires(client):
    old, user = register(client)
    with client.app.state.db.write() as session:
        code = issue_reset_code(session, user["id"])
    body = {"email": "secure@example.test", "code": code.lower(), "new_password": "after-reset-1"}
    response = client.post("/api/auth/reset", json=body)
    assert response.status_code == 200, response.text
    assert client.get("/api/me", headers=old).status_code == 401
    assert sign_in(client, password="after-reset-1").status_code == 200
    assert client.post("/api/auth/reset", json=body).status_code == 400  # already used

    with client.app.state.db.write() as session:
        code = issue_reset_code(session, user["id"])
        for row in session.query(PasswordResetCode).all():
            row.expires_at = int(time.time()) - 1
    body["code"] = code
    assert client.post("/api/auth/reset", json=body).status_code == 400
    body.update(email="someone-else@example.test")
    assert client.post("/api/auth/reset", json=body).status_code == 400


def test_new_reset_code_invalidates_previous(client):
    _, user = register(client)
    with client.app.state.db.write() as session:
        first = issue_reset_code(session, user["id"])
    with client.app.state.db.write() as session:
        issue_reset_code(session, user["id"])
    body = {"email": "secure@example.test", "code": first, "new_password": "after-reset-1"}
    assert client.post("/api/auth/reset", json=body).status_code == 400


def test_export_contains_only_own_private_data(client):
    student, mentor = login(client), login(client, 2)
    booking = book(client, student)
    client.put(
        f"/api/bookings/{booking['id']}/workspace", headers=student, json={"notes": "my note"}
    )
    client.put(
        f"/api/bookings/{booking['id']}/workspace", headers=mentor, json={"notes": "mentor note"}
    )
    assert client.get("/api/me/export").status_code == 401
    data = client.get("/api/me/export", headers=student).json()
    assert data["profile"]["id"] == 1
    assert any(b["id"] == booking["id"] for b in data["bookings"])
    assert [n["body"] for n in data["notes"] if n["booking_id"] == booking["id"]] == ["my note"]
    assert "mentor note" not in str(data)


# ------------------------------------------------------- access isolation


def test_other_student_cannot_reach_foreign_lesson_data(client):
    student, other = login(client), login(client, 3)
    booking = book(client, student)
    bid = booking["id"]
    attempt = client.post(
        "/api/quizzes", headers=student, json={"topic_id": 1, "stage": "pre", "booking_id": bid}
    ).json()
    assert client.get(f"/api/bookings/{bid}", headers=other).status_code == 403
    assert (
        client.put(f"/api/bookings/{bid}/workspace", headers=other, json={"notes": "x"}).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/bookings/{bid}/action", headers=other, json={"action": "cancel"}
        ).status_code
        == 403
    )
    assert client.post(f"/api/bookings/{bid}/payment-simulation", headers=other).status_code == 403
    assert (
        client.post(
            f"/api/bookings/{bid}/review", headers=other, json={"rating": 5, "comment": "great"}
        ).status_code
        == 403
    )
    assert client.get(f"/api/quizzes/{attempt['id']}", headers=other).status_code == 403
    assert (
        client.post(
            f"/api/quizzes/{attempt['id']}/submit", headers=other, json={"answers": [0, 0, 0]}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/quizzes", headers=other, json={"topic_id": 1, "stage": "pre", "booking_id": bid}
        ).status_code
        == 403
    )
    assert all(b["id"] != bid for b in client.get("/api/bookings", headers=other).json())


def test_admin_endpoints_require_team_role(client):
    student = login(client)
    assert client.get("/api/admin", headers=student).status_code == 403
    assert (
        client.put(
            "/api/admin/mentors/2", headers=student, json={"verified": True, "active": False}
        ).status_code
        == 403
    )
    assert (
        client.put(
            "/api/admin/subjects/1", headers=student, json={"name": "Hacked", "active": False}
        ).status_code
        == 403
    )
    assert client.get("/api/admin").status_code == 401
    assert client.get("/api/admin", headers=login(client, 99)).status_code == 200


def test_mentor_cannot_close_another_mentors_slot(client):
    slots = client.get("/api/mentor/slots", headers=login(client, 2)).json()
    other_mentor = login(client, 3)
    response = client.delete(f"/api/mentor/slots/{slots[0]['id']}", headers=other_mentor)
    assert response.status_code == 403


def test_openapi_documents_response_models(client):
    schema = client.get("/openapi.json").json()
    for name in ("BookingOut", "UserOut", "MentorCardOut", "QuizOut", "AdminOut", "ExportOut"):
        assert name in schema["components"]["schemas"]
