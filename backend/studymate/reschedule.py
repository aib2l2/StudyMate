"""Moving a 1:1 lesson to another slot by agreement of both participants.

The booking keeps its id, so notes, chat, quizzes and the price snapshot stay
attached. Reminders are keyed by slot: the old one is skipped, a new one is
scheduled.
"""

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from .models import Booking, Notification, RescheduleRequest, Slot, User
from .service import (
    ACTIVE,
    available_slots,
    fail,
    find_conflict,
    get,
    notify,
    now,
    schedule_reminders,
)

ANSWER_SECONDS = 24 * 3600


def pending_request(session: Session, booking_id: str) -> RescheduleRequest | None:
    req = session.scalar(
        select(RescheduleRequest).where(
            RescheduleRequest.booking_id == booking_id, RescheduleRequest.status == "pending"
        )
    )
    if req is None or req.expires_at <= now():
        return None  # an expired proposal is simply not offered any more
    return req


def _movable(session: Session, user: User, booking: Booking) -> Slot:
    if user.id not in (booking.student_id, booking.mentor_id):
        fail(403, "Перенести занятие может только его участник")
    slot = get(session, Slot, booking.slot_id)
    if (getattr(slot, "capacity", 1) or 1) > 1:
        fail(409, "Групповое занятие переносить нельзя: у него несколько участников")
    if booking.status not in ACTIVE or slot.starts_at <= now():
        fail(409, "Перенести можно только будущую активную встречу")
    return slot


def _slot_free(session: Session, slot: Slot) -> bool:
    taken = session.scalar(
        select(func.count(Booking.id)).where(
            Booking.slot_id == slot.id, Booking.status.in_((*ACTIVE, "completed"))
        )
    )
    return slot.enabled and taken == 0 and slot.starts_at > now() + 60


def options(session: Session, user: User, booking: Booking) -> list[Slot]:
    current = _movable(session, user, booking)
    return [
        s
        for s in available_slots(session, booking.mentor_id, now(), now() + 30 * 86400)
        if s.id != current.id
        and (getattr(s, "capacity", 1) or 1) == 1
        and not find_conflict(session, [booking.student_id], s, booking.id)
    ][:20]


def propose(session: Session, user: User, booking: Booking, slot_id: int) -> RescheduleRequest:
    current = _movable(session, user, booking)
    target = get(session, Slot, slot_id)
    if target.mentor_id != booking.mentor_id or target.id == current.id:
        fail(422, "Выберите другое свободное время этого же ментора")
    if (getattr(target, "capacity", 1) or 1) > 1 or not _slot_free(session, target):
        fail(409, "Это время уже занято или закрыто")
    if find_conflict(session, [booking.student_id, booking.mentor_id], target, booking.id):
        fail(409, "В это время у одного из участников уже есть занятие")
    stale = session.scalar(
        select(RescheduleRequest).where(
            RescheduleRequest.booking_id == booking.id, RescheduleRequest.status == "pending"
        )
    )
    if stale is not None:
        if stale.expires_at > now():
            fail(409, "Уже есть предложение о переносе. Дождитесь ответа или отмените его")
        stale.status = "expired"
        session.flush()
    req = RescheduleRequest(
        booking_id=booking.id,
        proposed_slot_id=target.id,
        requested_by=user.id,
        status="pending",
        created_at=now(),
        expires_at=min(now() + ANSWER_SECONDS, target.starts_at),
    )
    session.add(req)
    session.flush()
    other = booking.mentor_id if user.id == booking.student_id else booking.student_id
    notify(
        session,
        other,
        booking.id,
        "reschedule_proposed",
        f"{user.name} предлагает перенести встречу. Ответьте на странице занятия.",
        f"reschedule:{req.id}:proposed",
    )
    return req


def _open_request(session: Session, rid: int) -> tuple[RescheduleRequest, Booking]:
    req = get(session, RescheduleRequest, rid)
    booking = get(session, Booking, req.booking_id)
    if req.status == "pending" and req.expires_at <= now():
        req.status = "expired"
        session.flush()
    if req.status != "pending":
        fail(409, "Это предложение уже не действует")
    return req, booking


def accept(session: Session, user: User, rid: int) -> Booking:
    req, booking = _open_request(session, rid)
    if user.id not in (booking.student_id, booking.mentor_id) or user.id == req.requested_by:
        fail(403, "Принять перенос может другой участник встречи")
    _movable(session, user, booking)
    target = get(session, Slot, req.proposed_slot_id)
    # Re-check under the write lock: the slot may have been taken meanwhile.
    if not _slot_free(session, target) or find_conflict(
        session, [booking.student_id, booking.mentor_id], target, booking.id
    ):
        fail(409, "Предложенное время уже занято. Предложите другое")
    booking.slot_id = target.id
    booking.reschedule_count = (booking.reschedule_count or 0) + 1
    if booking.status == "pending":
        booking.expires_at = min(booking.expires_at, target.starts_at)
    req.status = "accepted"
    # Old reminders belong to the old slot; skip them explicitly as well.
    session.execute(
        update(Notification)
        .where(
            Notification.booking_id == booking.id,
            Notification.kind == "reminder",
            Notification.status == "pending",
        )
        .values(status="skipped")
    )
    session.flush()
    if booking.status == "confirmed":
        schedule_reminders(session, booking, target)
    for uid in (booking.student_id, booking.mentor_id):
        notify(
            session,
            uid,
            booking.id,
            "rescheduled",
            "Встреча перенесена на новое время. Заметки и переписка сохранены.",
            f"reschedule:{req.id}:accepted:{uid}",
        )
    return booking


def decline(session: Session, user: User, rid: int) -> None:
    req, booking = _open_request(session, rid)
    if user.id not in (booking.student_id, booking.mentor_id) or user.id == req.requested_by:
        fail(403, "Отклонить перенос может другой участник встречи")
    req.status = "declined"
    notify(
        session,
        req.requested_by,
        booking.id,
        "reschedule_declined",
        "Перенос не подошёл. Встреча остаётся в прежнее время.",
        f"reschedule:{req.id}:declined",
    )


def cancel(session: Session, user: User, rid: int) -> None:
    req, booking = _open_request(session, rid)
    if user.id != req.requested_by:
        fail(403, "Отозвать предложение может только его автор")
    req.status = "cancelled"
    other = booking.mentor_id if user.id == booking.student_id else booking.student_id
    notify(
        session,
        other,
        booking.id,
        "reschedule_cancelled",
        "Предложение о переносе отозвано.",
        f"reschedule:{req.id}:cancelled",
    )
