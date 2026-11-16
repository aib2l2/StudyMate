import time
import uuid
from statistics import median

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from .config import Settings
from .db import is_readonly
from .events import queue_event
from .models import (
    Booking,
    Favorite,
    Mentor,
    Notification,
    PaymentSimulation,
    ProgressEvent,
    QuizAttempt,
    Review,
    Slot,
    Subject,
    Topic,
    User,
)

ACTIVE = ("pending", "confirmed")
STATUS_LABELS = {
    "pending": "Ожидает подтверждения",
    "confirmed": "Запись подтверждена",
    "completed": "Занятие завершено",
    "cancelled": "Запись отменена",
    "rejected": "Ментор отклонил заявку",
    "expired": "Время ответа истекло",
}


def now():
    return int(time.time())


def fail(code, message):
    raise HTTPException(code, message)


def get(session, model, key):
    item = session.get(model, key)
    if item is None:
        fail(404, "Запись не найдена")
    return item


def notify(session, user_id, booking_id, kind, body, key, due=None, link=None, slot_id=None):
    session.execute(
        insert(Notification)
        .values(
            user_id=user_id,
            booking_id=booking_id,
            kind=kind,
            body=body,
            dedupe_key=key,
            due_at=due if due is not None else now(),
            status="pending",
            attempts=0,
            read=False,
            link=link,
            slot_id=slot_id,
        )
        .on_conflict_do_nothing(index_elements=["dedupe_key"])
    )
    # Live hint for the browser; delivered only if this transaction commits.
    if due is None or due <= now():
        queue_event(session, "notification", key, [user_id])
    if booking_id:
        queue_event(session, "booking", booking_id, [user_id])


def award(session, user_id, subject_id, source, points):
    session.execute(
        insert(ProgressEvent)
        .values(
            user_id=user_id, subject_id=subject_id, source=source, points=points, created_at=now()
        )
        .on_conflict_do_nothing(index_elements=["user_id", "source"])
    )


def has_overdue_pending(session) -> bool:
    return (
        session.scalar(
            select(Booking.id)
            .where(Booking.status == "pending", Booking.expires_at <= now())
            .limit(1)
        )
        is not None
    )


def expire_pending(session):
    """Mark overdue pending bookings as expired.

    Read-only sessions skip this: the read dependency expires overdue bookings
    in a short write transaction before the snapshot is opened.
    """
    if is_readonly(session):
        return
    released = []
    for booking in session.scalars(
        select(Booking).where(Booking.status == "pending", Booking.expires_at <= now())
    ):
        booking.status = "expired"
        released.append(booking.slot_id)
        for uid in (booking.student_id, booking.mentor_id):
            notify(
                session,
                uid,
                booking.id,
                "expired",
                "Время ответа на заявку истекло. Выберите другой слот.",
                f"{booking.id}:expired:{uid}",
            )
    session.flush()
    release_slots(session, released)


def release_slots(session, slot_ids):
    """A seat became free again: tell matching waitlist requests."""
    if not slot_ids:
        return
    from .matching import match_waitlist

    for slot_id in dict.fromkeys(slot_ids):
        match_waitlist(session, get(session, Slot, slot_id))


def profile(session, user):
    mentor = session.get(Mentor, user.id)
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "campus": user.campus,
        "course": user.course,
        "languages": user.languages,
        "interests": user.interests,
        "registered": user.registered,
        "is_admin": user.is_admin,
        "mentor": None
        if mentor is None
        else {
            "bio": mentor.bio,
            "price": mentor.price,
            "topic_ids": mentor.topic_ids,
            "formats": mentor.formats,
            "verified": mentor.verified,
            "active": mentor.active,
            "suspended": mentor.suspended,
        },
    }


def catalog(session):
    return [
        {
            "id": s.id,
            "slug": s.slug,
            "name": s.name,
            "active": s.active,
            "topics": [
                {"id": t.id, "name": t.name, "code": t.code}
                for t in session.scalars(
                    select(Topic).where(Topic.subject_id == s.id).order_by(Topic.id)
                )
            ],
        }
        for s in session.scalars(select(Subject).order_by(Subject.id))
    ]


RATING_PRIOR_WEIGHT = 3  # C in the Bayesian average


