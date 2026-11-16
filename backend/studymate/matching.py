"""Waitlist matches and the database side of recommendations."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Booking, Mentor, QuizAttempt, Review, Slot, Subject, Topic, User, Waitlist
from .recommend import Candidate, Signals, score_mentors
from .service import ACTIVE, available_slots, favorite_ids, get, mentor_card, notify, now, rating


def mentor_open(session: Session, mentor: Mentor | None) -> bool:
    """Accepting requests: active, not suspended by the team, an active topic."""
    if mentor is None or not mentor.active or mentor.suspended:
        return False
    return any(
        (t := session.get(Topic, tid)) and session.get(Subject, t.subject_id).active
        for tid in mentor.topic_ids
    )


def slot_free(session: Session, slot: Slot) -> bool:
    if not slot.enabled or slot.starts_at <= now() + 60:
        return False
    taken = session.scalar(
        select(func.count(Booking.id)).where(
            Booking.slot_id == slot.id, Booking.status.in_((*ACTIVE, "completed"))
        )
    )
    return taken < (getattr(slot, "capacity", 1) or 1)


def match_waitlist(session: Session, slot: Slot) -> int:
    """Notify students whose waitlist request this free slot now satisfies."""
    mentor = session.get(Mentor, slot.mentor_id)
    if not mentor_open(session, mentor) or not slot_free(session, slot):
        return 0
    person = get(session, User, mentor.user_id)
    price = getattr(slot, "price", None) or mentor.price
    slot_topic = getattr(slot, "topic_id", None)
    sent = 0
    for wait in session.scalars(
        select(Waitlist).where(
            Waitlist.deadline >= slot.ends_at,
            Waitlist.earliest <= slot.starts_at,
            Waitlist.budget >= price,
            Waitlist.student_id != mentor.user_id,
        )
    ):
        if wait.topic_id not in mentor.topic_ids or (slot_topic and slot_topic != wait.topic_id):
            continue
        if wait.language not in person.languages or wait.format not in mentor.formats:
            continue
        student = session.get(User, wait.student_id)
        if student is None or student.campus != person.campus:
            continue
        topic = get(session, Topic, wait.topic_id)
        favorite = mentor.user_id in favorite_ids(session, wait.student_id)
        notify(
            session,
            wait.student_id,
            None,
            "waitlist_match",
            f"Появилось время по теме «{topic.name}»: {person.name}"
            + (" (в избранном)" if favorite else ""),
            f"waitlist:{wait.id}:{slot.id}",
            link=f"/mentors/{mentor.user_id}",
        )
        sent += 1
    return sent


def gather_signals(session: Session, user: User) -> Signals:
    latest: dict[int, QuizAttempt] = {}
    for attempt in session.scalars(
        select(QuizAttempt)
        .where(QuizAttempt.user_id == user.id, QuizAttempt.submitted_at.is_not(None))
        .order_by(QuizAttempt.submitted_at)
    ):
        latest[attempt.topic_id] = attempt
    weak = {
        tid: (a.score, get(session, Topic, tid).name)
        for tid, a in latest.items()
        if a.score is not None and a.score < 2
    }
    liked = set(
        session.scalars(
            select(Review.mentor_id).where(Review.student_id == user.id, Review.rating >= 4)
        )
    )
    subjects = {s.id: s.name for s in session.scalars(select(Subject))}
    return Signals(
        weak_topics=weak,
        interests=frozenset(user.interests or []),
        interest_names=subjects,
        favorites=frozenset(favorite_ids(session, user.id)),
        liked_mentors=frozenset(liked),
    )


def recommendations(session: Session, user: User, horizon_days: int = 14) -> list[dict]:
    signals = gather_signals(session, user)
    candidates, slots_by_mentor = [], {}
    for mentor in session.scalars(select(Mentor).where(Mentor.user_id != user.id)):
        if not mentor_open(session, mentor):
            continue
        person = get(session, User, mentor.user_id)
        if person.campus != user.campus:
            continue
        slots = available_slots(session, mentor.user_id, now(), now() + horizon_days * 86400)
        if not slots:
            continue
        slots_by_mentor[mentor.user_id] = slots
        topics = [t for t in (session.get(Topic, tid) for tid in mentor.topic_ids) if t]
        candidates.append(
            Candidate(
                mentor_id=mentor.user_id,
                topic_ids=tuple(t.id for t in topics),
                subject_ids=tuple(t.subject_id for t in topics),
                verified=mentor.verified,
                rating_score=rating(session, mentor.user_id)["rating_score"],
            )
        )
    result = []
    for mentor_id, _score, reasons in score_mentors(signals, candidates):
        mentor = session.get(Mentor, mentor_id)
        result.append(
            mentor_card(
                session,
                mentor,
                slots_by_mentor[mentor_id][:6],
                reasons or ["Есть свободное время в ближайшие две недели"],
                mentor_id in signals.favorites,
            )
        )
    return result
