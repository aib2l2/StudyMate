"""Mentor profile and availability calendar."""

import uuid

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import groups
from ..deps import get_settings, read_session, read_user, write_session, write_user
from ..matching import match_waitlist
from ..models import Booking, Mentor, Slot, Topic, User
from ..schemas import (
    GroupFields,
    GroupSlotInput,
    MeetingInput,
    MentorInput,
    MySlotOut,
    Ok,
    SeriesClosedOut,
    SeriesInput,
    SeriesOut,
    SlotInput,
    SlotOut,
    UserOut,
)
from ..search import reindex_mentor
from ..service import ACTIVE, fail, get, now, profile, slot_json
from . import Router

router = Router(prefix="/api/mentor", tags=["mentor"])
SLOT_SECONDS = 1800


@router.get("/slots", response_model=list[MySlotOut])
def my_slots(user: User = Depends(read_user), s: Session = Depends(read_session)):
    result = []
    for slot in s.scalars(
        select(Slot)
        .where(Slot.mentor_id == user.id, Slot.starts_at > now())
        .order_by(Slot.starts_at)
    ):
        if groups.is_group(slot):
            seats = groups.participants(s, slot)
            result.append(
                {
                    **slot_json(slot, s),
                    "state": "group" if slot.enabled else "closed",
                    "booking_id": seats[0].id if seats else None,
                    "student": None,
                    "students": [get(s, User, b.student_id).name for b in seats],
                }
            )
            continue
        booking = s.scalar(
            select(Booking).where(
                Booking.slot_id == slot.id, Booking.status.in_((*ACTIVE, "completed"))
            )
        )
        result.append(
            {
                **slot_json(slot),
                "state": booking.status if booking else "free" if slot.enabled else "closed",
                "booking_id": booking.id if booking else None,
                "student": get(s, User, booking.student_id).name if booking else None,
            }
        )
    return result


@router.put("/profile", response_model=UserOut)
def update_mentor(
    data: MentorInput, user: User = Depends(write_user), s: Session = Depends(write_session)
):
    if not user.registered:
        fail(422, "Сначала заполните профиль")
    for tid in data.topic_ids:
        get(s, Topic, tid)
    mentor = s.get(Mentor, user.id)
    if not mentor:
        mentor = Mentor(user_id=user.id)
        s.add(mentor)
    # A change of expertise requires a fresh team review.
    if mentor.topic_ids != data.topic_ids or mentor.bio != data.bio:
        mentor.verified = False
    for key, value in data.model_dump().items():
        setattr(mentor, key, value)
    s.flush()
    reindex_mentor(s, user.id)
    return profile(s, user)


class SlotRefused(Exception):
    def __init__(self, status: int, reason: str):
        super().__init__(reason)
        self.status, self.reason = status, reason


def open_slot(
    s: Session,
    user: User,
    starts_at: int,
    series_id: str | None = None,
    group: GroupFields | None = None,
) -> Slot:
    """Create (or reopen) one interval; shared by single slots and series."""
    if not now() + 60 < starts_at < now() + 90 * 86400:
        raise SlotRefused(422, "Выберите время от текущего момента до 90 дней вперёд")
    ends_at = starts_at + SLOT_SECONDS
    existing = s.scalar(
        select(Slot).where(
            Slot.mentor_id == user.id, Slot.starts_at < ends_at, Slot.ends_at > starts_at
        )
    )
    if existing:
        if not existing.enabled and existing.starts_at == starts_at:
            existing.enabled = True
            existing.series_id = series_id or existing.series_id
            if group:
                groups.attach_meeting(s, existing, group)
            s.flush()
            match_waitlist(s, existing)
            return existing
        raise SlotRefused(409, "Этот интервал пересекается с вашим расписанием")
    busy = s.scalar(
        select(Booking)
        .join(Slot)
        .where(
            Booking.student_id == user.id,
            Booking.status.in_(ACTIVE),
            Slot.starts_at < ends_at,
            Slot.ends_at > starts_at,
        )
    )
    if busy:
        raise SlotRefused(409, "В это время у вас уже есть занятие")
    slot = Slot(mentor_id=user.id, starts_at=starts_at, ends_at=ends_at, series_id=series_id)
    s.add(slot)
    s.flush()
    if group:
        groups.attach_meeting(s, slot, group)
    match_waitlist(s, slot)
    return slot


def checked_group(s: Session, user: User, group: GroupFields | None) -> GroupFields | None:
    if group is None:
        return None
    from .bookings import validate_meeting_url

    groups.validate_group(s, get(s, Mentor, user.id), group)
    if group.format == "online":
        validate_meeting_url(group.meeting_url or "")
    return group