def rating(session, mentor_id):
    """Plain average for display plus a Bayesian score for ranking.

    score = (C·m + Σ ratings) / (C + n), m = mean of all reviews. A single 5★
    review no longer outranks twenty reviews averaging 4.8.
    """
    average, count = session.execute(
        select(func.avg(Review.rating), func.count(Review.id)).where(Review.mentor_id == mentor_id)
    ).one()
    overall = session.scalar(select(func.avg(Review.rating)))
    score = None
    if overall is not None:
        total = (average or 0) * count
        score = round((RATING_PRIOR_WEIGHT * overall + total) / (RATING_PRIOR_WEIGHT + count), 3)
    return {
        "rating": round(average, 1) if average is not None else None,
        "review_count": count,
        "rating_score": score,
    }


def seats_taken(session, slot_ids) -> dict[int, int]:
    """Active bookings per slot; a completed lesson counts as fully used."""
    if not slot_ids:
        return {}
    taken = dict(
        session.execute(
            select(Booking.slot_id, func.count(Booking.id))
            .where(Booking.slot_id.in_(slot_ids), Booking.status.in_(ACTIVE))
            .group_by(Booking.slot_id)
        ).all()
    )
    done = set(
        session.scalars(
            select(Booking.slot_id).where(
                Booking.slot_id.in_(slot_ids), Booking.status == "completed"
            )
        )
    )
    return {sid: (10**6 if sid in done else taken.get(sid, 0)) for sid in slot_ids}


def available_slots(session, mentor_id, earliest, deadline):
    candidates = list(
        session.scalars(
            select(Slot)
            .where(
                Slot.mentor_id == mentor_id,
                Slot.enabled.is_(True),
                Slot.starts_at >= max(earliest, now() + 60),
                Slot.ends_at <= deadline,
            )
            .order_by(Slot.starts_at)
        )
    )
    taken = seats_taken(session, [c.id for c in candidates])
    candidates = [c for c in candidates if taken[c.id] < (c.capacity or 1)]
    for c in candidates:
        c.taken = taken[c.id]  # transient attribute for slot_json
    busy = list(
        session.scalars(
            select(Slot)
            .join(Booking, Booking.slot_id == Slot.id)
            .where(
                Booking.status.in_(ACTIVE),
                (Booking.mentor_id == mentor_id) | (Booking.student_id == mentor_id),
            )
        )
    )
    return [
        slot
        for slot in candidates
        if not any(
            b.id != slot.id and b.starts_at < slot.ends_at and b.ends_at > slot.starts_at
            for b in busy
        )
    ]


def slot_json(slot, session=None):
    data = {
        "id": slot.id,
        "mentor_id": slot.mentor_id,
        "starts_at": slot.starts_at,
        "ends_at": slot.ends_at,
        "enabled": slot.enabled,
        "series_id": slot.series_id,
        "capacity": slot.capacity or 1,
    }
    if (slot.capacity or 1) > 1:
        from .models import SlotMeeting

        data["price"] = slot.price
        data["topic_id"] = slot.topic_id
        data["min_participants"] = slot.min_participants
        # Fresh count when a session is at hand; the transient value may be stale.
        taken = (
            seats_taken(session, [slot.id])[slot.id]
            if session is not None
            else getattr(slot, "taken", None)
        )
        if taken is not None:
            data["taken"] = min(taken, slot.capacity)
        if session is not None:
            meeting = session.get(SlotMeeting, slot.id)
            if meeting:
                data["format"] = meeting.format
    return data


def mentor_card(session, mentor, slots, reasons, favorite=False):
    user = get(session, User, mentor.user_id)
    return {
        "id": user.id,
        "name": user.name,
        "course": user.course,
        "campus": user.campus,
        "languages": user.languages,
        "bio": mentor.bio,
        "price": mentor.price,
        "topic_ids": mentor.topic_ids,
        "formats": mentor.formats,
        "verified": mentor.verified,
        "active": mentor.active,
        "suspended": mentor.suspended,
        "topics": [
            {"id": t.id, "name": t.name, "subject_id": t.subject_id}
            for t in (get(session, Topic, tid) for tid in mentor.topic_ids)
            if get(session, Subject, t.subject_id).active
        ],
        **rating(session, user.id),
        "slots": [slot_json(s, session) for s in slots],
        "reasons": reasons,
        "is_favorite": favorite,
    }


