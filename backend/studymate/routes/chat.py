"""Lesson chat endpoints."""

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from ..auth import RateLimiter
from ..chat import list_messages, mark_read, post_message
from ..deps import read_session, read_user, write_session, write_user
from ..models import Booking, User
from ..schemas import MessageInput, MessageOut, Ok, ReadInput, ThreadOut
from ..service import fail, get
from . import Router

router = Router(prefix="/api/bookings", tags=["chat"])


def chat_limiter(request: Request) -> RateLimiter:
    return request.app.state.chat_limiter


@router.get("/{booking_id}/messages", response_model=ThreadOut)
def messages(
    booking_id: str,
    after_id: int = 0,
    user: User = Depends(read_user),
    s: Session = Depends(read_session),
):
    return list_messages(s, user, get(s, Booking, booking_id), after_id)


@router.post("/{booking_id}/messages", response_model=MessageOut)
def send(
    booking_id: str,
    data: MessageInput,
    user: User = Depends(write_user),
    s: Session = Depends(write_session),
    limiter: RateLimiter = Depends(chat_limiter),
):
    if not limiter.hit(f"user:{user.id}", "chat"):
        fail(429, "Слишком много сообщений подряд. Подождите минуту")
    return post_message(s, user, get(s, Booking, booking_id), data.body, data.client_id)


@router.post("/{booking_id}/messages/read", response_model=Ok)
def read(
    booking_id: str,
    data: ReadInput,
    user: User = Depends(write_user),
    s: Session = Depends(write_session),
):
    mark_read(s, user, get(s, Booking, booking_id), data.last_read_id)
    return {"ok": True}
