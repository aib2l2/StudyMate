from conftest import book, login, proposal
from fastapi.testclient import TestClient
from studymate.api import create_app
from studymate.config import Settings
from studymate.models import Booking, Slot, User


def register(client, email="student@example.test"):
    return client.post(
        "/api/auth/register",
        json={"name": "New Student", "email": email, "password": "test-password-123", "course": 2},
    )


def test_guest_catalog_and_website_deep_links(client):
    assert client.get("/api/me").status_code == 401
    assert len(client.get("/api/public/catalog").json()) == 3
    rows = client.get("/api/public/mentors?topic_id=1").json()
    assert rows and all(m["slots"] for m in rows)
    profile = client.get("/api/public/mentors/2").json()
    assert profile["topics"] and profile["reviews"]
    for path in ("/", "/login", "/mentors/2", "/lessons/test-deep-link", "/calendar"):
        response = client.get(path)
        assert response.status_code == 200 and 'id="root"' in response.text
    assert client.get("/api/unknown").status_code == 404
    assert "/api/auth/telegram" not in client.get("/openapi.json").json()["paths"]
    assert client.post("/api/auth/telegram", json={}).status_code in (404, 405)


def test_password_registration_login_and_revoked_logout(client):
    result = register(client, " STUDENT@example.test ")
    assert result.status_code == 200
    h = {"Authorization": "Bearer " + result.json()["token"]}
    user = result.json()["user"]
    assert user["email"] == "student@example.test" and not user["is_admin"]
    with client.app.state.db.transaction() as session:
        saved = session.get(User, user["id"])
        assert saved.password_hash.startswith("pbkdf2_sha256$")
        assert "test-password-123" not in saved.password_hash
    assert register(client).status_code == 409
    assert (
        client.post(
            "/api/auth/login", json={"email": user["email"], "password": "wrong-password"}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/auth/login", json={"email": user["email"], "password": "test-password-123"}
        ).status_code
        == 200
    )
    assert client.post("/api/auth/logout", headers=h, json={}).status_code == 200
    assert client.get("/api/me", headers=h).status_code == 401
    assert (
        client.post(
            "/api/auth/register", json={"email": "x", "password": "short", "name": " "}
        ).status_code
        == 422
    )


def test_site_mode_has_no_demo_accounts_or_admin_by_email(tmp_path):
    settings = Settings(mode="site", database=str(tmp_path / "site.sqlite3"), worker_enabled=False)
    with TestClient(create_app(settings)) as site:
        assert site.get("/api/config").json()["demo_accounts"] == []
        assert site.post("/api/auth/demo", json={"user_id": 99}).status_code == 404
        response = register(site, "admin@example.test")
        assert response.status_code == 200 and not response.json()["user"]["is_admin"]
        h = {"Authorization": "Bearer " + response.json()["token"]}
        assert site.get("/api/admin", headers=h).status_code == 403
    import pytest

    with pytest.raises(ValueError):
        Settings(mode="site", database=str(tmp_path / "demo.sqlite3"))


def test_lesson_location_materials_and_private_notes(client):
    student, mentor, stranger, admin = (
        login(client),
        login(client, 2),
        login(client, 3),
        login(client, 99),
    )
    b = book(client, student)
    base = "/api/bookings/" + b["id"]
    assert client.get(base, headers=stranger).status_code == 403
    assert (
        client.post(base + "/action", headers=mentor, json={"action": "confirm"}).status_code == 422
    )
    for url in (
        "http://example.org",
        "javascript:alert(1)",
        "https://user:secret@example.org",
        "https://[broken",
        "https://example.org:invalid",
    ):
        assert (
            client.post(
                base + "/action", headers=mentor, json={"action": "confirm", "meeting_url": url}
            ).status_code
            == 422
        )
    assert (
        client.post(
            base + "/action",
            headers=mentor,
            json={"action": "confirm", "meeting_url": "https://example.org/room"},
        ).json()["status"]
        == "confirmed"
    )
    assert (
        client.post(
            base + "/action", headers=mentor, json={"action": "confirm", "meeting_url": ""}
        ).json()["meeting_url"]
        == "https://example.org/room"
    )
    assert (
        client.put(
            base + "/workspace", headers=student, json={"materials": "Unapproved"}
        ).status_code
        == 403
    )
    assert (
        client.put(
            base + "/workspace",
            headers=mentor,
            json={
                "materials": "https://docs.python.org/3/\nPractice joins",
                "notes": "Mentor private",
            },
        ).status_code
        == 200
    )
    assert (
        client.put(
            base + "/workspace", headers=student, json={"notes": "Student private"}
        ).status_code
        == 200
    )
    assert client.get(base, headers=student).json()["notes"] == "Student private"
    assert client.get(base, headers=mentor).json()["notes"] == "Mentor private"
    assert client.get(base, headers=admin).json()["notes"] == ""
    assert "Student private" not in client.get("/api/bookings", headers=mentor).text
    assert (
        client.put(base + "/workspace", headers=mentor, json={"meeting_url": ""}).status_code == 422
    )
    assert (
        client.put(base + "/workspace", headers=admin, json={"notes": "admin private"}).status_code
        == 403
    )


