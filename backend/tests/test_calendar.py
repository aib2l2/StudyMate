"""Part C: slot series, rescheduling, iCalendar export."""

import re
import time

from conftest import book, login
from sqlalchemy import select
from studymate.ics import calendar, escape, fold
from studymate.inbox import deliver_notifications
from studymate.models import Booking, LessonNote, Notification, Slot

WEEK = 7 * 86400


def future(days=30, hour_offset=0):
    return (int(time.time()) // 1800 + 1) * 1800 + days * 86400 + hour_offset * 3600


def series(client, headers, start, weeks):
    return client.post(
        "/api/mentor/slots/series", headers=headers, json={"starts_at": start, "weeks": weeks}
    )


def confirm(client, booking, mentor):
    response = client.post(
        f"/api/bookings/{booking['id']}/action",
        headers=mentor,
        json={"action": "confirm", "meeting_url": "https://meet.example.org/x"},
    )
    assert response.status_code == 200, response.text
    return response.json()


# ------------------------------------------------------------------ series


def test_series_creates_weekly_slots_and_skips_conflicts(client):
    mentor = login(client, 2)
    start = future()
    assert (
        client.post(
            "/api/mentor/slots", headers=mentor, json={"starts_at": start + 2 * WEEK}
        ).status_code
        == 200
    )
    response = series(client, mentor, start, 4)
    assert response.status_code == 200, response.text
    body = response.json()
    assert [s["starts_at"] for s in body["created"]] == [start, start + WEEK, start + 3 * WEEK]
    assert body["skipped"] == [
        {"starts_at": start + 2 * WEEK, "reason": "Этот интервал пересекается с вашим расписанием"}
    ]
    assert {s["series_id"] for s in body["created"]} == {body["series_id"]}
    mine = client.get("/api/mentor/slots", headers=mentor).json()
    assert sum(s.get("series_id") == body["series_id"] for s in mine) == 3


def test_series_beyond_90_days_is_skipped_and_validated(client):
    mentor = login(client, 2)
    body = series(client, mentor, future(80), 4).json()
    assert len(body["created"]) == 2 and len(body["skipped"]) == 2
    assert series(client, mentor, future(), 1).status_code == 422
    assert series(client, mentor, future(), 13).status_code == 422
    assert series(client, mentor, future(200), 2).status_code == 409  # nothing fits
    assert series(client, login(client), future(), 2).status_code == 404  # not a mentor


def test_close_series_keeps_booked_occurrences(client):
    mentor, student = login(client, 2), login(client)
    body = series(client, mentor, future(3), 3).json()
    first = body["created"][0]
    deadline = first["ends_at"] + 3600
    booking = client.post(
        "/api/bookings",
        headers=student,
        json={
            "slot_id": first["id"],
            "topic_id": 1,
            "deadline": deadline,
            "budget": 3000,
            "language": "ru",
            "format": "online",
            "request_key": "series-booking-1",
        },
    )
    assert booking.status_code == 200, booking.text
    closed = client.delete(f"/api/mentor/series/{body['series_id']}", headers=mentor).json()
    assert closed == {"closed": 2, "kept_with_bookings": 1}
    assert (
        client.delete(
            f"/api/mentor/series/{body['series_id']}", headers=login(client, 3)
        ).status_code
        == 403
    )
    assert client.delete("/api/mentor/series/missing", headers=mentor).status_code == 404


# -------------------------------------------------------------- reschedule


def test_accepting_reschedule_keeps_booking_notes_and_chat(client):
    student, mentor = login(client), login(client, 2)
    booking = confirm(client, book(client, student), mentor)
    bid = booking["id"]
    client.put(f"/api/bookings/{bid}/workspace", headers=student, json={"notes": "моя заметка"})
    client.post(
        f"/api/bookings/{bid}/messages",
        headers=student,
        json={"body": "до переноса", "client_id": "resched-msg-1"},
    )
    options = client.get(f"/api/bookings/{bid}/reschedule-options", headers=student).json()
    assert options and all(o["id"] != booking["slot"]["id"] for o in options)
    target = options[-1]
    req = client.post(
        f"/api/bookings/{bid}/reschedule", headers=student, json={"slot_id": target["id"]}
    )
    assert req.status_code == 200, req.text
    rid = req.json()["id"]
    lesson = client.get(f"/api/bookings/{bid}", headers=mentor).json()
    assert lesson["reschedule"]["proposed_slot"]["id"] == target["id"]
    assert (
        client.post(f"/api/reschedule/{rid}/accept", headers=student).status_code == 403
    )  # own proposal
    moved = client.post(f"/api/reschedule/{rid}/accept", headers=mentor)
    assert moved.status_code == 200, moved.text
    assert moved.json()["id"] == bid and moved.json()["slot"]["id"] == target["id"]
    assert moved.json()["price"] == booking["price"] and moved.json()["reschedule"] is None
    after = client.get(f"/api/bookings/{bid}", headers=student).json()
    assert after["notes"] == "моя заметка"
    assert [
        m["body"]
        for m in client.get(f"/api/bookings/{bid}/messages", headers=student).json()["messages"]
    ] == ["до переноса"]
    assert (
        client.post(f"/api/reschedule/{rid}/accept", headers=mentor).status_code == 409
    )  # already used


def test_old_reminder_skipped_new_one_scheduled(client):
    student, mentor = login(client), login(client, 2)
    booking = confirm(client, book(client, student), mentor)
    bid, old_slot = booking["id"], booking["slot"]["id"]
    target = client.get(f"/api/bookings/{bid}/reschedule-options", headers=mentor).json()[-1]
    rid = client.post(
        f"/api/bookings/{bid}/reschedule", headers=mentor, json={"slot_id": target["id"]}
    ).json()["id"]
    client.post(f"/api/reschedule/{rid}/accept", headers=student)
    db = client.app.state.db
    with db.write() as session:  # make every reminder due now
        for n in session.scalars(select(Notification).where(Notification.kind == "reminder")):
            n.due_at = int(time.time()) - 1
    deliver_notifications(db)
    with db.read() as session:
        rows = session.scalars(
            select(Notification).where(
                Notification.booking_id == bid, Notification.kind == "reminder"
            )
        ).all()
        by_slot = {(n.slot_id, n.status) for n in rows}
    assert (old_slot, "skipped") in by_slot
    assert (target["id"], "in_app") in by_slot


def test_reschedule_conflicts_and_single_pending(client):
    student, mentor, other = login(client), login(client, 2), login(client, 3)
    booking = book(client, student)
    bid = booking["id"]
    options = client.get(f"/api/bookings/{bid}/reschedule-options", headers=student).json()
    first, second = options[0], options[1]
    assert (
        client.post(
            f"/api/bookings/{bid}/reschedule", headers=other, json={"slot_id": first["id"]}
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/bookings/{bid}/reschedule",
            headers=student,
            json={"slot_id": booking["slot"]["id"]},
        ).status_code
        == 422
    )
    rid = client.post(
        f"/api/bookings/{bid}/reschedule", headers=student, json={"slot_id": first["id"]}
    ).json()["id"]
    assert (
        client.post(
            f"/api/bookings/{bid}/reschedule", headers=mentor, json={"slot_id": second["id"]}
        ).status_code
        == 409
    )
    # Someone else takes the proposed slot before the mentor answers.
    with client.app.state.db.write() as session:
        session.get(Slot, first["id"]).enabled = False
    assert client.post(f"/api/reschedule/{rid}/accept", headers=mentor).status_code == 409
    assert client.post(f"/api/reschedule/{rid}/cancel", headers=mentor).status_code == 403
    assert client.post(f"/api/reschedule/{rid}/cancel", headers=student).status_code == 200
    rid2 = client.post(
        f"/api/bookings/{bid}/reschedule", headers=student, json={"slot_id": second["id"]}
    ).json()["id"]
    assert client.post(f"/api/reschedule/{rid2}/decline", headers=mentor).status_code == 200
    assert (
        client.get(f"/api/bookings/{bid}", headers=student).json()["slot"]["id"]
        == booking["slot"]["id"]
    )


def test_expired_proposal_is_replaced_and_past_lessons_stay(client):
    student, mentor = login(client), login(client, 2)
    bid = book(client, student)["id"]
    options = client.get(f"/api/bookings/{bid}/reschedule-options", headers=student).json()
    rid = client.post(
        f"/api/bookings/{bid}/reschedule", headers=student, json={"slot_id": options[0]["id"]}
    ).json()["id"]
    from studymate.models import RescheduleRequest

    with client.app.state.db.write() as session:
        session.get(RescheduleRequest, rid).expires_at = int(time.time()) - 1
    assert client.get(f"/api/bookings/{bid}", headers=student).json()["reschedule"] is None
    assert client.post(f"/api/reschedule/{rid}/accept", headers=mentor).status_code == 409
    assert (
        client.post(
            f"/api/bookings/{bid}/reschedule", headers=student, json={"slot_id": options[1]["id"]}
        ).status_code
        == 200
    )
    client.post(f"/api/bookings/{bid}/action", headers=student, json={"action": "cancel"})
    assert client.get(f"/api/bookings/{bid}/reschedule-options", headers=student).status_code == 409


# --------------------------------------------------------------------- ics


def unfold(text: str) -> list[str]:
    return text.replace("\r\n ", "").split("\r\n")


def test_ics_folding_escaping_and_utc():
    long_name = "Разбор " + "очень длинной темы " * 10 + "; с запятой, и\nпереносом"
    body = calendar(
        [
            {
                "uid": "b1@studymate.local",
                "start": 1_800_000_000,
                "end": 1_800_001_800,
                "summary": long_name,
                "location": "Аудитория C1.2",
                "url": "https://meet.example.org/a,b",
                "sequence": 2,
            }
        ],
        1_799_000_000,
    )
    raw_lines = body.split("\r\n")
    assert all(len(line.encode()) <= 75 for line in raw_lines)
    assert body.endswith("\r\n") and "\n" not in body.replace("\r\n", "")
    lines = unfold(body)
    summary = next(line for line in lines if line.startswith("SUMMARY:"))
    assert summary == "SUMMARY:" + escape(long_name)
    assert "\\;" in summary and "\\," in summary and "\\n" in summary
    assert "DTSTART:20270115T080000Z" in lines and "SEQUENCE:2" in lines
    assert fold("я" * 100).count("\r\n ") == 2  # 37 + 37 + 26 two-byte chars


def test_ics_downloads_for_participants_only(client):
    student, mentor, other = login(client), login(client, 2), login(client, 3)
    booking = book(client, student)
    bid = booking["id"]
    assert client.get(f"/api/bookings/{bid}/calendar.ics", headers=student).status_code == 409
    confirm(client, booking, mentor)
    response = client.get(f"/api/bookings/{bid}/calendar.ics", headers=student)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/calendar")
    text = response.text
    assert f"UID:{bid}@studymate.local" in text and "URL:https://meet.example.org/x" in text
    assert re.search(r"DTSTART:\d{8}T\d{6}Z", text)
    assert client.get(f"/api/bookings/{bid}/calendar.ics", headers=other).status_code == 403
    everything = client.get("/api/calendar.ics", headers=mentor).text
    assert everything.count("BEGIN:VEVENT") >= 1 and f"{bid}@studymate.local" in everything
    with client.app.state.db.read() as session:
        assert session.get(Booking, bid).reschedule_count == 0
        assert session.get(LessonNote, (bid, 1)) is None
