"""Part A: event bus, SSE stream with tickets, lesson chat."""

import asyncio
import json
import threading
import time

import pytest
from conftest import book, login
from sqlalchemy import select
from studymate.events import CLOSE, EventBus, TicketStore, end_sessions, queue_event
from studymate.models import Notification


def send(client, headers, bid, body, key):
    return client.post(
        f"/api/bookings/{bid}/messages", headers=headers, json={"body": body, "client_id": key}
    )


# ---------------------------------------------------------------- bus


def test_events_publish_only_after_commit(client):
    db = client.app.state.db
    published = []
    db.bus.publish = published.extend
    with db.write() as session:
        queue_event(session, "booking", "b1", [1, 2])
    assert published == [{"type": "booking", "id": "b1", "users": [1, 2]}]
    published.clear()
    with pytest.raises(RuntimeError), db.write() as session:
        queue_event(session, "booking", "b2", [1])
        raise RuntimeError("boom")
    assert published == []


def test_session_ended_targets_tokens():
    async def scenario():
        bus = EventBus()
        bus.bind(asyncio.get_running_loop())
        a, b, other = bus.subscribe(1, "tok-a"), bus.subscribe(1, "tok-b"), bus.subscribe(2, "x")
        bus._dispatch([{"type": "session_ended", "id": 1, "users": [1], "keep_token": "tok-a"}])
        assert not a.closed and b.closed and not other.closed
        bus._dispatch([{"type": "thread", "id": "booking:1", "users": [1, 2]}])
        assert a.queue.get_nowait() == {"type": "thread", "id": "booking:1"}
        assert b.queue.get_nowait() is CLOSE
        bus._dispatch([{"type": "session_ended", "id": 1, "users": [1], "only_token": "tok-a"}])
        assert a.closed
        for _ in range(5):
            assert bus.subscribe(3, "t") is not None
        assert bus.subscribe(3, "t") is None  # stream limit per user

    asyncio.run(scenario())


def test_slow_subscriber_is_closed_instead_of_blocking():
    async def scenario():
        bus = EventBus()
        bus.bind(asyncio.get_running_loop())
        sub = bus.subscribe(1, "t")
        bus._dispatch([{"type": "thread", "id": i, "users": [1]} for i in range(150)])
        assert sub.closed

    asyncio.run(scenario())


def test_tickets_are_single_use_and_expire():
    store = TicketStore()
    ticket = store.issue(1, "hash")
    assert store.redeem(ticket) == (1, "hash")
    assert store.redeem(ticket) is None
    assert TicketStore(lifetime=-1).redeem(TicketStore(lifetime=-1).issue(1, "h")) is None
    expired = TicketStore(lifetime=-1)
    assert expired.redeem(expired.issue(1, "h")) is None


def test_end_sessions_is_queued_until_commit(client):
    db = client.app.state.db
    published = []
    db.bus.publish = published.extend
    with db.write() as session:
        end_sessions(session, 7, keep_token="k")
    assert published[0]["type"] == "session_ended" and published[0]["keep_token"] == "k"


# ------------------------------------------------------------ stream


class StreamReader:
    """Reads an SSE stream in a background thread."""

    def __init__(self, client, ticket):
        self.events, self.lines = [], []
        self.status = None
        self.done = threading.Event()
        self.thread = threading.Thread(target=self._run, args=(client, ticket), daemon=True)
        self.thread.start()

    def _run(self, client, ticket):
        with client.stream("GET", f"/api/events?ticket={ticket}") as response:
            self.status = response.status_code
            for line in response.iter_lines():
                self.lines.append(line)
                if line.startswith("data: "):
                    self.events.append(json.loads(line[6:]))
        self.done.set()

    def wait_for(self, predicate, timeout=5):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate(self):
                return True
            time.sleep(0.05)
        return False


def ticket(client, headers):
    response = client.post("/api/events/ticket", headers=headers)
    assert response.status_code == 200
    return response.json()["ticket"]


def test_stream_delivers_hints_and_closes_on_logout_everywhere(client):
    client.app.state.heartbeat_seconds = 0.2
    student, mentor = login(client), login(client, 2)
    booking = book(client, student)
    reader = StreamReader(client, ticket(client, mentor))
    assert reader.wait_for(lambda r: r.status == 200)
    assert reader.wait_for(lambda r: any(line == ": ping" for line in r.lines))

    # The stream holds no transaction: writes go through while it is open.
    started = time.monotonic()
    with client.app.state.db.write():
        pass
    assert time.monotonic() - started < 2

    assert send(client, student, booking["id"], "Привет!", "msg-00000001").status_code == 200
    assert reader.wait_for(
        lambda r: {"type": "thread", "id": f"booking:{booking['id']}"} in r.events
    )
    assert all("Привет" not in line for line in reader.lines)  # hints only, no content

    assert client.post("/api/auth/logout-all", headers=mentor).status_code == 200
    assert reader.done.wait(5)
    assert any("session_ended" in line for line in reader.lines)


