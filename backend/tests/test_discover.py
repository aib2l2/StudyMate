"""Part B: text search, Bayesian sorting, favorites, waitlist matches, recommendations."""

import time

from conftest import book, login, proposal
from sqlalchemy import select
from studymate import search
from studymate.models import Notification, Review
from studymate.quizzes import BANK
from studymate.recommend import Candidate, Signals, score_mentors


def deadline():
    return int(time.time()) + 5 * 86400


def mentors(client, headers=None, **params):
    query = "&".join(f"{k}={v}" for k, v in {"deadline": deadline(), **params}.items())
    path = "/api/mentors?" if headers else "/api/public/mentors?"
    response = client.get(path + query, headers=headers or {})
    assert response.status_code == 200, response.text
    return response.json()


def notices(client, user_id, kind):
    from types import SimpleNamespace

    with client.app.state.db.read() as session:
        rows = session.scalars(
            select(Notification).where(Notification.user_id == user_id, Notification.kind == kind)
        ).all()
        return [SimpleNamespace(body=n.body, link=n.link) for n in rows]


# ------------------------------------------------------------------ search


def test_text_search_by_name_topic_and_prefix(client):
    assert {m["id"] for m in mentors(client, q="Аяул")} == {2}
    sql = {m["id"] for m in mentors(client, q="sql")}
    assert 2 in sql and 14 not in sql  # Ерасыл teaches networks
    both = {m["id"] for m in mentors(client, q="базы аяулым")}
    assert both == {2}  # all words must match
    assert mentors(client, q="несуществующееслово") == []


def test_search_input_cannot_break_fts(client):
    for raw in ['"*OR(', "NEAR(a b)", "a* AND -b", "'; DROP TABLE users; --", "*"]:
        assert client.get(f"/api/public/mentors?q={raw}").status_code == 200
    assert search.tokens("a" * 50 + " ок x") == ["ок"]
    assert search.fts_query(["sql", 'jo"in']) == '"sql"* "join"*'


def test_like_fallback_gives_same_results(client, monkeypatch):
    with_fts = {m["id"] for m in mentors(client, q="sql")}
    monkeypatch.setattr(search, "index_exists", lambda _bind: False)
    assert {m["id"] for m in mentors(client, q="sql")} == with_fts
    assert {m["id"] for m in mentors(client, q="Аяул")} == {2}


def test_profile_edit_reindexes_mentor(client):
    mentor = login(client, 2)
    profile = client.get("/api/me", headers=mentor).json()["mentor"]
    profile["bio"] = "Объясняю через пиццерию и таблицы заказов: уникальныйпример"
    assert client.put("/api/mentor/profile", headers=mentor, json=profile).status_code == 200
    assert {m["id"] for m in mentors(client, q="уникальныйпример")} == {2}
    with client.app.state.db.write() as session:
        assert search.reindex_all(session) >= 9


# ----------------------------------------------------------------- sorting


def test_rating_sort_uses_bayesian_average(client):
    rows = mentors(client, sort="rating", topic_id=1)
    scores = [m["rating_score"] or 0 for m in rows]
    assert scores == sorted(scores, reverse=True)
    with client.app.state.db.read() as session:
        all_ratings = [r.rating for r in session.scalars(select(Review))]
        own = [r.rating for r in session.scalars(select(Review).where(Review.mentor_id == 2))]
    overall = sum(all_ratings) / len(all_ratings)
    expected = (3 * overall + sum(own)) / (3 + len(own))
    card = next(m for m in rows if m["id"] == 2)
    assert abs(card["rating_score"] - expected) < 0.001
    prices = [m["price"] for m in mentors(client, sort="price", topic_id=1)]
    assert prices == sorted(prices)
    assert client.get("/api/public/mentors?sort=unknown").status_code == 422


def test_single_five_star_does_not_beat_many_good_reviews():
    one = score_mentors(Signals(), [Candidate(1, (), (), False, (3 * 4.5 + 5) / 4)])
    many = score_mentors(Signals(), [Candidate(2, (), (), False, (3 * 4.5 + 20 * 4.8) / 23)])
    assert many[0][1] > one[0][1]


# --------------------------------------------------------------- favorites


def test_favorites_flags_filter_and_idempotency(client):
    student = login(client)
    assert client.put("/api/favorites/2", headers=student).status_code == 200
    assert client.put("/api/favorites/2", headers=student).status_code == 200
    assert client.put("/api/favorites/1", headers=student).status_code == 404  # not a mentor
    assert client.put("/api/favorites/2", headers=login(client, 2)).status_code == 422
    # Demo data already has Amina (15) among Alikhan's favorites.
    assert {m["id"] for m in client.get("/api/favorites", headers=student).json()} == {2, 15}
    rows = mentors(client, student, topic_id=1)
    assert next(m for m in rows if m["id"] == 2)["is_favorite"] is True
    assert "В вашем избранном" in next(m for m in rows if m["id"] == 2)["reasons"]
    only = {m["id"] for m in mentors(client, student, topic_id=1, favorites_only="true")}
    assert only == {2, 15}
    assert all(not m["is_favorite"] for m in mentors(client, topic_id=1))  # guest
    assert client.delete("/api/favorites/2", headers=student).status_code == 200
    assert client.delete("/api/favorites/2", headers=student).status_code == 200
    assert [m["id"] for m in client.get("/api/favorites", headers=student).json()] == [15]


