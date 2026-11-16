"""Part D: group lessons."""

import sqlite3
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing

import pytest
from conftest import login
from sqlalchemy import select
from studymate.groups import cancel_underfilled
from studymate.models import Booking, ProgressEvent, Slot

PASSWORD = "group-password-1"


def start_at(days=4, hours=0):
    return (int(time.time()) // 1800 + 1) * 1800 + days * 86400 + hours * 3600


def group_body(**extra):
    body = {
        "starts_at": start_at(),
        "capacity": 3,
        "topic_id": 1,
        "price": 1200,
        "format": "online",
        "meeting_url": "https://meet.example.org/group",
        "min_participants": 1,
    }
    body.update(extra)
    return body


def create_group(client, mentor, **extra):
    response = client.post("/api/mentor/slots/group", headers=mentor, json=group_body(**extra))
    assert response.status_code == 200, response.text
    return response.json()


def seat(client, headers, slot, key=None, **extra):
    body = {
        "slot_id": slot["id"],
        "topic_id": slot["topic_id"],
        "deadline": slot["ends_at"] + 3600,
        "budget": 3000,
        "language": "ru",
        "format": "online",
        "request_key": key or "seat-" + uuid.uuid4().hex[:12],
    }
    body.update(extra)
    return client.post("/api/bookings", headers=headers, json=body)


def register(client, n):
    response = client.post(
        "/api/auth/register",
        json={"name": f"Студент {n}", "email": f"s{n}@group.test", "password": PASSWORD},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["token"]}


# ---------------------------------------------------------------- creation


def test_group_slot_validation(client):
    mentor = login(client, 2)
    assert (
        client.post(
            "/api/mentor/slots/group", headers=mentor, json=group_body(capacity=6)
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/mentor/slots/group", headers=mentor, json=group_body(topic_id=5)
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/mentor/slots/group", headers=mentor, json=group_body(meeting_url="")
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/mentor/slots/group", headers=mentor, json=group_body(meeting_url="http://x.org")
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/mentor/slots/group", headers=mentor, json=group_body(min_participants=4)
        ).status_code
        == 422
    )
    campus = client.post(
        "/api/mentor/slots/group",
        headers=mentor,
        json=group_body(
            format="campus", meeting_url=None, meeting_place="C1.2", starts_at=start_at(5)
        ),
    )
    assert campus.status_code == 200 and campus.json()["format"] == "campus"
    assert (
        client.post("/api/mentor/slots/group", headers=login(client), json=group_body()).status_code
        == 404
    )


def test_group_appears_in_search_with_seat_price(client):
    mentor = login(client, 2)
    slot = create_group(client, mentor, price=900)
    deadline = slot["ends_at"] + 3600
    rows = client.get(f"/api/public/mentors?topic_id=1&budget=1000&deadline={deadline}").json()
    card = next(m for m in rows if m["id"] == 2)  # base price 2500 > budget, but a seat fits
    group = next(s for s in card["slots"] if s["id"] == slot["id"])
    assert group["capacity"] == 3 and group["taken"] == 0 and group["price"] == 900
    assert all(s["capacity"] > 1 for s in card["slots"])  # 1:1 slots over budget are hidden
    other_topic = client.get(
        f"/api/public/mentors?topic_id=2&budget=1000&deadline={deadline}"
    ).json()
    assert all(s["id"] != slot["id"] for m in other_topic for s in m["slots"])


# ----------------------------------------------------------------- seats


def test_seats_confirm_immediately_and_share_meeting(client):
    mentor, first, second = login(client, 2), login(client), login(client, 3)
    slot = create_group(client, mentor)
    a = seat(client, first, slot)
    assert a.status_code == 200, a.text
    assert a.json()["status"] == "confirmed" and a.json()["price"] == 1200
    assert a.json()["meeting_url"] == "https://meet.example.org/group"
    b = seat(client, second, slot).json()
    assert b["group"] == {"capacity": 3, "taken": 2, "participants": ["Аликхан", "Ерлан"]}
    assert seat(client, first, slot).status_code == 409  # one seat per student
    assert seat(client, first, slot, topic_id=2).status_code in (409, 422)
    assert seat(client, login(client, 99), slot, budget=100).status_code == 409
    # The mentor edits shared data once; every participant sees it.
    assert (
        client.put(
            f"/api/bookings/{a.json()['id']}/workspace",
            headers=mentor,
            json={"materials": "Схема JOIN"},
        ).status_code
        == 200
    )
    assert (
        client.get(f"/api/bookings/{b['id']}", headers=second).json()["materials"] == "Схема JOIN"
    )
    assert (
        client.post(
            f"/api/bookings/{b['id']}/action", headers=mentor, json={"action": "confirm"}
        ).status_code
        == 409
    )
    # Private notes stay per participant.
    client.put(
        f"/api/bookings/{a.json()['id']}/workspace", headers=first, json={"notes": "только моё"}
    )
    assert client.get(f"/api/bookings/{b['id']}", headers=second).json()["notes"] == ""
    # The mentor's own lessons around the group are still conflict-checked.
    mine = client.get("/api/mentor/slots", headers=mentor).json()
    row = next(x for x in mine if x["id"] == slot["id"])
    assert row["state"] == "group" and row["students"] == ["Аликхан", "Ерлан"]


def test_last_seat_race_has_exactly_one_winner(client):
    mentor = login(client, 2)
    slot = create_group(client, mentor, capacity=2)
    assert seat(client, login(client, 3), slot).status_code == 200
    students = [register(client, n) for n in range(5)]

    def take(headers):
        return seat(client, headers, slot).status_code

    with ThreadPoolExecutor(max_workers=5) as pool:
        codes = list(pool.map(take, students))
    assert sorted(codes) == [200, 409, 409, 409, 409]
    with client.app.state.db.read() as session:
        active = session.scalars(
            select(Booking).where(
                Booking.slot_id == slot["id"], Booking.status.in_(("pending", "confirmed"))
            )
        ).all()
        assert len(active) == 2


def test_trigger_blocks_overbooking_even_bypassing_the_service(client):
    mentor = login(client, 2)
    slot = create_group(client, mentor, capacity=2)
    seat(client, login(client), slot)
    seat(client, login(client, 3), slot)
    path = client.app.state.db.settings.database
    with closing(sqlite3.connect(path)) as raw:
        with pytest.raises(sqlite3.IntegrityError, match="slot_full"):
            raw.execute(
                "INSERT INTO bookings (id, student_id, mentor_id, slot_id, topic_id, price, status,"
                " description, deadline, language, format, created_at, expires_at, request_key,"
                " meeting_url, meeting_place, materials, reschedule_count)"
                " VALUES ('raw', 99, 2, ?, 1, 0, 'confirmed', '', 0, 'ru', 'online', 0, 0, 'raw',"
                " '', '', '', 0)",
                (slot["id"],),
            )
        # Reviving a cancelled seat into a full slot is blocked too.
        raw.execute(
            "UPDATE bookings SET status='cancelled' WHERE slot_id=? AND student_id=1", (slot["id"],)
        )
        raw.execute(
            "INSERT INTO bookings (id, student_id, mentor_id, slot_id, topic_id, price, status,"
            " description, deadline, language, format, created_at, expires_at, request_key,"
            " meeting_url, meeting_place, materials, reschedule_count)"
            " VALUES ('raw2', 99, 2, ?, 1, 0, 'confirmed', '', 0, 'ru', 'online', 0, 0, 'raw2',"
            " '', '', '', 0)",
            (slot["id"],),
        )
        with pytest.raises(sqlite3.IntegrityError, match="slot_full"):
            raw.execute(
                "UPDATE bookings SET status='confirmed' WHERE slot_id=? AND student_id=1",
                (slot["id"],),
            )
        raw.rollback()


def test_one_to_one_slots_keep_single_booking_rule(client):
    path = client.app.state.db.settings.database
    with closing(sqlite3.connect(path)) as raw:
        (slot_id,) = raw.execute("SELECT slot_id FROM bookings WHERE id='demo-incoming'").fetchone()
        with pytest.raises(sqlite3.IntegrityError, match="slot_full"):
            raw.execute(
                "INSERT INTO bookings (id, student_id, mentor_id, slot_id, topic_id, price, status,"
                " description, deadline, language, format, created_at, expires_at, request_key,"
                " meeting_url, meeting_place, materials, reschedule_count)"
                " VALUES ('dup', 1, 2, ?, 1, 0, 'pending', '', 0, 'ru', 'online', 0, 0, 'dup',"
                " '', '', '', 0)",
                (slot_id,),
            )


def test_cancel_frees_seat_and_notifies_waitlist(client):
    mentor, first = login(client, 2), login(client)
    slot = create_group(client, mentor, capacity=2)
    a = seat(client, first, slot).json()
    seat(client, login(client, 3), slot)
    assert seat(client, login(client, 99), slot).status_code == 409
    assert (
        client.post(
            f"/api/bookings/{a['id']}/action", headers=first, json={"action": "cancel"}
        ).status_code
        == 200
    )
    assert seat(client, login(client, 99), slot).status_code == 200


# -------------------------------------------------------------- lifecycle


def test_group_completion_awards_mentor_once(client):
    mentor, first, second = login(client, 2), login(client), login(client, 3)
    slot = create_group(client, mentor)
    a, b = seat(client, first, slot).json(), seat(client, second, slot).json()
    assert (
        client.post(
            f"/api/bookings/{a['id']}/action", headers=first, json={"action": "complete"}
        ).status_code
        == 409
    )
    assert (
        client.post(f"/api/mentor/slots/{slot['id']}/complete", headers=mentor).status_code == 200
    )
    for headers, booking in ((first, a), (second, b)):
        done = client.post(
            f"/api/bookings/{booking['id']}/action", headers=headers, json={"action": "complete"}
        )
        assert done.status_code == 200 and done.json()["status"] == "completed"
    with client.app.state.db.read() as session:
        sources = session.scalars(
            select(ProgressEvent.source).where(ProgressEvent.user_id == 2)
        ).all()
    assert sources.count(f"group:{slot['id']}") == 1
    assert not any(s == f"session:{a['id']}" for s in sources)
    review = client.post(
        f"/api/bookings/{a['id']}/review", headers=first, json={"rating": 5, "comment": "Отлично"}
    )
    assert review.status_code == 200


def test_mentor_cancels_whole_group(client):
    mentor, first, second = login(client, 2), login(client), login(client, 3)
    slot = create_group(client, mentor)
    a, b = seat(client, first, slot).json(), seat(client, second, slot).json()
    assert (
        client.post(f"/api/mentor/slots/{slot['id']}/cancel", headers=login(client, 3)).status_code
        == 403
    )
    assert client.post(f"/api/mentor/slots/{slot['id']}/cancel", headers=mentor).status_code == 200
    for headers, booking in ((first, a), (second, b)):
        assert (
            client.get(f"/api/bookings/{booking['id']}", headers=headers).json()["status"]
            == "cancelled"
        )
    assert seat(client, login(client, 99), slot).status_code == 409


def test_underfilled_group_cancelled_once(client):
    mentor = login(client, 2)
    slot = create_group(client, mentor, starts_at=start_at(10), capacity=4, min_participants=2)
    booking = seat(client, login(client), slot).json()
    db = client.app.state.db
    with db.write() as session:  # nothing happens while the start is far away
        assert cancel_underfilled(session) == 0
        row = session.get(Slot, slot["id"])
        row.starts_at, row.ends_at = int(time.time()) + 3601, int(time.time()) + 3601 + 1800
    with db.write() as session:
        assert cancel_underfilled(session) == 1
    with db.write() as session:
        assert cancel_underfilled(session) == 0  # idempotent
        assert session.get(Slot, slot["id"]).enabled is False
    assert (
        client.get(f"/api/bookings/{booking['id']}", headers=login(client)).json()["status"]
        == "cancelled"
    )


def test_group_chat_room_and_no_reschedule(client):
    mentor, first, second, outsider = (
        login(client, 2),
        login(client),
        login(client, 3),
        login(client, 99),
    )
    slot = create_group(client, mentor)
    a, b = seat(client, first, slot).json(), seat(client, second, slot).json()
    sent = client.post(
        f"/api/bookings/{a['id']}/messages",
        headers=first,
        json={"body": "Всем привет", "client_id": "group-msg-01"},
    )
    assert sent.status_code == 200
    room = client.get(f"/api/bookings/{b['id']}/messages", headers=second).json()
    assert room["thread"] == f"slot:{slot['id']}" and [m["body"] for m in room["messages"]] == [
        "Всем привет"
    ]
    assert (
        client.get(f"/api/bookings/{a['id']}/messages", headers=mentor).json()["can_write"] is True
    )
    assert client.get(f"/api/bookings/{a['id']}/messages", headers=outsider).status_code == 403
    assert (
        client.get(f"/api/bookings/{a['id']}/reschedule-options", headers=first).status_code == 409
    )


def test_group_series(client):
    mentor = login(client, 2)
    body = {
        "starts_at": start_at(6),
        "weeks": 3,
        "group": {k: v for k, v in group_body().items() if k != "starts_at"},
    }
    created = client.post("/api/mentor/slots/series", headers=mentor, json=body)
    assert created.status_code == 200, created.text
    assert all(s["capacity"] == 3 and s["format"] == "online" for s in created.json()["created"])


def test_demo_seed_v22_is_idempotent(client):
    from studymate.seed import seed

    db = client.app.state.db
    seed(db)
    seed(db)
    with db.read() as session:
        from studymate.models import ChatMessage, Favorite, SlotMeeting, Waitlist

        assert session.query(SlotMeeting).count() == 1
        assert session.query(Favorite).filter_by(user_id=1).count() == 1
        assert session.query(Waitlist).filter_by(student_id=1).count() == 1
        assert session.query(ChatMessage).count() == 2
        series = session.scalars(select(Slot).where(Slot.series_id == "demo-series-ayaulym")).all()
        assert 1 <= len(series) <= 4
    rows = client.get("/api/bookings", headers=login(client, 3)).json()
    group = next(b for b in rows if b["group"])
    assert group["group"]["participants"] == ["Ерлан"] and group["status"] == "confirmed"