def find_matches(
    session,
    user,
    topic_id=None,
    budget=100000,
    earliest=None,
    deadline=None,
    language="ru",
    format="online",
    q=None,
    sort="soonest",
    favorites_only=False,
):
    from .search import matching_ids

    expire_pending(session)
    favorites = favorite_ids(session, user.id) if user is not None else set()
    text_ids = matching_ids(session, q)
    if user is None:
        from types import SimpleNamespace

        user = SimpleNamespace(id=-1, campus="Astana IT University")
    earliest, deadline = earliest or now(), deadline or now() + 7 * 86400
    if deadline <= max(earliest, now()):
        fail(422, "Дедлайн должен быть позже удобного времени")
    if topic_id:
        topic = get(session, Topic, topic_id)
        if not get(session, Subject, topic.subject_id).active:
            return []
    result = []
    for mentor in session.scalars(
        select(Mentor).where(
            Mentor.active.is_(True),
            Mentor.suspended.is_(False),
            Mentor.user_id != user.id,
        )
    ):
        person = get(session, User, mentor.user_id)
        if person.campus != user.campus or language not in person.languages:
            continue
        if topic_id and topic_id not in mentor.topic_ids:
            continue
        if text_ids is not None and mentor.user_id not in text_ids:
            continue
        if favorites_only and mentor.user_id not in favorites:
            continue
        if not any(
            get(session, Subject, get(session, Topic, tid).subject_id).active
            for tid in mentor.topic_ids
        ):
            continue
        from .groups import slot_matches

        slots = [
            x
            for x in available_slots(session, mentor.user_id, earliest, deadline)
            if slot_matches(session, x, mentor, topic_id, budget, format)
        ]
        if not slots:
            continue
        reasons = [
            "Знаком с выбранной темой" if topic_id else "Ментор вашего кампуса",
            "Есть время до дедлайна",
            "Подходит по бюджету",
        ]
        if mentor.verified:
            reasons.append("Проверен командой")
        if mentor.user_id in favorites:
            reasons.append("В вашем избранном")
        result.append(
            mentor_card(session, mentor, slots[:12], reasons, mentor.user_id in favorites)
        )
    soonest = lambda m: m["slots"][0]["starts_at"]  # noqa: E731
    keys = {
        "soonest": lambda m: (soonest(m), not m["verified"], -(m["rating_score"] or 0), m["price"]),
        "price": lambda m: (m["price"], soonest(m)),
        "rating": lambda m: (-(m["rating_score"] or 0), -m["review_count"], soonest(m)),
    }
    return sorted(result, key=keys.get(sort, keys["soonest"]))


def favorite_ids(session, user_id) -> set[int]:
    return set(session.scalars(select(Favorite.mentor_id).where(Favorite.user_id == user_id)))


def booking_json(session, booking, viewer_id=None):
    slot = get(session, Slot, booking.slot_id)
    topic = get(session, Topic, booking.topic_id)
    review = session.scalar(select(Review).where(Review.booking_id == booking.id))
    attempts = list(
        session.scalars(select(QuizAttempt).where(QuizAttempt.booking_id == booking.id))
    )
    receipt = session.get(PaymentSimulation, booking.id)
    from .groups import group_json, shared_meeting

    shared = shared_meeting(session, slot, booking)
    unread = 0
    if viewer_id is not None:
        from .chat import thread_of, unread_count

        unread = unread_count(session, thread_of(session, booking), viewer_id)
    return {
        "id": booking.id,
        "student_id": booking.student_id,
        "student_name": get(session, User, booking.student_id).name,
        "mentor_id": booking.mentor_id,
        "mentor_name": get(session, User, booking.mentor_id).name,
        "topic_id": topic.id,
        "topic": topic.name,
        "subject_id": topic.subject_id,
        "slot": slot_json(slot, session),
        "price": booking.price,
        "status": booking.status,
        "status_label": STATUS_LABELS[booking.status],
        "description": booking.description,
        "deadline": booking.deadline,
        "format": booking.format,
        "language": booking.language,
        "created_at": booking.created_at,
        "expires_at": booking.expires_at,
        "meeting_url": shared["meeting_url"],
        "meeting_place": shared["meeting_place"],
        "materials": shared["materials"],
        "mentor_completed_at": shared["mentor_completed_at"],
        "group": group_json(session, slot),
        "reschedule": pending_reschedule_json(session, booking),
        "payment": "simulation_only",
        "unread_messages": unread,
        "receipt": None
        if receipt is None
        else {
            "id": receipt.receipt_id,
            "amount": receipt.amount,
            "commission": receipt.commission,
            "mentor_amount": receipt.amount - receipt.commission,
        },
        "review": None if review is None else {"rating": review.rating, "comment": review.comment},
        "quizzes": {
            a.stage: {"id": a.id, "score": a.score, "total": len(a.question_ids)} for a in attempts
        },
    }