def test_suspended_favorite_stays_listed_without_time(client):
    student, team = login(client), login(client, 99)
    client.put("/api/favorites/2", headers=student)
    client.put("/api/admin/mentors/2", headers=team, json={"verified": True, "active": False})
    card = next(m for m in client.get("/api/favorites", headers=student).json() if m["id"] == 2)
    assert card["slots"] == [] and card["reasons"] == ["Сейчас не принимает заявки"]


# ---------------------------------------------------------------- waitlist


def free_start(days=20):
    return (int(time.time()) // 1800 + 1) * 1800 + days * 86400


def wait_for(client, headers, start):
    body = {
        "topic_id": 1,
        "budget": 3000,
        "deadline": start + 3600,
        "earliest": start - 3600,
        "language": "ru",
        "format": "online",
    }
    assert client.post("/api/waitlist", headers=headers, json=body).status_code == 200


def test_new_slot_notifies_matching_waitlist(client):
    student, mentor = login(client), login(client, 2)
    client.put("/api/favorites/2", headers=student)
    start = free_start()
    wait_for(client, student, start)
    assert (
        client.post("/api/mentor/slots", headers=mentor, json={"starts_at": start}).status_code
        == 200
    )
    found = notices(client, 1, "waitlist_match")
    assert len(found) == 1 and found[0].link == "/mentors/2" and "избранном" in found[0].body
    listed = client.get("/api/notifications", headers=student).json()
    assert any(n["link"] == "/mentors/2" for n in listed)
    # A slot outside the requested window does not match.
    client.post("/api/mentor/slots", headers=mentor, json={"starts_at": start + 3 * 86400})
    assert len(notices(client, 1, "waitlist_match")) == 1


def test_suspended_mentor_notifies_nobody(client):
    student, mentor, team = login(client), login(client, 2), login(client, 99)
    client.put("/api/admin/mentors/2", headers=team, json={"verified": True, "active": False})
    start = free_start(21)
    wait_for(client, student, start)
    client.post("/api/mentor/slots", headers=mentor, json={"starts_at": start})
    assert notices(client, 1, "waitlist_match") == []


def test_released_seat_notifies_waitlist(client):
    other, student = login(client, 3), login(client)
    booking = book(client, other)
    with client.app.state.db.read() as session:
        from studymate.models import Slot

        slot = session.get(Slot, booking["slot"]["id"])
        start = slot.starts_at
    wait_for(client, student, start)
    assert notices(client, 1, "waitlist_match") == []
    client.post(f"/api/bookings/{booking['id']}/action", headers=other, json={"action": "cancel"})
    assert len(notices(client, 1, "waitlist_match")) == 1


# --------------------------------------------------------- recommendations


def test_score_mentors_rules():
    signals = Signals(
        weak_topics={1: (1, "SQL JOIN")},
        interests=frozenset({2}),
        interest_names={2: "Python"},
        favorites=frozenset({20}),
        liked_mentors=frozenset({30}),
    )
    ranked = score_mentors(
        signals,
        [
            Candidate(10, (1,), (1,), True, 4.6),  # weak topic + verified + strong rating
            Candidate(20, (3,), (2,), False, None),  # interest + favorite
            Candidate(30, (5,), (3,), False, 3.0),  # liked before
            Candidate(40, (6,), (3,), False, 2.5),  # nothing, weak rating
        ],
    )
    assert [r[0] for r in ranked] == [10, 20, 30, 40]
    assert ranked[0][1] == 3 + 1 + 1.6
    assert "Вы ответили 1/3 по теме «SQL JOIN»" in ranked[0][2]
    assert ranked[1][2] == ["Ваш интерес: Python", "В вашем избранном"]
    assert ranked[3][2] == []
    assert len(score_mentors(Signals(), [Candidate(i, (), (), False, None) for i in range(9)])) == 6


def test_recommendations_explain_weak_quiz_topic(client):
    student = login(client)
    attempt = client.post("/api/quizzes", headers=student, json={"topic_id": 1}).json()
    bank = BANK["sql-join"]
    wrong = [(bank[q["id"]][2] + 1) % len(bank[q["id"]][1]) for q in attempt["questions"]]
    client.post(f"/api/quizzes/{attempt['id']}/submit", headers=student, json={"answers": wrong})
    rows = client.get("/api/recommendations", headers=student).json()
    assert rows and len(rows) <= 6
    assert all(m["id"] != 1 for m in rows)
    top = rows[0]
    assert 1 in top["topic_ids"]
    assert any("по теме «SQL JOIN»" in r for r in top["reasons"])


def test_recommendations_skip_suspended_mentors(client):
    team = login(client, 99)
    client.put("/api/admin/mentors/2", headers=team, json={"verified": True, "active": False})
    rows = client.get("/api/recommendations", headers=login(client, 3)).json()
    assert all(m["id"] != 2 for m in rows)
    assert client.get("/api/recommendations").status_code == 401


def test_booking_still_works_with_new_filters(client):
    student = login(client)
    body = proposal(client, student)
    assert client.post("/api/bookings", headers=student, json={**body, "q": "x"}).status_code == 200
