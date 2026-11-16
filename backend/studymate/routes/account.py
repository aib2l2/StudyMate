"""The signed-in user's profile, progress, notifications, waitlist and data export."""

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..deps import read_session, read_user, write_session, write_user
from ..models import (
    ChatMessage,
    LessonNote,
    Notification,
    QuizAttempt,
    Subject,
    Topic,
    User,
    Waitlist,
)
from ..schemas import (
    ExportOut,
    NotificationOut,
    Ok,
    ProfileInput,
    ProgressOut,
    UserOut,
    WaitlistInput,
    WaitlistOut,
)
from ..search import reindex_mentor
from ..service import fail, get, list_bookings, now, profile, progress
from . import Router

router = Router(prefix="/api", tags=["account"])


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(read_user), s: Session = Depends(read_session)):
    return profile(s, user)


@router.put("/me", response_model=UserOut)
def update_me(
    data: ProfileInput, user: User = Depends(write_user), s: Session = Depends(write_session)
):
    if any(not s.get(Subject, sid) for sid in data.interests):
        fail(422, "Выберите предметы из каталога")
    if not data.name.strip():
        fail(422, "Введите имя")
    for key, value in data.model_dump().items():
        setattr(user, key, value.strip() if key == "name" else value)
    user.registered = True
    s.flush()
    reindex_mentor(s, user.id)  # the name is searchable
    return profile(s, user)


@router.get("/progress", response_model=ProgressOut)
def get_progress(user: User = Depends(read_user), s: Session = Depends(read_session)):
    return progress(s, user)


def waitlist_rows(s: Session, user: User) -> list[dict]:
    rows = s.scalars(
        select(Waitlist).where(Waitlist.student_id == user.id).order_by(Waitlist.created_at.desc())
    )
    return [
        {
            "id": x.id,
            "topic": get(s, Topic, x.topic_id).name,
            "deadline": x.deadline,
            "budget": x.budget,
        }
        for x in rows
    ]


@router.get("/waitlist", response_model=list[WaitlistOut])
def waitlist(user: User = Depends(read_user), s: Session = Depends(read_session)):
    return waitlist_rows(s, user)


@router.post("/waitlist", response_model=Ok)
def join_waitlist(
    data: WaitlistInput, user: User = Depends(write_user), s: Session = Depends(write_session)
):
    get(s, Topic, data.topic_id)
    if data.deadline <= max(now(), data.earliest):
        fail(422, "Проверьте дедлайн и удобное время")
    existing = s.scalar(
        select(Waitlist).where(
            Waitlist.student_id == user.id,
            Waitlist.topic_id == data.topic_id,
            Waitlist.deadline == data.deadline,
        )
    )
    if not existing:
        s.add(Waitlist(student_id=user.id, created_at=now(), **data.model_dump()))
    return {"ok": True, "message": "Заявка сохранена. Команда видит её в листе ожидания"}


@router.get("/notifications", response_model=list[NotificationOut])
def notifications(user: User = Depends(read_user), s: Session = Depends(read_session)):
    return [
        {
            "id": n.id,
            "body": n.body,
            "kind": n.kind,
            "booking_id": n.booking_id,
            "status": n.status,
            "read": n.read,
            "due_at": n.due_at,
            "link": n.link,
        }
        for n in s.scalars(
            select(Notification)
            .where(
                Notification.user_id == user.id,
                Notification.due_at <= now(),
                Notification.status != "skipped",
            )
            .order_by(Notification.id.desc())
            .limit(30)
        )
    ]


@router.post("/notifications/read", response_model=Ok)
def read_notifications(user: User = Depends(write_user), s: Session = Depends(write_session)):
    for row in s.scalars(
        select(Notification).where(Notification.user_id == user.id, Notification.due_at <= now())
    ):
        row.read = True
    return {"ok": True}


@router.get("/me/export", response_model=ExportOut)
def export_my_data(user: User = Depends(read_user), s: Session = Depends(read_session)):
    """Everything StudyMate stores about the user, minus other people's private notes."""
    notes = s.scalars(select(LessonNote).where(LessonNote.user_id == user.id))
    attempts = s.scalars(
        select(QuizAttempt).where(QuizAttempt.user_id == user.id).order_by(QuizAttempt.created_at)
    )
    return {
        "exported_at": now(),
        "profile": profile(s, user),
        "bookings": list_bookings(s, user),
        "notes": [
            {"booking_id": n.booking_id, "body": n.body, "updated_at": n.updated_at} for n in notes
        ],
        "quiz_attempts": [
            {
                "id": a.id,
                "topic_id": a.topic_id,
                "booking_id": a.booking_id,
                "stage": a.stage,
                "score": a.score,
                "created_at": a.created_at,
                "submitted_at": a.submitted_at,
            }
            for a in attempts
        ],
        "progress": progress(s, user),
        "waitlist": waitlist_rows(s, user),
        # Only messages the user wrote: other people's words are theirs to export.
        "messages": [
            {"thread": m.thread_key, "body": m.body, "created_at": m.created_at}
            for m in s.scalars(
                select(ChatMessage).where(ChatMessage.sender_id == user.id).order_by(ChatMessage.id)
            )
        ],
    }
