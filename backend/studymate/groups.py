"""Group lessons: one slot, up to five students, one booking row per student.

Keeping a booking per student means notes, quizzes, reviews, XP, the payment
simulation and data export work per participant without changes. What is
shared (place, materials, the mentor's completion mark) lives in
``slot_meetings``. Capacity is enforced twice: by the service (clear 409) and
by SQLite triggers (last line of defence, like the old unique index).
"""

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .events import queue_event
from .models import Booking, Mentor, Slot, SlotMeeting, Subject, Topic, User
from .service import (
    ACTIVE,
    STATUS_LABELS,
    award,
    fail,
    find_conflict,
    get,
    notify,
    now,
    schedule_reminders,
    seats_taken,
)

MAX_CAPACITY = 5
CANCEL_BEFORE = 2 * 3600  # under-filled groups are cancelled two hours before start


def is_group(slot: Slot) -> bool:
    return (slot.capacity or 1) > 1


def meeting_of(session: Session, slot: Slot) -> SlotMeeting:
    meeting = session.get(SlotMeeting, slot.id)
    if meeting is None:
        fail(409, "У группового занятия нет данных встречи")
    return meeting


def shared_meeting(session: Session, slot: Slot, booking: Booking) -> dict:
    if is_group(slot) and (meeting := session.get(SlotMeeting, slot.id)):
        return {
            "meeting_url": meeting.meeting_url,
            "meeting_place": meeting.meeting_place,
            "materials": meeting.materials,
            "mentor_completed_at": meeting.mentor_completed_at,
        }
    return {
        "meeting_url": booking.meeting_url,
        "meeting_place": booking.meeting_place,
        "materials": booking.materials,
        "mentor_completed_at": booking.mentor_completed_at,
    }


def participants(session: Session, slot: Slot, statuses=(*ACTIVE, "completed")) -> list[Booking]:
    return list(
        session.scalars(
            select(Booking)
            .where(Booking.slot_id == slot.id, Booking.status.in_(statuses))
            .order_by(Booking.created_at)
        )
    )


def group_json(session: Session, slot: Slot) -> dict | None:
    if not is_group(slot):
        return None
    rows = participants(session, slot)
    return {
        "capacity": slot.capacity,
        "taken": sum(b.status in ACTIVE for b in rows) or sum(1 for _ in rows),
        "participants": [get(session, User, b.student_id).name for b in rows],
    }


def slot_matches(session, slot: Slot, mentor: Mentor, topic_id, budget: int, format_: str) -> bool:
    """Does this free slot fit the search? Groups have their own topic, price and format."""
    if not is_group(slot):
        return mentor.price <= budget and format_ in mentor.formats
    meeting = session.get(SlotMeeting, slot.id)
    return (
        meeting is not None
        and meeting.cancelled_at is None
        and (not topic_id or slot.topic_id == topic_id)
        and (slot.price or 0) <= budget
        and meeting.format == format_
    )


# ------------------------------------------------------------------ mentor


def validate_group(session: Session, mentor: Mentor, data) -> None:
    if not 2 <= data.capacity <= MAX_CAPACITY:
        fail(422, "В группе от 2 до 5 мест")
    if not 1 <= data.min_participants <= data.capacity:
        fail(422, "Минимум участников — от 1 до числа мест")
    topic = get(session, Topic, data.topic_id)
    if topic.id not in mentor.topic_ids or not get(session, Subject, topic.subject_id).active:
        fail(422, "Выберите одну из своих активных тем")
    if data.format == "online" and not (data.meeting_url or "").strip():
        fail(422, "Для онлайн-группы укажите ссылку на встречу")
    if data.format == "campus" and not (data.meeting_place or "").strip():
        fail(422, "Для группы на кампусе укажите аудиторию")


def attach_meeting(session: Session, slot: Slot, data) -> None:
    slot.capacity = data.capacity
    slot.topic_id = data.topic_id
    slot.price = data.price
    slot.min_participants = data.min_participants
    existing = session.get(SlotMeeting, slot.id)
    meeting = existing or SlotMeeting(slot_id=slot.id)
    meeting.format = data.format
    meeting.meeting_url = (data.meeting_url or "").strip() if data.format == "online" else ""
    meeting.meeting_place = (data.meeting_place or "").strip() if data.format == "campus" else ""
    meeting.cancelled_at = None
    if existing is None:
        session.add(meeting)
    session.flush()