def pending_reschedule_json(session, booking):
    from .reschedule import pending_request

    req = pending_request(session, booking.id)
    if req is None:
        return None
    return {
        "id": req.id,
        "proposed_slot": slot_json(get(session, Slot, req.proposed_slot_id)),
        "requested_by": req.requested_by,
        "expires_at": req.expires_at,
    }


def list_bookings(session, user, all_records=False):
    expire_pending(session)
    query = select(Booking).order_by(Booking.created_at.desc())
    if not (all_records and user.is_admin):
        query = query.where((Booking.student_id == user.id) | (Booking.mentor_id == user.id))
    # Unread counters only for one's own lessons: the team must not learn about private chats.
    return [
        booking_json(session, b, user.id if user.id in (b.student_id, b.mentor_id) else None)
        for b in session.scalars(query)
    ]


def find_conflict(session, people, slot, exclude_booking_id=None, ignore_slot_id=None):
    """An active booking of any of `people` overlapping `slot`, or None.

    Shared by booking and rescheduling so both apply exactly the same rule.
    """
    query = (
        select(Booking)
        .join(Slot, Booking.slot_id == Slot.id)
        .where(
            Booking.status.in_(ACTIVE),
            Slot.starts_at < slot.ends_at,
            Slot.ends_at > slot.starts_at,
            Booking.mentor_id.in_(people) | Booking.student_id.in_(people),
        )
    )
    if exclude_booking_id:
        query = query.where(Booking.id != exclude_booking_id)
    if ignore_slot_id:  # other seats of the same group lesson are not a conflict
        query = query.where(Booking.slot_id != ignore_slot_id)
    return session.scalars(query).first()


def schedule_reminders(session, booking, slot):
    """Reminder 15 minutes before; keyed by slot so a moved lesson gets a fresh one."""
    for uid in (booking.student_id, booking.mentor_id):
        notify(
            session,
            uid,
            booking.id,
            "reminder",
            "Скоро занятие StudyMate. Ссылка или место встречи находятся на странице занятия.",
            f"{booking.id}:reminder:{slot.id}:{uid}",
            max(now(), slot.starts_at - 900),
            slot_id=slot.id,
        )


def create_booking(session: Session, user: User, data: dict, settings: Settings):
    expire_pending(session)
    existing = session.scalar(
        select(Booking).where(
            Booking.student_id == user.id, Booking.request_key == data["request_key"]
        )
    )
    if existing:
        if (existing.slot_id, existing.topic_id) != (data["slot_id"], data["topic_id"]):
            fail(409, "Этот ключ запроса уже использован для другой записи")
        return booking_json(session, existing, user.id)
    if not user.registered:
        fail(422, "Сначала заполните профиль")
    slot = get(session, Slot, data["slot_id"])
    mentor = get(session, Mentor, slot.mentor_id)
    person = get(session, User, mentor.user_id)
    topic = get(session, Topic, data["topic_id"])
    if mentor.user_id == user.id:
        fail(422, "Выберите другого ментора")
    if (slot.capacity or 1) > 1:
        from .groups import book_seat

        return booking_json(session, book_seat(session, user, data, slot, mentor, person), user.id)
    if (
        not mentor.active
        or mentor.suspended
        or not slot.enabled
        or not get(session, Subject, topic.subject_id).active
    ):
        fail(409, "Ментор или предмет временно недоступен")
    if (
        topic.id not in mentor.topic_ids
        or data["language"] not in person.languages
        or data["format"] not in mentor.formats
        or person.campus != user.campus
    ):
        fail(422, "Ментор не подходит под условия заявки")
    if mentor.price > data["budget"]:
        fail(
            409,
            f"Текущая цена ментора — {mentor.price} ₸, выше вашего бюджета. Обновите условия поиска",
        )
    if (
        slot.ends_at > data["deadline"]
        or slot.starts_at < data.get("earliest", 0)
        or slot.starts_at <= now() + 60
    ):
        fail(409, "Проверьте бюджет, дедлайн и доступность времени")
    if session.scalar(
        select(Booking.id).where(Booking.slot_id == slot.id, Booking.status == "completed")
    ):
        fail(409, "Этот интервал уже использован для состоявшейся встречи")
    if find_conflict(session, [user.id, mentor.user_id], slot):
        fail(409, "Это время уже занято. Выберите другой слот")
    booking = Booking(
        id=str(uuid.uuid4()),
        student_id=user.id,
        mentor_id=mentor.user_id,
        slot_id=slot.id,
        topic_id=topic.id,
        price=mentor.price,
        status="pending",
        description=data["description"],
        deadline=data["deadline"],
        language=data["language"],
        format=data["format"],
        created_at=now(),
        expires_at=min(now() + settings.booking_ttl, slot.starts_at),
        request_key=data["request_key"],
    )
    session.add(booking)
    session.flush()
    notify(
        session,
        mentor.user_id,
        booking.id,
        "new_booking",
        f"Новая заявка: {user.name}, {topic.name}. Подтвердите время в течение 15 минут.",
        f"{booking.id}:new",
    )
    notify(
        session,
        user.id,
        booking.id,
        "created",
        "Заявка отправлена. Ожидаем подтверждения ментора.",
        f"{booking.id}:created",
    )
    return booking_json(session, booking, user.id)


