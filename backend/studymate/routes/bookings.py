"""Booking lifecycle, the lesson page, reviews and the payment simulation."""

from urllib.parse import urlsplit

from fastapi import Depends
from sqlalchemy.orm import Session

from .. import groups
from ..config import Settings
from ..deps import get_settings, read_session, read_user, write_session, write_user
from ..models import Booking, LessonNote, PaymentSimulation, Slot, User
from ..schemas import (
    ActionInput,
    BookingInput,
    BookingOut,
    LessonOut,
    Ok,
    PaymentOut,
    ReviewInput,
    WorkspaceInput,
)
from ..service import (
    add_review,
    booking_json,
    change_booking,
    create_booking,
    expire_pending,
    fail,
    get,
    list_bookings,
    now,
)
from . import Router

router = Router(prefix="/api/bookings", tags=["bookings"])


def validate_meeting_url(value: str) -> None:
    try:
        parts = urlsplit(value.strip())
        _ = parts.port  # raises ValueError for a malformed port
    except ValueError:
        fail(422, "Проверьте адрес ссылки на встречу")
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        fail(422, "Для встречи укажите HTTPS-ссылку без логина и пароля")


def lesson_access(s: Session, user: User, booking_id: str) -> Booking:
    expire_pending(s)
    booking = get(s, Booking, booking_id)
    if user.id not in (booking.student_id, booking.mentor_id) and not user.is_admin:
        fail(403, "Это занятие другого пользователя")
    return booking


@router.get("", response_model=list[BookingOut])
def bookings(user: User = Depends(read_user), s: Session = Depends(read_session)):
    return list_bookings(s, user)


@router.post("", response_model=BookingOut)
def book(
    data: BookingInput,
    user: User = Depends(write_user),
    s: Session = Depends(write_session),
    settings: Settings = Depends(get_settings),
):
    return create_booking(s, user, data.model_dump(), settings)


@router.post("/{booking_id}/action", response_model=BookingOut)
def booking_action(
    booking_id: str,
    data: ActionInput,
    user: User = Depends(write_user),
    s: Session = Depends(write_session),
    settings: Settings = Depends(get_settings),
):
    if data.action == "confirm" and (
        data.meeting_url is not None or data.meeting_place is not None
    ):
        booking = get(s, Booking, booking_id)
        if booking.mentor_id != user.id:
            fail(403, "Место встречи задаёт ментор этого занятия")
        if booking.status == "pending":
            if data.meeting_url:
                validate_meeting_url(data.meeting_url)
            if data.meeting_url is not None:
                booking.meeting_url = data.meeting_url.strip()
            if data.meeting_place is not None:
                booking.meeting_place = data.meeting_place.strip()
    return change_booking(s, user, booking_id, data.action, settings)


@router.get("/{booking_id}", response_model=LessonOut)
def lesson(booking_id: str, user: User = Depends(read_user), s: Session = Depends(read_session)):
    booking = lesson_access(s, user, booking_id)
    note = s.get(LessonNote, (booking_id, user.id))
    viewer = user.id if user.id in (booking.student_id, booking.mentor_id) else None
    return {**booking_json(s, booking, viewer), "notes": note.body if note else ""}


@router.put("/{booking_id}/workspace", response_model=Ok)
def workspace(
    booking_id: str,
    data: WorkspaceInput,
    user: User = Depends(write_user),
    s: Session = Depends(write_session),
):
    booking = lesson_access(s, user, booking_id)
    slot = get(s, Slot, booking.slot_id)
    if groups.is_group(slot) and any(
        getattr(data, n) is not None for n in ("meeting_url", "meeting_place", "materials")
    ):
        if user.id != booking.mentor_id:
            fail(403, "Ссылку, место и материалы редактирует ментор занятия")
        if data.meeting_url:
            validate_meeting_url(data.meeting_url)
        groups.update_meeting(s, user, slot, data)
        data = data.model_copy(
            update={"meeting_url": None, "meeting_place": None, "materials": None}
        )
    for name in ("meeting_url", "meeting_place", "materials"):
        value = getattr(data, name)
        if value is None:
            continue
        if user.id != booking.mentor_id:
            fail(403, "Ссылку, место и материалы редактирует ментор занятия")
        if name == "meeting_url" and value:
            validate_meeting_url(value)
        required = "meeting_url" if booking.format == "online" else "meeting_place"
        if booking.status == "confirmed" and name == required and not value.strip():
            fail(422, "Подтверждённому занятию нужно место встречи")
        setattr(booking, name, value.strip())
    if data.notes is not None:
        if user.id not in (booking.student_id, booking.mentor_id):
            fail(403, "Личные заметки доступны только участникам")
        note = s.get(LessonNote, (booking_id, user.id))
        if not note:
            note = LessonNote(booking_id=booking_id, user_id=user.id)
            s.add(note)
        note.body, note.updated_at = data.notes, now()
    s.flush()
    return {"ok": True}


@router.post("/{booking_id}/review", response_model=BookingOut)
def review(
    booking_id: str,
    data: ReviewInput,
    user: User = Depends(write_user),
    s: Session = Depends(write_session),
):
    return add_review(s, user, booking_id, data.rating, data.comment)


@router.post("/{booking_id}/payment-simulation", response_model=PaymentOut)
def payment_simulation(
    booking_id: str,
    user: User = Depends(write_user),
    s: Session = Depends(write_session),
    settings: Settings = Depends(get_settings),
):
    booking = get(s, Booking, booking_id)
    if booking.student_id != user.id:
        fail(403, "Расчёт доступен только студенту этого занятия")
    if booking.status not in ("confirmed", "completed"):
        fail(409, "Дождитесь подтверждения ментора")
    receipt = s.get(PaymentSimulation, booking_id)
    if not receipt:
        receipt = PaymentSimulation(
            booking_id=booking_id,
            receipt_id="DEMO-" + booking_id[:12],
            amount=booking.price,
            commission=round(booking.price * settings.commission_percent / 100),
            created_at=now(),
        )
        s.add(receipt)
        s.flush()
    return {
        "id": receipt.receipt_id,
        "amount": receipt.amount,
        "commission": receipt.commission,
        "mentor_amount": receipt.amount - receipt.commission,
        "charged": 0,
        "simulation": True,
    }