def update_meeting(session: Session, user: User, slot: Slot, data) -> SlotMeeting:
    if slot.mentor_id != user.id:
        fail(403, "Это занятие другого ментора")
    meeting = meeting_of(session, slot)
    for name in ("meeting_url", "meeting_place", "materials"):
        value = getattr(data, name)
        if value is None:
            continue
        required = "meeting_url" if meeting.format == "online" else "meeting_place"
        if name == required and not value.strip():
            fail(422, "Групповому занятию нужно место встречи")
        setattr(meeting, name, value.strip())
    session.flush()
    _announce(session, slot, "group_updated", "Ментор обновил данные группового занятия.")
    return meeting


def cancel_group(session: Session, slot: Slot, reason: str, key: str) -> int:
    """Cancel every active seat (idempotent through slot_meetings.cancelled_at)."""
    meeting = meeting_of(session, slot)
    if meeting.cancelled_at is not None:
        return 0
    meeting.cancelled_at = now()
    slot.enabled = False
    count = 0
    for booking in participants(session, slot, ACTIVE):
        booking.status = "cancelled"
        count += 1
        notify(
            session,
            booking.student_id,
            booking.id,
            "group_cancelled",
            reason,
            f"{key}:{booking.student_id}",
        )
    notify(session, slot.mentor_id, None, "group_cancelled", reason, f"{key}:{slot.mentor_id}")
    session.flush()
    return count


def complete_group(session: Session, user: User, slot: Slot, settings) -> SlotMeeting:
    if slot.mentor_id != user.id:
        fail(403, "Завершение отмечает ментор занятия")
    meeting = meeting_of(session, slot)
    if meeting.cancelled_at is not None or not participants(session, slot, ("confirmed",)):
        fail(409, "В группе нет подтверждённых участников")
    if now() < slot.ends_at and settings.mode != "demo":
        fail(409, "Занятие ещё не закончилось")
    if meeting.mentor_completed_at is None:
        meeting.mentor_completed_at = now()
        for booking in participants(session, slot, ("confirmed",)):
            notify(
                session,
                booking.student_id,
                booking.id,
                "completion_requested",
                "Ментор завершил групповое занятие. Подтвердите, что оно состоялось.",
                f"{booking.id}:completion_requested",
            )
    session.flush()
    return meeting


def _announce(session: Session, slot: Slot, kind: str, body: str) -> None:
    for booking in participants(session, slot, ACTIVE):
        notify(
            session,
            booking.student_id,
            booking.id,
            kind,
            body,
            f"{kind}:{slot.id}:{booking.student_id}:{now()}",
        )
    queue_event(session, "slot", slot.id, [slot.mentor_id])


# ----------------------------------------------------------------- student