def change_booking(session, user, booking_id, action, settings):
    expire_pending(session)
    booking = get(session, Booking, booking_id)
    if user.id not in (booking.student_id, booking.mentor_id) and not user.is_admin:
        fail(403, "Эта заявка принадлежит другому пользователю")
    slot = get(session, Slot, booking.slot_id)
    if (slot.capacity or 1) > 1:
        from .groups import change_seat

        change_seat(session, user, booking, slot, action, settings)
        return booking_json(session, booking, user.id)
    if action == "request_completion":
        if user.id != booking.mentor_id:
            fail(403, "Завершение запрашивает ментор занятия")
        if booking.status != "confirmed":
            fail(409, "Сначала подтвердите запись")
        if now() < get(session, Slot, booking.slot_id).ends_at and settings.mode != "demo":
            fail(409, "Занятие ещё не закончилось")
        if booking.mentor_completed_at is None:
            booking.mentor_completed_at = now()
            notify(
                session,
                booking.student_id,
                booking.id,
                "completion_requested",
                "Ментор завершил встречу. Подтвердите, что занятие состоялось.",
                f"{booking.id}:completion_requested",
            )
        return booking_json(session, booking, user.id)
    target = {
        "confirm": "confirmed",
        "reject": "rejected",
        "cancel": "cancelled",
        "complete": "completed",
    }.get(action)
    if target is None:
        fail(422, "Неизвестное действие")
    if action in ("confirm", "reject") and user.id != booking.mentor_id:
        fail(403, "Подтвердить или отклонить заявку может только её ментор")
    if action == "complete" and user.id != booking.student_id:
        fail(403, "Студент подтверждает, что занятие состоялось")
    if booking.status == target:
        return booking_json(session, booking, user.id)
    if action in ("confirm", "reject") and booking.status != "pending":
        fail(409, "Заявка уже обработана или время ответа истекло")
    if action == "cancel" and booking.status not in ACTIVE:
        fail(409, "Эту запись уже нельзя отменить")
    if action == "complete":
        if user.id != booking.student_id:
            fail(403, "Студент подтверждает, что занятие состоялось")
        if booking.mentor_completed_at is None:
            fail(409, "Дождитесь отметки ментора о завершении встречи")
        if booking.status != "confirmed":
            fail(409, "Завершить можно только подтверждённое занятие")
        if now() < get(session, Slot, booking.slot_id).ends_at and settings.mode != "demo":
            fail(409, "Завершение доступно после времени окончания занятия")
        booking.completed_at = now()
        topic = get(session, Topic, booking.topic_id)
        for uid in (booking.student_id, booking.mentor_id):
            award(session, uid, topic.subject_id, f"session:{booking.id}", 30)
    if action == "confirm":
        if not (booking.meeting_url if booking.format == "online" else booking.meeting_place):
            fail(422, "Укажите ссылку на встречу или место занятия")
        booking.confirmed_at = now()
        schedule_reminders(session, booking, get(session, Slot, booking.slot_id))
    booking.status = target
    if target in ("cancelled", "rejected"):
        session.flush()
        release_slots(session, [booking.slot_id])
    for uid in (booking.student_id, booking.mentor_id):
        message = STATUS_LABELS[target] + (
            ". Пройдите тест после занятия и оставьте отзыв."
            if action == "complete"
            else ". Откройте StudyMate для деталей."
        )
        notify(session, uid, booking.id, action, message, f"{booking.id}:{target}:{uid}")
    session.flush()
    return booking_json(session, booking, user.id)