def test_campus_confirmation_requires_a_location(client):
    student, mentor = login(client), login(client, 2)
    payload = proposal(client, student)
    response = client.post("/api/bookings", headers=student, json={**payload, "format": "campus"})
    assert response.status_code == 200
    path = "/api/bookings/" + response.json()["id"] + "/action"
    assert (
        client.post(
            path, headers=mentor, json={"action": "confirm", "meeting_url": "https://example.org"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            path, headers=mentor, json={"action": "confirm", "meeting_place": "Библиотека, стол 4"}
        ).json()["status"]
        == "confirmed"
    )


def test_both_participants_confirm_completion_and_xp_is_not_duplicated(client):
    student, mentor = login(client), login(client, 2)
    b = book(client, student)
    path = "/api/bookings/" + b["id"] + "/action"
    client.post(
        path, headers=mentor, json={"action": "confirm", "meeting_url": "https://example.org/room"}
    )
    assert client.post(path, headers=student, json={"action": "complete"}).status_code == 409
    assert (
        client.post(path, headers=student, json={"action": "request_completion"}).status_code == 403
    )
    assert client.post(path, headers=mentor, json={"action": "complete"}).status_code == 403
    assert client.post(path, headers=mentor, json={"action": "request_completion"}).json()[
        "mentor_completed_at"
    ]
    before = client.get("/api/progress", headers=student).json()["points"]
    assert (
        client.post(path, headers=student, json={"action": "complete"}).json()["status"]
        == "completed"
    )
    assert client.post(path, headers=student, json={"action": "complete"}).status_code == 200
    assert client.get("/api/progress", headers=student).json()["points"] == before + 30
    assert client.post(path, headers=mentor, json={"action": "complete"}).status_code == 403


def test_early_completion_shortcut_only_in_demo(client):
    student, mentor = login(client), login(client, 2)
    b = book(client, student)
    path = "/api/bookings/" + b["id"] + "/action"
    client.post(
        path, headers=mentor, json={"action": "confirm", "meeting_url": "https://example.org/room"}
    )
    import pytest
    from fastapi import HTTPException
    from studymate.service import change_booking

    with pytest.raises(HTTPException) as raised, client.app.state.db.transaction() as session:
        change_booking(
            session,
            session.get(User, 2),
            b["id"],
            "request_completion",
            Settings(mode="site", database="/tmp/studymate-site-test.sqlite3"),
        )
    assert raised.value.status_code == 409


def test_calendar_marks_bookings_and_soft_closed_intervals(client):
    student, mentor = login(client), login(client, 2)
    b = book(client, student)

    def slot():
        return next(
            s
            for s in client.get("/api/mentor/slots", headers=mentor).json()
            if s["id"] == b["slot"]["id"]
        )

    assert slot()["state"] == "pending"
    assert (
        client.delete("/api/mentor/slots/" + str(b["slot"]["id"]), headers=mentor).status_code
        == 409
    )
    client.post("/api/bookings/" + b["id"] + "/action", headers=student, json={"action": "cancel"})
    route = "/api/mentor/slots/" + str(b["slot"]["id"])
    assert client.delete(route, headers=mentor).status_code == 200
    assert slot()["state"] == "closed" and slot()["enabled"] is False
    with client.app.state.db.transaction() as session:
        assert session.get(Slot, b["slot"]["id"]) is not None
        assert session.get(Booking, b["id"]) is not None
    assert (
        client.post(
            "/api/mentor/slots", headers=mentor, json={"starts_at": b["slot"]["starts_at"]}
        ).status_code
        == 200
    )
    assert slot()["state"] == "free"


def test_admin_suspension_cannot_be_overridden_by_mentor_profile(client):
    mentor, admin = login(client, 2), login(client, 99)
    assert (
        client.put(
            "/api/admin/mentors/2", headers=admin, json={"verified": True, "active": False}
        ).status_code
        == 200
    )
    profile = client.get("/api/me", headers=mentor).json()["mentor"]
    assert profile["active"] is True and profile["suspended"] is True
    assert (
        client.put(
            "/api/mentor/profile", headers=mentor, json={**profile, "active": True}
        ).status_code
        == 200
    )
    assert client.get("/api/public/mentors/2").status_code == 404
    assert 2 not in [m["id"] for m in client.get("/api/public/mentors?topic_id=1").json()]
    assert (
        client.put(
            "/api/admin/mentors/2", headers=admin, json={"verified": True, "active": True}
        ).status_code
        == 200
    )
    assert client.get("/api/public/mentors/2").status_code == 200


def test_disabled_subject_is_excluded_and_earliest_is_rechecked(client):
    student, admin = login(client), login(client, 99)
    p = proposal(client, student)
    assert (
        client.post(
            "/api/bookings", headers=student, json={**p, "earliest": p["deadline"]}
        ).status_code
        == 409
    )
    client.put(
        "/api/admin/subjects/1", headers=admin, json={"name": "SQL / Databases", "active": False}
    )
    assert client.get("/api/public/mentors?topic_id=1").json() == []
    assert client.post("/api/bookings", headers=student, json=p).status_code == 409


def test_completed_demo_interval_cannot_be_booked_again(client):
    student, mentor, second = login(client), login(client, 2), login(client, 3)
    p = proposal(client, student)
    b = client.post("/api/bookings", headers=student, json=p).json()
    path = "/api/bookings/" + b["id"] + "/action"
    client.post(
        path, headers=mentor, json={"action": "confirm", "meeting_url": "https://example.org/room"}
    )
    client.post(path, headers=mentor, json={"action": "request_completion"})
    client.post(path, headers=student, json={"action": "complete"})
    assert client.post("/api/bookings", headers=second, json=p).status_code == 409
    own = client.get("/api/mentor/slots", headers=mentor).json()
    assert next(s for s in own if s["id"] == p["slot_id"])["state"] == "completed"
    card = client.get("/api/public/mentors/2").json()
    assert p["slot_id"] not in [s["id"] for s in card["slots"]]


def test_public_profile_rejects_mentor_with_no_active_topics(client):
    admin = login(client, 99)
    client.put(
        "/api/admin/subjects/1", headers=admin, json={"name": "Базы данных", "active": False}
    )
    assert client.get("/api/public/mentors/2").status_code == 404
    # A mentor with Python expertise remains visible, with only active topics.
    profile = client.get("/api/public/mentors/12").json()
    assert profile["topics"] and all(t["subject_id"] != 1 for t in profile["topics"])


def test_local_admin_command_promotes_only_an_existing_site_account(tmp_path, monkeypatch):
    path = str(tmp_path / "site.sqlite3")
    settings = Settings(mode="site", database=path, worker_enabled=False)
    with TestClient(create_app(settings)) as site:
        assert register(site, "owner@example.test").status_code == 200
    monkeypatch.setenv("APP_MODE", "site")
    monkeypatch.setenv("DATABASE_PATH", path)
    monkeypatch.setenv("WORKER_ENABLED", "0")
    monkeypatch.setattr("sys.argv", ["studymate", "admin", "--email", "owner@example.test"])
    from studymate.__main__ import main

    main()
    with TestClient(create_app(settings)) as site:
        result = site.post(
            "/api/auth/login", json={"email": "owner@example.test", "password": "test-password-123"}
        ).json()
        assert result["user"]["is_admin"] is True
        assert (
            site.get(
                "/api/admin", headers={"Authorization": "Bearer " + result["token"]}
            ).status_code
            == 200
        )


def test_local_reset_password_command_issues_working_code(tmp_path, monkeypatch, capsys):
    path = str(tmp_path / "site.sqlite3")
    settings = Settings(mode="site", database=path, worker_enabled=False)
    with TestClient(create_app(settings)) as site:
        assert register(site, "forgot@example.test").status_code == 200
    monkeypatch.setenv("APP_MODE", "site")
    monkeypatch.setenv("DATABASE_PATH", path)
    monkeypatch.setenv("WORKER_ENABLED", "0")
    monkeypatch.setattr(
        "sys.argv", ["studymate", "reset-password", "--email", "Forgot@example.test"]
    )
    from studymate.__main__ import main

    main()
    code = capsys.readouterr().out.split(": ", 1)[1].split()[0]
    with TestClient(create_app(settings)) as site:
        body = {"email": "forgot@example.test", "code": code, "new_password": "fresh-password-9"}
        assert site.post("/api/auth/reset", json=body).status_code == 200
        login = site.post(
            "/api/auth/login", json={"email": "forgot@example.test", "password": "fresh-password-9"}
        )
        assert login.status_code == 200
