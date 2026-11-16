"""FastAPI dependencies shared by the routers.

* ``read_session`` — snapshot without SQLite's write lock (GET endpoints).
  Overdue pending bookings are expired in a short write transaction first,
  so reads still see current statuses.
* ``write_session`` — ``BEGIN IMMEDIATE`` transaction for every change.

``read_user``/``write_user`` resolve the bearer token through the matching
session, so a route and its user share one transaction.
"""

from collections.abc import Iterator

from fastapi import Depends, Header, Request
from sqlalchemy import delete
from sqlalchemy.orm import Session

from .auth import sha256
from .config import Settings
from .db import Database
from .models import SessionToken, User
from .service import expire_pending, fail, get, has_overdue_pending, now


def get_database(request: Request) -> Database:
    return request.app.state.db


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def read_session(db: Database = Depends(get_database)) -> Iterator[Session]:
    with db.read() as probe:
        overdue = has_overdue_pending(probe)
    if overdue:
        with db.write() as session:
            expire_pending(session)
    with db.read() as session:
        yield session


def write_session(db: Database = Depends(get_database)) -> Iterator[Session]:
    with db.write() as session:
        yield session


def bearer_hash(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer ") or len(authorization) < 20:
        fail(401, "Войдите в StudyMate")
    return sha256(authorization[7:])


def _resolve_user(session: Session, db: Database, authorization: str | None) -> User:
    token_hash = bearer_hash(authorization)
    token = session.get(SessionToken, token_hash)
    if not token:
        fail(401, "Войдите заново: сессия завершилась")
    if token.expires_at <= now():
        # Drop the expired token right away instead of waiting for the worker.
        with db.write() as cleanup:
            cleanup.execute(delete(SessionToken).where(SessionToken.token_hash == token_hash))
        fail(401, "Войдите заново: сессия завершилась")
    return get(session, User, token.user_id)


def read_user(
    authorization: str | None = Header(default=None),
    s: Session = Depends(read_session),
    db: Database = Depends(get_database),
) -> User:
    return _resolve_user(s, db, authorization)


def write_user(
    authorization: str | None = Header(default=None),
    s: Session = Depends(write_session),
) -> User:
    token_hash = bearer_hash(authorization)
    token = s.get(SessionToken, token_hash)
    if not token or token.expires_at <= now():
        if token:
            s.delete(token)
            # Commit the cleanup: the 401 below rolls back the rest.
            s.commit()
        fail(401, "Войдите заново: сессия завершилась")
    return get(s, User, token.user_id)


def read_admin(user: User = Depends(read_user)) -> User:
    if not user.is_admin:
        fail(403, "Доступ только для команды StudyMate")
    return user


def write_admin(user: User = Depends(write_user)) -> User:
    if not user.is_admin:
        fail(403, "Доступ только для команды StudyMate")
    return user