@router.post("/slots", response_model=SlotOut)
def add_slot(
    data: SlotInput, user: User = Depends(write_user), s: Session = Depends(write_session)
):
    get(s, Mentor, user.id)
    try:
        return slot_json(open_slot(s, user, data.starts_at))
    except SlotRefused as refused:
        fail(refused.status, refused.reason)


WEEK = 7 * 86400  # Asia/Almaty has no daylight saving time, so a week is always 604800 s


@router.post("/slots/series", response_model=SeriesOut)
def add_series(
    data: SeriesInput, user: User = Depends(write_user), s: Session = Depends(write_session)
):
    """Weekly occurrences stored as ordinary slots sharing a series_id.

    Conflicting weeks are skipped instead of failing the whole series.
    """
    get(s, Mentor, user.id)
    group = checked_group(s, user, data.group)
    series_id = str(uuid.uuid4())
    created, skipped = [], []
    for week in range(data.weeks):
        starts_at = data.starts_at + week * WEEK
        try:
            with s.begin_nested():  # a refused week must not undo earlier ones
                created.append(slot_json(open_slot(s, user, starts_at, series_id, group), s))
        except SlotRefused as refused:
            skipped.append({"starts_at": starts_at, "reason": refused.reason})
    if not created:
        fail(409, "Ни одно время серии не подошло: " + skipped[0]["reason"])
    return {"series_id": series_id, "created": created, "skipped": skipped}


@router.post("/slots/group", response_model=SlotOut)
def add_group_slot(
    data: GroupSlotInput, user: User = Depends(write_user), s: Session = Depends(write_session)
):
    get(s, Mentor, user.id)
    group = checked_group(s, user, data)
    try:
        return slot_json(open_slot(s, user, data.starts_at, group=group), s)
    except SlotRefused as refused:
        fail(refused.status, refused.reason)


def own_group(s: Session, user: User, slot_id: int) -> Slot:
    slot = get(s, Slot, slot_id)
    if slot.mentor_id != user.id:
        fail(403, "Это занятие другого ментора")
    if not groups.is_group(slot):
        fail(409, "Это не групповое занятие")
    return slot


@router.put("/slots/{slot_id}/meeting", response_model=Ok)
def update_group_meeting(
    slot_id: int,
    data: MeetingInput,
    user: User = Depends(write_user),
    s: Session = Depends(write_session),
):
    from .bookings import validate_meeting_url

    if data.meeting_url:
        validate_meeting_url(data.meeting_url)
    groups.update_meeting(s, user, own_group(s, user, slot_id), data)
    return {"ok": True}


@router.post("/slots/{slot_id}/cancel", response_model=Ok)
def cancel_group_slot(
    slot_id: int, user: User = Depends(write_user), s: Session = Depends(write_session)
):
    slot = own_group(s, user, slot_id)
    if slot.starts_at <= now():
        fail(409, "Начавшееся занятие отменить нельзя")
    count = groups.cancel_group(
        s, slot, "Ментор отменил групповое занятие.", f"group-cancelled:{slot.id}"
    )
    return {"ok": True, "message": f"Отменено записей: {count}"}


@router.post("/slots/{slot_id}/complete", response_model=Ok)
def complete_group_slot(
    slot_id: int,
    user: User = Depends(write_user),
    s: Session = Depends(write_session),
    settings=Depends(get_settings),
):
    groups.complete_group(s, user, own_group(s, user, slot_id), settings)
    return {"ok": True}


@router.delete("/series/{series_id}", response_model=SeriesClosedOut)
def close_series(
    series_id: str, user: User = Depends(write_user), s: Session = Depends(write_session)
):
    """Close future free occurrences; those with bookings stay untouched."""
    rows = list(s.scalars(select(Slot).where(Slot.series_id == series_id)))
    if not rows:
        fail(404, "Серия не найдена")
    if any(r.mentor_id != user.id for r in rows):
        fail(403, "Это расписание другого ментора")
    closed = kept = 0
    for slot in rows:
        if slot.starts_at <= now() or not slot.enabled:
            continue
        if s.scalar(
            select(Booking.id).where(
                Booking.slot_id == slot.id, Booking.status.in_((*ACTIVE, "completed"))
            )
        ):
            kept += 1
            continue
        slot.enabled = False
        closed += 1
    return {"closed": closed, "kept_with_bookings": kept}


@router.delete("/slots/{slot_id}", response_model=Ok)
def delete_slot(
    slot_id: int, user: User = Depends(write_user), s: Session = Depends(write_session)
):
    slot = get(s, Slot, slot_id)
    if slot.mentor_id != user.id:
        fail(403, "Это расписание другого ментора")
    if s.scalar(
        select(Booking.id).where(
            Booking.slot_id == slot.id, Booking.status.in_((*ACTIVE, "completed"))
        )
    ):
        fail(409, "На это время есть действующая запись. Сначала отмените её")
    slot.enabled = False
    return {"ok": True}