def test_stream_rejects_bad_tickets_and_too_many_tabs(client):
    assert client.get("/api/events?ticket=nope").status_code == 401
    assert client.post("/api/events/ticket").status_code == 401
    headers = login(client)
    used = ticket(client, headers)
    client.app.state.tickets.redeem(used)
    assert client.get(f"/api/events?ticket={used}").status_code == 401
    for _ in range(5):
        client.app.state.db.bus.subscribe(1, "other-tab")
    assert client.get(f"/api/events?ticket={ticket(client, headers)}").status_code == 429


def test_stream_ends_when_token_expires(client):
    client.app.state.heartbeat_seconds = 0.1
    headers = login(client)
    reader = StreamReader(client, ticket(client, headers))
    assert reader.wait_for(lambda r: r.status == 200)
    from studymate.models import SessionToken

    with client.app.state.db.write() as session:
        for token in session.scalars(select(SessionToken)):
            token.expires_at = 0
    assert reader.done.wait(5)
    assert any("session_ended" in line for line in reader.lines)


# -------------------------------------------------------------- chat


def test_chat_between_participants_only(client):
    student, mentor, other, team = (
        login(client),
        login(client, 2),
        login(client, 3),
        login(client, 99),
    )
    bid = book(client, student)["id"]
    sent = send(client, student, bid, "  Можно разобрать LEFT JOIN?  ", "msg-00000001")
    assert sent.status_code == 200 and sent.json()["body"] == "Можно разобрать LEFT JOIN?"
    thread = client.get(f"/api/bookings/{bid}/messages", headers=mentor).json()
    assert [m["body"] for m in thread["messages"]] == ["Можно разобрать LEFT JOIN?"]
    assert thread["can_write"] and thread["thread"] == f"booking:{bid}"
    for outsider in (other, team):
        assert client.get(f"/api/bookings/{bid}/messages", headers=outsider).status_code == 403
        assert send(client, outsider, bid, "Привет", "msg-out-0001").status_code == 403
    assert send(client, mentor, bid, "   ", "msg-blank-001").status_code == 422
    after = client.get(f"/api/bookings/{bid}/messages?after_id=999", headers=mentor).json()
    assert after["messages"] == []


def test_chat_idempotent_and_read_only_after_cancel(client):
    student, mentor = login(client), login(client, 2)
    bid = book(client, student)["id"]
    first = send(client, student, bid, "Раз", "msg-same-0001").json()
    again = send(client, student, bid, "Раз", "msg-same-0001").json()
    assert first["id"] == again["id"]
    assert len(client.get(f"/api/bookings/{bid}/messages", headers=student).json()["messages"]) == 1
    client.post(f"/api/bookings/{bid}/action", headers=student, json={"action": "cancel"})
    thread = client.get(f"/api/bookings/{bid}/messages", headers=mentor).json()
    assert not thread["can_write"] and len(thread["messages"]) == 1
    assert send(client, mentor, bid, "Жаль", "msg-late-0001").status_code == 409


def test_one_notification_per_unread_batch_and_unread_counter(client):
    student, mentor = login(client), login(client, 2)
    bid = book(client, student)["id"]
    for i in range(3):
        send(client, student, bid, f"Сообщение {i}", f"msg-batch-{i:04d}")

    def message_notices():
        with client.app.state.db.read() as session:
            return session.scalars(
                select(Notification).where(
                    Notification.user_id == 2, Notification.kind == "message"
                )
            ).all()

    assert len(message_notices()) == 1
    rows = client.get("/api/bookings", headers=mentor).json()
    assert next(b for b in rows if b["id"] == bid)["unread_messages"] == 3
    thread = client.get(f"/api/bookings/{bid}/messages", headers=mentor).json()
    last = thread["messages"][-1]["id"]
    assert (
        client.post(
            f"/api/bookings/{bid}/messages/read", headers=mentor, json={"last_read_id": last}
        ).status_code
        == 200
    )
    assert (
        next(b for b in client.get("/api/bookings", headers=mentor).json() if b["id"] == bid)[
            "unread_messages"
        ]
        == 0
    )
    assert (
        client.get(f"/api/bookings/{bid}/messages", headers=student).json()["others_last_read_id"]
        == last
    )
    send(client, student, bid, "Ещё вопрос", "msg-batch-9999")
    assert len(message_notices()) == 2
    # The team sees no chat counters in its overview of all bookings.
    team_rows = client.get("/api/admin", headers=login(client, 99)).json()["bookings"]
    assert next(b for b in team_rows if b["id"] == bid)["unread_messages"] == 0


def test_chat_rate_limit(client):
    student = login(client)
    bid = book(client, student)["id"]
    codes = [send(client, student, bid, "x", f"msg-rate-{i:04d}").status_code for i in range(21)]
    assert codes[:20] == [200] * 20 and codes[20] == 429


def test_export_contains_only_own_messages(client):
    student, mentor = login(client), login(client, 2)
    bid = book(client, student)["id"]
    send(client, student, bid, "Мой вопрос", "msg-exp-0001")
    send(client, mentor, bid, "Ответ ментора", "msg-exp-0002")
    exported = client.get("/api/me/export", headers=student).json()["messages"]
    assert [m["body"] for m in exported] == ["Мой вопрос"]