def add_review(session, user, booking_id, rating_value, comment):
    booking = get(session, Booking, booking_id)
    if booking.student_id != user.id:
        fail(403, "Отзыв может оставить только студент этого занятия")
    if booking.status != "completed":
        fail(409, "Отзыв доступен после завершения занятия")
    if session.scalar(select(Review).where(Review.booking_id == booking.id)):
        fail(409, "Вы уже оставили отзыв")
    session.add(
        Review(
            booking_id=booking.id,
            student_id=user.id,
            mentor_id=booking.mentor_id,
            rating=rating_value,
            comment=comment,
            created_at=now(),
        )
    )
    session.flush()
    return booking_json(session, booking, user.id)


def progress(session, user):
    plants = []
    for subject in session.scalars(select(Subject)):
        points = session.scalar(
            select(func.coalesce(func.sum(ProgressEvent.points), 0)).where(
                ProgressEvent.user_id == user.id, ProgressEvent.subject_id == subject.id
            )
        )
        level = 3 if points >= 120 else 2 if points >= 60 else 1 if points >= 20 else 0
        plants.append(
            {
                "subject_id": subject.id,
                "name": subject.name,
                "slug": subject.slug,
                "points": points,
                "level": level,
                "next_level": [20, 60, 120, None][level],
            }
        )
    completed = session.scalar(
        select(func.count(Booking.id)).where(
            Booking.status == "completed",
            (Booking.student_id == user.id) | (Booking.mentor_id == user.id),
        )
    )
    successful = session.scalar(
        select(func.count(QuizAttempt.id)).where(
            QuizAttempt.user_id == user.id, QuizAttempt.score >= 2
        )
    )
    return {
        "plants": plants,
        "completed_sessions": completed,
        "successful_tests": successful,
        "points": sum(p["points"] for p in plants),
        "achievements": [
            {
                "name": "Первый зачёт",
                "description": "Успешно пройти первый мини-тест",
                "earned": successful > 0,
            },
            {
                "name": "Знакомый человек",
                "description": "Завершить первое занятие",
                "earned": completed > 0,
            },
            {
                "name": "Широкий кругозор",
                "description": "Набрать опыт по трём предметам",
                "earned": sum(p["level"] > 0 for p in plants) >= 3,
            },
        ],
    }


def stats(session):
    bookings = list(session.scalars(select(Booking)))
    total = len(bookings)
    completed = sum(b.status == "completed" for b in bookings)
    confirms = [b.confirmed_at - b.created_at for b in bookings if b.confirmed_at]
    students = set(b.student_id for b in bookings)
    repeat = sum(sum(b.student_id == uid for b in bookings) >= 2 for uid in students)
    topics = [
        {"topic": t.name, "count": sum(b.topic_id == t.id for b in bookings)}
        for t in session.scalars(select(Topic))
    ]
    return {
        "total": total,
        "completed": completed,
        "completion_rate": round(completed / total * 100, 1) if total else None,
        "cancelled": sum(b.status == "cancelled" for b in bookings),
        "median_confirmation_seconds": median(confirms) if confirms else None,
        "repeat_students": repeat,
        "unique_students": len(students),
        "repeat_rate": round(repeat / len(students) * 100, 1) if students else None,
        "topics": sorted(topics, key=lambda x: -x["count"]),
        "definitions": {
            "completion_rate": "Завершённые занятия / все созданные заявки, включая ожидающие и отменённые",
            "confirmation": "Медианное время от создания до подтверждения; учитываются все когда-либо подтверждённые заявки",
            "repeat": "Студенты с двумя и более заявками / все студенты с заявками; отмены учитываются",
        },
    }
