import pytest
from fastapi.testclient import TestClient
from studymate.api import create_app
from studymate.config import Settings


@pytest.fixture
def client(tmp_path):
    app = create_app(Settings(database=str(tmp_path / "test-demo.sqlite3"), worker_enabled=False))
    with TestClient(app) as current:
        yield current


def login(client, uid=1):
    response = client.post("/api/auth/demo", json={"user_id": uid})
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["token"]}


def proposal(client, headers, mentor_id=2, key="test-request-0001"):
    import time

    deadline = int(time.time()) + 5 * 86400
    mentors = client.get(
        f"/api/mentors?topic_id=1&budget=3000&deadline={deadline}", headers=headers
    ).json()
    mentor = next(m for m in mentors if m["id"] == mentor_id)
    return {
        "slot_id": mentor["slots"][0]["id"],
        "topic_id": 1,
        "deadline": deadline,
        "budget": 3000,
        "language": "ru",
        "format": "online",
        "description": "Хочу разобраться в LEFT JOIN",
        "request_key": key,
    }


def book(client, headers):
    response = client.post("/api/bookings", json=proposal(client, headers), headers=headers)
    assert response.status_code == 200, response.text
    return response.json()
