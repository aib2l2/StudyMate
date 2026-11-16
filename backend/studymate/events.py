"""In-process event bus for live updates (Server-Sent Events).

Design:

* An event is only a *hint* that something changed: ``{"type", "id"}``. The
  browser re-fetches the data through the normal API, so a lost event never
  loses data and duplicates are harmless.
* Events are published **after commit** only. Service code calls
  ``queue_event(session, ...)``; a Session ``after_commit`` hook hands the batch
  to the bus, ``after_rollback`` drops it.
* Request handlers run in a thread pool, so delivery hops onto the event loop
  with ``call_soon_threadsafe``.
* One uvicorn process: subscribers live in memory. Several processes would
  need an external broker.
"""

import asyncio
import hashlib
import itertools
import secrets
import threading
import time
from dataclasses import dataclass, field

from sqlalchemy import event as sa_event
from sqlalchemy.orm import Session

STREAMS_PER_USER = 5
TICKET_SECONDS = 30
CLOSE = object()  # sentinel put into a subscriber queue to end its stream


@dataclass(eq=False)
class Subscriber:
    user_id: int
    token_hash: str
    queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=100))
    closed: bool = False


class EventBus:
    def __init__(self):
        self.loop: asyncio.AbstractEventLoop | None = None
        self._subs: dict[int, set[Subscriber]] = {}
        self._lock = threading.Lock()
        self._ids = itertools.count(1)

    def bind(self, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop

    def next_id(self) -> int:
        return next(self._ids)

    # -- subscriptions (called on the event loop)
    def subscribe(self, user_id: int, token_hash: str) -> Subscriber | None:
        with self._lock:
            current = self._subs.setdefault(user_id, set())
            if len(current) >= STREAMS_PER_USER:
                return None
            sub = Subscriber(user_id, token_hash)
            current.add(sub)
            return sub

    def unsubscribe(self, sub: Subscriber) -> None:
        with self._lock:
            subs = self._subs.get(sub.user_id)
            if subs is not None:
                subs.discard(sub)
                if not subs:
                    del self._subs[sub.user_id]

    def count(self, user_id: int) -> int:
        with self._lock:
            return len(self._subs.get(user_id, ()))

    # -- publishing (any thread)
    def publish(self, events: list[dict]) -> None:
        if not events:
            return
        if self.loop is None or self.loop.is_closed():
            return
        self.loop.call_soon_threadsafe(self._dispatch, list(events))

    def _close(self, sub: Subscriber) -> None:
        if sub.closed:
            return
        sub.closed = True
        while True:  # make room so the close marker always fits
            try:
                sub.queue.put_nowait(CLOSE)
                return
            except asyncio.QueueFull:
                sub.queue.get_nowait()

    def _dispatch(self, events: list[dict]) -> None:
        with self._lock:
            snapshot = {uid: list(subs) for uid, subs in self._subs.items()}
        for item in events:
            for uid in item.get("users", ()):
                for sub in snapshot.get(uid, ()):
                    if sub.closed:
                        continue
                    if item["type"] == "session_ended":
                        only, keep = item.get("only_token"), item.get("keep_token")
                        if (only and sub.token_hash != only) or (keep and sub.token_hash == keep):
                            continue
                        self._close(sub)
                        continue
                    try:
                        sub.queue.put_nowait({"type": item["type"], "id": str(item["id"])})
                    except asyncio.QueueFull:
                        self._close(sub)  # slow client: it reconnects and refetches


def queue_event(session: Session, type_: str, id_, users) -> None:
    """Remember an event; it is published only if the transaction commits."""
    users = sorted({int(u) for u in users if u is not None})
    if users:
        session.info.setdefault("events", []).append({"type": type_, "id": id_, "users": users})


def end_sessions(session: Session, user_id: int, *, only_token=None, keep_token=None) -> None:
    """Close live streams of a user after commit (logout, password change...)."""
    session.info.setdefault("events", []).append(
        {
            "type": "session_ended",
            "id": user_id,
            "users": [user_id],
            "only_token": only_token,
            "keep_token": keep_token,
        }
    )


@sa_event.listens_for(Session, "after_commit")
def _publish_after_commit(session):
    events = session.info.pop("events", None)
    bus = session.info.get("bus")
    if events and bus is not None:
        bus.publish(events)


@sa_event.listens_for(Session, "after_rollback")
def _drop_after_rollback(session):
    session.info.pop("events", None)


class TicketStore:
    """Single-use, short-lived stream tickets.

    ``EventSource`` cannot send an ``Authorization`` header and the session
    token must not travel in a URL, so the page exchanges its token for a
    30-second ticket and opens ``/api/events?ticket=…``.
    """

    def __init__(self, lifetime=TICKET_SECONDS):
        self.lifetime = lifetime
        self._items: dict[str, tuple[int, str, float]] = {}
        self._lock = threading.Lock()

    def issue(self, user_id: int, token_hash: str) -> str:
        ticket = secrets.token_urlsafe(32)
        now = time.monotonic()
        with self._lock:
            for key in [k for k, v in self._items.items() if v[2] < now]:
                del self._items[key]
            self._items[hashlib.sha256(ticket.encode()).hexdigest()] = (
                user_id,
                token_hash,
                now + self.lifetime,
            )
        return ticket

    def redeem(self, ticket: str) -> tuple[int, str] | None:
        key = hashlib.sha256(ticket.encode()).hexdigest()
        with self._lock:
            item = self._items.pop(key, None)
        if item is None or item[2] < time.monotonic():
            return None
        return item[0], item[1]
