"""Team (moderation) section."""

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..deps import read_admin, read_session, write_admin, write_session
from ..models import Mentor, Notification, Subject, Topic, User, Waitlist
from ..schemas import AdminOut, Ok, SubjectInput, VerifyInput
from ..search import reindex_all
from ..service import catalog, get, list_bookings, mentor_card, stats
from . import Router

router = Router(prefix="/api/admin", tags=["admin"])


@router.get("", response_model=AdminOut)
def admin_data(user: User = Depends(read_admin), s: Session = Depends(read_session)):
    return {
        "stats": stats(s),
        "mentors": [mentor_card(s, m, [], []) for m in s.scalars(select(Mentor))],
        "bookings": list_bookings(s, user, True),
        "catalog": catalog(s),
        "waitlist": [
            {
                "student": get(s, User, w.student_id).name,
                "topic": get(s, Topic, w.topic_id).name,
                "deadline": w.deadline,
                "budget": w.budget,
            }
            for w in s.scalars(select(Waitlist))
        ],
        "delivery_issues": [
            {"id": n.id, "status": n.status, "kind": n.kind}
            for n in s.scalars(
                select(Notification).where(Notification.status.in_(["uncertain", "failed"]))
            )
        ],
    }


@router.put("/mentors/{mentor_id}", response_model=Ok)
def verify(
    mentor_id: int,
    data: VerifyInput,
    user: User = Depends(write_admin),
    s: Session = Depends(write_session),
):
    mentor = get(s, Mentor, mentor_id)
    mentor.verified, mentor.suspended = data.verified, not data.active
    return {"ok": True}


@router.put("/subjects/{subject_id}", response_model=Ok)
def subject_update(
    subject_id: int,
    data: SubjectInput,
    user: User = Depends(write_admin),
    s: Session = Depends(write_session),
):
    subject = get(s, Subject, subject_id)
    renamed = subject.name != data.name
    subject.name, subject.active = data.name, data.active
    if renamed:
        s.flush()
        reindex_all(s)  # subject names are part of the search document
    return {"ok": True}
