"""Favorites and recommendations."""

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from ..deps import read_session, read_user, write_session, write_user
from ..matching import mentor_open, recommendations
from ..models import Favorite, Mentor, User
from ..schemas import MentorCardOut, Ok
from ..service import available_slots, fail, get, mentor_card, now
from . import Router

router = Router(prefix="/api", tags=["discover"])


@router.put("/favorites/{mentor_id}", response_model=Ok)
def add_favorite(
    mentor_id: int, user: User = Depends(write_user), s: Session = Depends(write_session)
):
    get(s, Mentor, mentor_id)
    if mentor_id == user.id:
        fail(422, "Себя добавить в избранное нельзя")
    s.execute(
        insert(Favorite)
        .values(user_id=user.id, mentor_id=mentor_id, created_at=now())
        .on_conflict_do_nothing()
    )
    return {"ok": True}


@router.delete("/favorites/{mentor_id}", response_model=Ok)
def remove_favorite(
    mentor_id: int, user: User = Depends(write_user), s: Session = Depends(write_session)
):
    row = s.get(Favorite, (user.id, mentor_id))
    if row:
        s.delete(row)
    return {"ok": True}


@router.get("/favorites", response_model=list[MentorCardOut])
def favorites(user: User = Depends(read_user), s: Session = Depends(read_session)):
    """Favorite mentors; a paused profile stays listed but without bookable time."""
    cards = []
    for fav in s.scalars(
        select(Favorite).where(Favorite.user_id == user.id).order_by(Favorite.created_at.desc())
    ):
        mentor = get(s, Mentor, fav.mentor_id)
        open_ = mentor_open(s, mentor)
        slots = available_slots(s, mentor.user_id, now(), now() + 14 * 86400) if open_ else []
        reasons = [] if open_ else ["Сейчас не принимает заявки"]
        cards.append(mentor_card(s, mentor, slots[:6], reasons, True))
    return cards


@router.get("/recommendations", response_model=list[MentorCardOut])
def recommended(user: User = Depends(read_user), s: Session = Depends(read_session)):
    return recommendations(s, user)
