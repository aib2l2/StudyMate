"""Mentor text search: SQLite FTS5 with a LIKE fallback.

The index is synchronised from the service layer (``reindex_mentor``) rather
than by triggers: it spans several tables (users, mentors, topics, subjects)
and only a few write paths change it.
"""

import logging
import re

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from .models import Mentor, Subject, Topic, User

TOKEN = re.compile(r"\w+", re.UNICODE)
MAX_TOKENS = 8
log = logging.getLogger("studymate")


def fts_available(bind) -> bool:
    try:
        bind.execute(text("CREATE VIRTUAL TABLE temp.fts_probe USING fts5(x)"))
        bind.execute(text("DROP TABLE temp.fts_probe"))
        return True
    except Exception:  # sqlite built without FTS5
        log.warning("SQLite FTS5 is unavailable; mentor search falls back to LIKE")
        return False


def index_exists(bind) -> bool:
    return (
        bind.execute(
            text("SELECT 1 FROM sqlite_master WHERE type='table' AND name='mentor_search'")
        ).first()
        is not None
    )


def create_index(bind) -> None:
    bind.execute(
        text(
            "CREATE VIRTUAL TABLE IF NOT EXISTS mentor_search USING fts5("
            "name, bio, topics, tokenize='unicode61 remove_diacritics 2')"
        )
    )


def tokens(query: str | None) -> list[str]:
    """Words of 2–40 characters; at most 8. Raw input never reaches MATCH."""
    words = [w.lower() for w in TOKEN.findall(query or "") if 2 <= len(w) <= 40]
    return words[:MAX_TOKENS]


def fts_query(words: list[str]) -> str:
    # Each word becomes a quoted prefix term; spaces mean AND in FTS5.
    return " ".join('"' + w.replace('"', "") + '"*' for w in words)


def _document(session_or_conn, user_id: int) -> tuple[str, str, str] | None:
    exec_ = session_or_conn.execute
    row = exec_(
        text(
            "SELECT u.name, m.bio, m.topic_ids FROM mentors m JOIN users u ON u.id = m.user_id "
            "WHERE m.user_id = :id"
        ),
        {"id": user_id},
    ).first()
    if row is None:
        return None
    import json

    topic_ids = row.topic_ids if isinstance(row.topic_ids, list) else json.loads(row.topic_ids)
    names = []
    for tid in topic_ids:
        found = exec_(
            text(
                "SELECT t.name, s.name FROM topics t JOIN subjects s ON s.id = t.subject_id "
                "WHERE t.id = :id"
            ),
            {"id": tid},
        ).first()
        if found:
            names += [found[0], found[1]]
    return row.name, row.bio, " ".join(dict.fromkeys(names))


def reindex_mentor(session: Session | Connection, user_id: int) -> None:
    if not index_exists(session):
        return
    session.execute(text("DELETE FROM mentor_search WHERE rowid = :id"), {"id": user_id})
    doc = _document(session, user_id)
    if doc:
        session.execute(
            text("INSERT INTO mentor_search(rowid, name, bio, topics) VALUES (:id, :n, :b, :t)"),
            {"id": user_id, "n": doc[0], "b": doc[1], "t": doc[2]},
        )


def reindex_all(session: Session | Connection) -> int:
    if not index_exists(session):
        return 0
    session.execute(text("DELETE FROM mentor_search"))
    ids = [r[0] for r in session.execute(text("SELECT user_id FROM mentors"))]
    for uid in ids:
        reindex_mentor(session, uid)
    return len(ids)


def matching_ids(session: Session, query: str | None) -> set[int] | None:
    """Mentor ids matching the query, or None when there is no text filter."""
    words = tokens(query)
    if not words:
        return None
    if index_exists(session):
        rows = session.execute(
            text("SELECT rowid FROM mentor_search WHERE mentor_search MATCH :q"),
            {"q": fts_query(words)},
        )
        return {r[0] for r in rows}
    return like_ids(session, words)


def like_ids(session: Session, words: list[str]) -> set[int]:
    """Fallback without FTS5: every word must start a word in name/bio/topics."""
    result = set()
    for mentor in session.query(Mentor):
        user = session.get(User, mentor.user_id)
        topic_names = []
        for tid in mentor.topic_ids:
            topic = session.get(Topic, tid)
            if topic:
                topic_names += [topic.name, session.get(Subject, topic.subject_id).name]
        haystack = {
            w.lower() for w in TOKEN.findall(" ".join([user.name, mentor.bio, *topic_names]))
        }
        if all(any(h.startswith(w) for h in haystack) for w in words):
            result.add(mentor.user_id)
    return result
