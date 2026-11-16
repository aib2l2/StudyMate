"""Lesson chat: threads, access rules, unread counters and notifications."""

from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from .events import queue_event
from .models import Booking, ChatMessage, ChatRead, Slot, User
from .service import fail, get, notify, now

WRITE_AFTER_COMPLETION = 7 * 86400
PAGE = 100


def thread_of(session: Session, booking: Booking) -> str:
    """Thread key is derived on the server, never taken from the client."""
    slot = session.get(Slot, booking.slot_id)
    if slot is not None and (getattr(slot, "capacity", 1) or 1) > 1:
        return f"slot:{slot.id}"
    return f"booking:{booking.id}"


def thread_bookings(session: Session, thread_key: str) -> list[Booking]:
    kind, _, key = thread_key.partition(":")
    if kind == "booking":
        booking = session.get(Booking, key)
        return [booking] if booking else []
    return list(session.scalars(select(Booking).where(Booking.slot_id == int(key))))


def _can_write(booking: Booking) -> bool:
    if booking.status in ("pending", "confirmed"):
        return True
    return (
        booking.status == "completed"
        and now() - (booking.completed_at or 0) <= WRITE_AFTER_COMPLETION
    )


def access(session: Session, user: User, booking: Booking) -> tuple[str, str]:
    """Return (thread_key, mode) where mode is 'write' or 'read'.

    The team role gives no access: chats are private like lesson notes.
    """
    key = thread_of(session, booking)
    rows = thread_bookings(session, key)
    if key.startswith("slot:"):
        # Group room: the mentor and students who hold (or held) a seat.
        mine = [
            b
            for b in rows
            if b.student_id == user.id
            and b.status in ("pending", "confirmed", "completed", "cancelled")
        ]
        if user.id == booking.mentor_id:
            mode = "write" if any(_can_write(b) for b in rows) else "read"
            return key, mode
        if not mine:
            fail(403, "Переписка доступна только участникам занятия")
        return key, "write" if any(_can_write(b) for b in mine) else "read"
    if user.id not in (booking.student_id, booking.mentor_id):
        fail(403, "Переписка доступна только участникам занятия")
    return key, "write" if _can_write(booking) else "read"


def participants(session: Session, thread_key: str) -> set[int]:
    rows = thread_bookings(session, thread_key)
    people = {b.mentor_id for b in rows}
    people |= {
        b.student_id
        for b in rows
        if thread_key.startswith("booking:") or b.status in ("pending", "confirmed", "completed")
    }
    return people


def last_read(session: Session, thread_key: str, user_id: int) -> int:
    row = session.get(ChatRead, (thread_key, user_id))
    return row.last_read_id if row else 0


def unread_count(session: Session, thread_key: str, user_id: int) -> int:
    return session.scalar(
        select(func.count(ChatMessage.id)).where(
            ChatMessage.thread_key == thread_key,
            ChatMessage.id > last_read(session, thread_key, user_id),
            ChatMessage.sender_id != user_id,
        )
    )


def message_json(session: Session, m: ChatMessage) -> dict:
    return {
        "id": m.id,
        "sender_id": m.sender_id,
        "sender_name": get(session, User, m.sender_id).name,
        "body": m.body,
        "created_at": m.created_at,
        "client_id": m.client_id,
    }


def list_messages(session: Session, user: User, booking: Booking, after_id: int = 0) -> dict:
    key, mode = access(session, user, booking)
    rows = list(
        session.scalars(
            select(ChatMessage)
            .where(ChatMessage.thread_key == key, ChatMessage.id > after_id)
            .order_by(ChatMessage.id)
            .limit(PAGE)
        )
    )
    others = participants(session, key) - {user.id}
    return {
        "thread": key,
        "can_write": mode == "write",
        "messages": [message_json(session, m) for m in rows],
        "my_last_read_id": last_read(session, key, user.id),
        "others_last_read_id": max((last_read(session, key, uid) for uid in others), default=0),
    }


def post_message(session: Session, user: User, booking: Booking, body: str, client_id: str) -> dict:
    key, mode = access(session, user, booking)
    existing = session.scalar(
        select(ChatMessage).where(
            ChatMessage.sender_id == user.id, ChatMessage.client_id == client_id
        )
    )
    if existing:  # retried send: same message, no duplicate
        if existing.thread_key != key:
            fail(409, "Этот идентификатор сообщения уже использован")
        return message_json(session, existing)
    if mode != "write":
        fail(409, "Переписка по этому занятию закрыта, её можно только читать")
    text = body.strip()
    if not text:
        fail(422, "Напишите сообщение")
    message = ChatMessage(
        thread_key=key, sender_id=user.id, body=text, created_at=now(), client_id=client_id
    )
    session.add(message)
    session.flush()
    _mark_read(session, key, user.id, message.id)
    people = participants(session, key)
    for uid in people - {user.id}:
        first_unread = session.scalar(
            select(func.min(ChatMessage.id)).where(
                ChatMessage.thread_key == key,
                ChatMessage.id > last_read(session, key, uid),
                ChatMessage.sender_id != uid,
            )
        )
        # One notification per batch of unread messages, not one per message.
        notify(
            session,
            uid,
            _booking_for(session, key, uid, booking),
            "message",
            f"Новое сообщение от {user.name}",
            f"thread:{key}:{uid}:{first_unread}",
        )
    queue_event(session, "thread", key, people)
    return message_json(session, message)


def _booking_for(session: Session, key: str, uid: int, fallback: Booking) -> str:
    """Link a notification to the recipient's own booking in a group room."""
    for b in thread_bookings(session, key):
        if b.student_id == uid:
            return b.id
    return fallback.id


def _mark_read(session: Session, key: str, user_id: int, message_id: int) -> None:
    session.execute(
        insert(ChatRead)
        .values(thread_key=key, user_id=user_id, last_read_id=message_id)
        .on_conflict_do_update(
            index_elements=["thread_key", "user_id"],
            set_={"last_read_id": func.max(ChatRead.last_read_id, message_id)},
        )
    )


def mark_read(session: Session, user: User, booking: Booking, message_id: int) -> None:
    key, _ = access(session, user, booking)
    latest = (
        session.scalar(select(func.max(ChatMessage.id)).where(ChatMessage.thread_key == key)) or 0
    )
    _mark_read(session, key, user.id, min(message_id, latest))
    queue_event(session, "thread", key, participants(session, key))
