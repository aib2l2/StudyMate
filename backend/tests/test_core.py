import asyncio
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from conftest import book, login, proposal
from fastapi.testclient import TestClient
from sqlalchemy import select
from studymate.api import create_app
from studymate.inbox import outbox_tick
from studymate.models import Booking, Notification
from studymate.quizzes import BANK


def test_full_booking_learning_review_payment_flow(client):
    student, mentor = login(client), login(client, 2)
    booking = book(client, student)
    bid = booking["id"]
    attempt = client.post(
        "/api/quizzes", headers=student, json={"topic_id": 1, "stage": "pre", "booking_id": bid}
    ).json()
    assert all("correct" not in q for q in attempt["questions"])
    assert "feedback" not in attempt
    pre = client.post(
        f"/api/quizzes/{attempt['id']}/submit", headers=student, json={"answers": [1, 1, 0]}
    ).json()
    assert pre["score"] == 3
    assert (
        client.post(
            f"/api/bookings/{bid}/action",
            headers=mentor,
            json={"action": "confirm", "meeting_url": "https://example.org/study-room"},
        ).json()["status"]
        == "confirmed"
    )
    receipt = client.post(
        f"/api/bookings/{bid}/payment-simulation", headers=student, json={}
    ).json()
    assert receipt["charged"] == 0 and receipt["simulation"] is True
    assert receipt["commission"] == 375 and receipt["mentor_amount"] == 2125
    assert (
        client.post(f"/api/bookings/{bid}/payment-simulation", headers=student, json={}).json()
        == receipt
    )
    assert (
        client.post(
            f"/api/bookings/{bid}/action", headers=mentor, json={"action": "request_completion"}
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/bookings/{bid}/action", headers=student, json={"action": "complete"}
        ).json()["status"]
        == "completed"
    )
    post = client.post(
        "/api/quizzes", headers=student, json={"topic_id": 1, "stage": "post", "booking_id": bid}
    ).json()
    assert {q["id"] for q in post["questions"]}.isdisjoint(q["id"] for q in attempt["questions"])
    assert (
        client.post(
            f"/api/quizzes/{post['id']}/submit", headers=student, json={"answers": [1, 1, 0]}
        ).json()["score"]
        == 3
    )
    review = client.post(
        f"/api/bookings/{bid}/review",
        headers=student,
        json={"rating": 5, "comment": "Разобрался на примере"},
    )
    assert review.status_code == 200
    assert review.json()["review"]["rating"] == 5
    progress = client.get("/api/progress", headers=student).json()
    assert progress["plants"][0]["points"] == 70
    assert progress["completed_sessions"] == 2


def test_idempotency_and_conflicting_request_key(client):
    headers = login(client)
    body = proposal(client, headers)
    one = client.post("/api/bookings", headers=headers, json=body)
    two = client.post("/api/bookings", headers=headers, json=body)
    assert one.status_code == two.status_code == 200
    assert one.json()["id"] == two.json()["id"]
    assert (
        client.post("/api/bookings", headers=headers, json={**body, "topic_id": 2}).status_code
        == 409
    )


def test_concurrent_booking_has_one_winner(client):
    first, second = login(client), login(client, 3)
    body = proposal(client, first)

    def submit(headers):
        return client.post("/api/bookings", headers=headers, json=body).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        codes = list(executor.map(submit, [first, second]))
    assert sorted(codes) == [200, 409]


