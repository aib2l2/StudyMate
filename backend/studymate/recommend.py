"""Explainable mentor recommendations.

``score_mentors`` is a pure, deterministic function over plain data: no
database, no machine learning. The database layer only gathers signals, so
the rules are unit-tested and easy to explain at the defense.
"""

from dataclasses import dataclass, field

WEAK_TOPIC, INTEREST, FAVORITE, LIKED_BEFORE, VERIFIED = 3, 1, 2, 2, 1
NEUTRAL_RATING = 3.0
LIMIT = 6


@dataclass(frozen=True)
class Signals:
    weak_topics: dict[int, tuple[int, str]] = field(default_factory=dict)  # topic -> (score, name)
    interests: frozenset[int] = frozenset()  # subject ids
    interest_names: dict[int, str] = field(default_factory=dict)
    favorites: frozenset[int] = frozenset()
    liked_mentors: frozenset[int] = frozenset()


@dataclass(frozen=True)
class Candidate:
    mentor_id: int
    topic_ids: tuple[int, ...]
    subject_ids: tuple[int, ...]
    verified: bool
    rating_score: float | None


def score_mentors(signals: Signals, candidates: list[Candidate], limit: int = LIMIT):
    """Return [(mentor_id, score, reasons)] best first."""
    ranked = []
    for c in candidates:
        score, reasons = 0.0, []
        for tid in c.topic_ids:
            if tid in signals.weak_topics:
                result, name = signals.weak_topics[tid]
                score += WEAK_TOPIC
                reasons.append(f"Вы ответили {result}/3 по теме «{name}»")
        shared = [sid for sid in dict.fromkeys(c.subject_ids) if sid in signals.interests]
        if shared:
            score += INTEREST
            reasons.append(f"Ваш интерес: {signals.interest_names.get(shared[0], 'предмет')}")
        if c.mentor_id in signals.favorites:
            score += FAVORITE
            reasons.append("В вашем избранном")
        if c.mentor_id in signals.liked_mentors:
            score += LIKED_BEFORE
            reasons.append("Вы уже занимались и поставили 4–5★")
        if c.verified:
            score += VERIFIED
            reasons.append("Проверен командой")
        if c.rating_score is not None:
            score += c.rating_score - NEUTRAL_RATING
            if c.rating_score >= 4.5:
                reasons.append("Высокий рейтинг с учётом числа отзывов")
        ranked.append((c.mentor_id, round(score, 3), reasons))
    ranked.sort(key=lambda r: (-r[1], r[0]))
    return ranked[:limit]
