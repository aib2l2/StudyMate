"""Rescheduling and calendar export (.ics)."""

from fastapi import Depends
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import reschedule as moves
from ..deps import read_session, read_user, write_session, write_user
from ..ics import calendar
from ..models import Booking, Slot, Topic, User
from ..schemas import BookingOut, Ok, RescheduleInput, RescheduleOut, SlotOut
from ..service import booking_json, fail, get, now, slot_json
from . import Router

router = Router(prefix="/api", tags=["calendar"])


@router.get("/bookings/{booking_id}/reschedule-options", response_model=list[SlotOut])
def reschedule_options(
    booking_id: str, user: User = Depends(read_user), s: Session = Depends(read_session)
):
    return [slot_json(x) for x in moves.options(s, user, get(s, Booking, booking_id))]


@router.post("/bookings/{booking_id}/reschedule", response_model=RescheduleOut)
def propose(
    booking_id: str,
    data: RescheduleInput,
    user: User = Depends(write_user),
    s: Session = Depends(write_session),
):
    req = moves.propose(s, user, get(s, Booking, booking_id), data.slot_id)
    return {
        "id": req.id,
        "proposed_slot": slot_json(get(s, Slot, req.proposed_slot_id)),
        "requested_by": req.requested_by,
        "expires_at": req.expires_at,
    }


@router.post("/reschedule/{rid}/accept", response_model=BookingOut)
def accept(rid: int, user: User = Depends(write_user), s: Session = Depends(write_session)):
    return booking_json(s, moves.accept(s, user, rid), user.id)


@router.post("/reschedule/{rid}/decline", response_model=Ok)
def decline(rid: int, user: User = Depends(write_user), s: Session = Depends(write_session)):
    moves.decline(s, user, rid)
    return {"ok": True}


@router.post("/reschedule/{rid}/cancel", response_model=Ok)
def cancel(rid: int, user: User = Depends(write_user), s: Session = Depends(write_session)):
    moves.cancel(s, user, rid)
    return {"ok": True}


def _event(s: Session, booking: Booking, user: User) -> dict:
    slot = get(s, Slot, booking.slot_id)
    topic = get(s, Topic, booking.topic_id)
    other = booking.mentor_id if user.id == booking.student_id else booking.student_id
    meeting = booking_json(s, booking)  # group lessons keep the place on the slot
    return {
        "uid": f"{booking.id}@studymate.local",
        "start": slot.starts_at,
        "end": slot.ends_at,
        "sequence": booking.reschedule_count or 0,
        "summary": f"StudyMate: {topic.name}",
        "description": f"Встреча с {get(s, User, other).name}. Страница: /lessons/{booking.id}",
        "location": meeting["meeting_place"],
        "url": meeting["meeting_url"],
    }


def _ics(body: str, filename: str) -> Response:
    return Response(
        body,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/bookings/{booking_id}/calendar.ics", include_in_schema=False)
def booking_ics(
    booking_id: str, user: User = Depends(read_user), s: Session = Depends(read_session)
):
    booking = get(s, Booking, booking_id)
    if user.id not in (booking.student_id, booking.mentor_id):
        fail(403, "Это занятие другого пользователя")
    if booking.status != "confirmed":
        fail(409, "В календарь можно добавить подтверждённую встречу")
    return _ics(calendar([_event(s, booking, user)], now()), "studymate-lesson.ics")


@router.get("/calendar.ics", include_in_schema=False)
def all_ics(user: User = Depends(read_user), s: Session = Depends(read_session)):
    rows = s.scalars(
        select(Booking)
        .join(Slot, Slot.id == Booking.slot_id)
        .where(
            Booking.status == "confirmed",
            Slot.ends_at > now(),
            (Booking.student_id == user.id) | (Booking.mentor_id == user.id),
        )
        .order_by(Slot.starts_at)
    )
    return _ics(calendar([_event(s, b, user) for b in rows], now()), "studymate.ics")