def book_seat(
    session: Session, user: User, data: dict, slot: Slot, mentor: Mentor, person: User
) -> Booking:
    meeting = meeting_of(session, slot)
    topic = get(session, Topic, slot.topic_id)
    if not mentor.active or mentor.suspended or not slot.enabled or meeting.cancelled_at:
        fail(409, "Ментор или занятие временно недоступны")
    if not get(session, Subject, topic.subject_id).active:
        fail(409, "Ментор или предмет временно недоступен")
    if data["topic_id"] != slot.topic_id:
        fail(422, f"Это групповое занятие по теме «{topic.name}»")
    if data["language"] not in person.languages or person.campus != user.campus:
        fail(422, "Ментор не подходит под условия заявки")
    if data["format"] != meeting.format:
        fail(422, "Формат группового занятия другой")
    if slot.price > data["budget"]:
        fail(409, f"Место в группе стоит {slot.price} ₸, выше вашего бюджета")
    if (
        slot.ends_at > data["deadline"]
        or slot.starts_at < data.get("earliest", 0)
        or slot.starts_at <= now() + 60
    ):
        fail(409, "Проверьте дедлайн и доступность времени")
    if meeting.mentor_completed_at:
        fail(409, "Это занятие уже прошло")
    if session.scalar(
        select(Booking.id).where(
            Booking.slot_id == slot.id, Booking.student_id == user.id, Booking.status.in_(ACTIVE)
        )
    ):
        fail(409, "Вы уже записаны на это занятие")
    if seats_taken(session, [slot.id])[slot.id] >= slot.capacity:
        fail(409, "Мест в группе не осталось")
    if find_conflict(session, [user.id], slot, ignore_slot_id=slot.id):
        fail(409, "В это время у вас уже есть занятие")
    booking = Booking(
        id=str(uuid.uuid4()),
        student_id=user.id,
        mentor_id=mentor.user_id,
        slot_id=slot.id,
        topic_id=topic.id,
        price=slot.price,
        # The place is known up front, so a seat is confirmed immediately.
        status="confirmed",
        description=data["description"],
        deadline=data["deadline"],
        language=data["language"],
        format=meeting.format,
        created_at=now(),
        confirmed_at=now(),
        expires_at=slot.starts_at,
        request_key=data["request_key"],
    )
    session.add(booking)
    try:
        session.flush()
    except IntegrityError as error:  # the capacity trigger or the one-seat index
        fail(409, "Мест в группе не осталось" if "slot_full" in str(error) else "Вы уже записаны")
    schedule_reminders(session, booking, slot)
    notify(
        session,
        mentor.user_id,
        booking.id,
        "group_joined",
        f"{user.name} записался на групповое занятие «{topic.name}».",
        f"{booking.id}:joined",
    )
    notify(
        session,
        user.id,
        booking.id,
        "created",
        "Вы записаны на групповое занятие.",
        f"{booking.id}:created",
    )
    queue_event(session, "slot", slot.id, [mentor.user_id])
    return booking


def change_seat(
    session: Session, user: User, booking: Booking, slot: Slot, action: str, settings
) -> None:
    from .service import release_slots

    if action == "request_completion":
        complete_group(session, user, slot, settings)
        return
    if action in ("confirm", "reject"):
        fail(409, "Место в группе подтверждается сразу при записи")
    if action == "cancel":
        if booking.status not in ACTIVE:
            fail(409, "Эту запись уже нельзя отменить")
        booking.status = "cancelled"
        session.flush()
        release_slots(session, [slot.id])
        for uid in (booking.student_id, booking.mentor_id):
            notify(
                session,
                uid,
                booking.id,
                "cancel",
                "Участник отменил запись в группу.",
                f"{booking.id}:cancelled:{uid}",
            )
        return
    if action == "complete":
        if user.id != booking.student_id:
            fail(403, "Студент подтверждает, что занятие состоялось")
        if booking.status == "completed":
            return
        meeting = meeting_of(session, slot)
        if meeting.mentor_completed_at is None:
            fail(409, "Дождитесь отметки ментора о завершении встречи")
        if booking.status != "confirmed":
            fail(409, "Завершить можно только подтверждённое занятие")
        booking.status = "completed"
        booking.completed_at = now()
        topic = get(session, Topic, booking.topic_id)
        award(session, booking.student_id, topic.subject_id, f"session:{booking.id}", 30)
        # The mentor earns XP once per group, not once per student.
        award(session, booking.mentor_id, topic.subject_id, f"group:{slot.id}", 30)
        notify(
            session,
            booking.student_id,
            booking.id,
            "complete",
            STATUS_LABELS["completed"] + ". Пройдите тест после занятия и оставьте отзыв.",
            f"{booking.id}:completed:{booking.student_id}",
        )
        session.flush()
        return
    fail(422, "Неизвестное действие")


def cancel_underfilled(session: Session) -> int:
    """Worker step: cancel groups below min_participants two hours before start."""
    cancelled = 0
    for slot in session.scalars(
        select(Slot).where(
            Slot.capacity > 1,
            Slot.enabled.is_(True),
            Slot.starts_at > now(),
            Slot.starts_at <= now() + CANCEL_BEFORE,
        )
    ):
        meeting = session.get(SlotMeeting, slot.id)
        if meeting is None or meeting.cancelled_at is not None:
            continue
        active = len(participants(session, slot, ACTIVE))
        if active < slot.min_participants:
            cancel_group(
                session,
                slot,
                "Групповое занятие отменено: не набралось минимальное число участников.",
                f"group-underfilled:{slot.id}",
            )
            cancelled += 1
    return cancelled