def test_foreign_booking_and_mentor_permissions(client):
    student, stranger, admin = login(client), login(client, 3), login(client, 99)
    booking = book(client, student)
    for headers in (stranger, student, admin):
        assert (
            client.post(
                f"/api/bookings/{booking['id']}/action",
                headers=headers,
                json={"action": "confirm", "meeting_url": "https://example.org/study-room"},
            ).status_code
            == 403
        )
    assert (
        client.post(
            f"/api/bookings/{booking['id']}/action", headers=stranger, json={"action": "cancel"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/bookings/{booking['id']}/payment-simulation", headers=stranger, json={}
        ).status_code
        == 403
    )
    assert client.get("/api/admin", headers=student).status_code == 403
    assert client.get("/api/admin", headers=admin).status_code == 200


def test_cancel_releases_slot_and_preserves_price(client):
    student, second = login(client), login(client, 3)
    body = proposal(client, student)
    booking = client.post("/api/bookings", headers=student, json=body).json()
    assert (
        client.post(
            f"/api/bookings/{booking['id']}/action", headers=student, json={"action": "cancel"}
        ).status_code
        == 200
    )
    result = client.post(
        "/api/bookings", headers=second, json={**body, "request_key": "second-booking-001"}
    )
    assert result.status_code == 200 and result.json()["price"] == 2500


def test_expiration_releases_slot_and_blocks_late_confirm(client):
    student, mentor = login(client), login(client, 2)
    booking = book(client, student)
    with client.app.state.db.transaction() as session:
        session.get(Booking, booking["id"]).expires_at = int(time.time()) - 1
    assert (
        client.post(
            f"/api/bookings/{booking['id']}/action",
            headers=mentor,
            json={"action": "confirm", "meeting_url": "https://example.org/study-room"},
        ).status_code
        == 409
    )
    rows = client.get("/api/bookings", headers=student).json()
    assert next(b for b in rows if b["id"] == booking["id"])["status"] == "expired"
    assert (
        client.post(
            "/api/bookings",
            headers=student,
            json={**proposal(client, student), "request_key": "after-expiration-001"},
        ).status_code
        == 200
    )


@pytest.mark.parametrize(
    "field,value", [("budget", 100), ("language", "kk"), ("topic_id", 3), ("deadline", 1)]
)
def test_server_rechecks_booking_conditions(client, field, value):
    student = login(client)
    body = proposal(client, student)
    assert client.post(
        "/api/bookings", headers=student, json={**body, field: value}
    ).status_code in (409, 422)


def test_no_matching_mentors_and_waitlist(client):
    headers = login(client)
    assert client.get("/api/mentors?topic_id=1&budget=1", headers=headers).json() == []
    payload = {
        "topic_id": 1,
        "budget": 1,
        "deadline": int(time.time()) + 86400,
        "earliest": int(time.time()),
        "language": "ru",
        "format": "online",
    }
    before = len(client.get("/api/waitlist", headers=headers).json())  # demo data has one
    assert client.post("/api/waitlist", headers=headers, json=payload).status_code == 200
    client.post("/api/waitlist", headers=headers, json=payload)
    assert len(client.get("/api/waitlist", headers=headers).json()) == before + 1


def test_reviews_require_completed_session_and_unique_author(client):
    student, stranger, mentor = login(client), login(client, 3), login(client, 2)
    booking = book(client, student)
    route = f"/api/bookings/{booking['id']}/review"
    review = {"rating": 5, "comment": "Хорошее занятие"}
    assert client.post(route, headers=student, json=review).status_code == 409
    assert client.post(route, headers=stranger, json=review).status_code == 403
    client.post(
        f"/api/bookings/{booking['id']}/action",
        headers=mentor,
        json={"action": "confirm", "meeting_url": "https://example.org/study-room"},
    )
    client.post(
        f"/api/bookings/{booking['id']}/action",
        headers=mentor,
        json={"action": "request_completion"},
    )
    client.post(
        f"/api/bookings/{booking['id']}/action", headers=student, json={"action": "complete"}
    )
    assert client.post(route, headers=student, json=review).status_code == 200
    assert client.post(route, headers=student, json=review).status_code == 409


def test_progress_cannot_be_farmed_and_attempts_are_private(client):
    student, stranger = login(client), login(client, 3)
    baseline = client.get("/api/progress", headers=student).json()["points"]
    attempt = client.post("/api/quizzes", headers=student, json={"topic_id": 1}).json()
    route = f"/api/quizzes/{attempt['id']}"
    assert client.get(route, headers=stranger).status_code == 403
    assert (
        client.post(route + "/submit", headers=stranger, json={"answers": [1, 1, 0]}).status_code
        == 403
    )
    first = client.post(route + "/submit", headers=student, json={"answers": [1, 1, 0]}).json()
    assert first["score"] == 3
    assert (
        client.post(route + "/submit", headers=student, json={"answers": [0, 0, 0]}).json()["score"]
        == 3
    )
    another = client.post("/api/quizzes", headers=student, json={"topic_id": 1}).json()
    client.post(
        f"/api/quizzes/{another['id']}/submit", headers=student, json={"answers": [1, 1, 0]}
    )
    assert client.get("/api/progress", headers=student).json()["points"] == baseline + 20


def test_post_quiz_not_available_before_session(client):
    headers = login(client)
    booking = book(client, headers)
    assert (
        client.post(
            "/api/quizzes",
            headers=headers,
            json={"topic_id": 1, "stage": "post", "booking_id": booking["id"]},
        ).status_code
        == 409
    )


def test_mentor_profile_verification_and_slot_overlap(client):
    mentor = login(client, 2)
    user = client.get("/api/me", headers=mentor).json()
    assert user["mentor"]["verified"] is True
    updated = client.put(
        "/api/mentor/profile",
        headers=mentor,
        json={**user["mentor"], "bio": "Новое описание способов объяснения и опыта в университете"},
    )
    assert updated.status_code == 200 and updated.json()["mentor"]["verified"] is False
    slot = client.get("/api/mentor/slots", headers=mentor).json()[0]
    assert (
        client.post(
            "/api/mentor/slots", headers=mentor, json={"starts_at": slot["starts_at"] + 900}
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/api/mentor/slots", headers=mentor, json={"starts_at": int(time.time()) - 3600}
        ).status_code
        == 422
    )


def test_persistence_and_demo_outbox_is_idempotent(client):
    headers = login(client)
    booking = book(client, headers)
    db = client.app.state.db
    asyncio.run(outbox_tick(db))
    with db.transaction() as session:
        rows = list(
            session.scalars(select(Notification).where(Notification.booking_id == booking["id"]))
        )
        assert len(rows) == 2 and all(n.status == "in_app" for n in rows)
    # A fresh app runs the same migrations and opens the same saved data.
    with TestClient(create_app(db.settings)) as restarted:
        rows = restarted.get("/api/bookings", headers=headers).json()
        assert any(b["id"] == booking["id"] for b in rows)
        asyncio.run(outbox_tick(restarted.app.state.db))
        with restarted.app.state.db.transaction() as session:
            assert (
                len(
                    list(
                        session.scalars(
                            select(Notification).where(Notification.booking_id == booking["id"])
                        )
                    )
                )
                == 2
            )


def test_overdue_cancelled_reminder_skipped(client):
    student, mentor = login(client), login(client, 2)
    booking = book(client, student)
    client.post(
        f"/api/bookings/{booking['id']}/action",
        headers=mentor,
        json={"action": "confirm", "meeting_url": "https://example.org/study-room"},
    )
    client.post(f"/api/bookings/{booking['id']}/action", headers=student, json={"action": "cancel"})
    with client.app.state.db.transaction() as session:
        for n in session.scalars(select(Notification).where(Notification.kind == "reminder")):
            n.due_at = int(time.time()) - 7200
    asyncio.run(outbox_tick(client.app.state.db))
    with client.app.state.db.transaction() as session:
        assert all(
            n.status == "skipped"
            for n in session.scalars(select(Notification).where(Notification.kind == "reminder"))
        )


@pytest.mark.parametrize("code", list(BANK))
def test_question_bank_has_distinct_valid_pre_post_sets(code):
    rows = BANK[code]
    assert len(rows) == 6 and len({q[0] for q in rows}) == 6
    assert all(
        len(options) == 3 and 0 <= answer < len(options) and explanation
        for _, options, answer, explanation in rows
    )
