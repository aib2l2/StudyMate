"""Pages open to guests and shared catalog data."""

from typing import Literal

from fastapi import Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..deps import get_settings, read_session, read_user
from ..models import Mentor, Review, Subject, Topic, User
from ..schemas import ConfigOut, HealthOut, MentorCardOut, SubjectOut
from ..service import available_slots, catalog, fail, find_matches, get, mentor_card, now
from . import Router

router = Router(prefix="/api", tags=["public"])
Sort = Literal["soonest", "price", "rating"]

DEMO_ACCOUNTS = [
    {"id": 1, "name": "Аликхан", "role": "Студент"},
    {"id": 2, "name": "Аяулым", "role": "Ментор"},
    {"id": 3, "name": "Ерлан", "role": "Второй студент"},
    {"id": 99, "name": "Команда", "role": "Администратор"},
]


@router.get("/health", response_model=HealthOut)
def health(request: Request):
    task = request.app.state.worker_task
    state = "running" if task and not task.done() else "failed" if task else "disabled"
    return {
        "status": "degraded" if state == "failed" else "ok",
        "mode": request.app.state.settings.mode,
        "notification_worker": state,
    }


@router.get("/config", response_model=ConfigOut)
def config(settings=Depends(get_settings)):
    return {
        "mode": settings.mode,
        "timezone": "Asia/Almaty",
        "payment": "simulation_only",
        "demo_accounts": DEMO_ACCOUNTS if settings.mode == "demo" else [],
    }


@router.get("/catalog", response_model=list[SubjectOut])
def get_catalog(user: User = Depends(read_user), s: Session = Depends(read_session)):
    return catalog(s)


@router.get("/public/catalog", response_model=list[SubjectOut])
def public_catalog(s: Session = Depends(read_session)):
    return catalog(s)


@router.get("/public/mentors", response_model=list[MentorCardOut])
def public_mentors(
    topic_id: int | None = None,
    budget: int = Query(default=100000, ge=0, le=100000),
    earliest: int | None = None,
    deadline: int | None = None,
    language: Literal["ru", "en", "kk"] = "ru",
    format: Literal["online", "campus"] = "online",
    q: str = Query(default="", max_length=200),
    sort: Sort = "soonest",
    s: Session = Depends(read_session),
):
    return find_matches(
        s, None, topic_id, budget, earliest, deadline, language, format, q=q, sort=sort
    )


@router.get("/public/mentors/{mentor_id}", response_model=MentorCardOut)
def public_mentor(mentor_id: int, s: Session = Depends(read_session)):
    mentor = get(s, Mentor, mentor_id)
    if (
        mentor.suspended
        or not mentor.active
        or not any(
            get(s, Subject, get(s, Topic, tid).subject_id).active for tid in mentor.topic_ids
        )
    ):
        fail(404, "Ментор сейчас не принимает заявки")
    card = mentor_card(s, mentor, available_slots(s, mentor_id, now(), now() + 30 * 86400), [])
    card["reviews"] = [
        {
            "rating": r.rating,
            "comment": r.comment,
            "student": get(s, User, r.student_id).name,
            "created_at": r.created_at,
        }
        for r in s.scalars(
            select(Review)
            .where(Review.mentor_id == mentor_id)
            .order_by(Review.created_at.desc())
            .limit(20)
        )
    ]
    return card


@router.get("/mentors", response_model=list[MentorCardOut])
def mentors(
    topic_id: int | None = None,
    budget: int = Query(default=100000, ge=0, le=100000),
    earliest: int | None = None,
    deadline: int | None = None,
    language: Literal["ru", "en", "kk"] = "ru",
    format: Literal["online", "campus"] = "online",
    q: str = Query(default="", max_length=200),
    sort: Sort = "soonest",
    favorites_only: bool = False,
    user: User = Depends(read_user),
    s: Session = Depends(read_session),
):
    return find_matches(
        s,
        user,
        topic_id,
        budget,
        earliest,
        deadline,
        language,
        format,
        q=q,
        sort=sort,
        favorites_only=favorites_only,
    )
