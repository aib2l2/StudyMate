"""Accounts: demo entry, registration, login, logout, passwords."""

from fastapi import Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth import (
    RateLimiter,
    burn_password_check,
    issue_token,
    normalize_email,
    password_hash,
    reset_code_hash,
    revoke_sessions,
    sha256,
    verify_password,
)
from ..config import Settings
from ..db import Database
from ..deps import get_database, get_settings, read_user, write_session
from ..events import end_sessions
from ..models import PasswordResetCode, SessionToken, User
from ..schemas import (
    AuthOut,
    Credentials,
    DemoLogin,
    Ok,
    PasswordChange,
    PasswordReset,
    Registration,
)
from ..service import fail, get, now, profile
from . import Router

router = Router(prefix="/api/auth", tags=["auth"])


def limiter(request: Request) -> RateLimiter:
    return request.app.state.rate_limiter


def checked_email(request: Request, email: str) -> str:
    """Rate-limit by (client, email) and validate the address."""
    normalized = normalize_email(email)
    client = request.client.host if request.client else "local"
    if not limiter(request).hit(client, normalized or email.strip().lower()):
        fail(429, "Слишком много попыток. Попробуйте через минуту")
    if not normalized:
        fail(422, "Введите корректный email")
    return normalized


def signed_in(db: Database, user_id: int) -> dict:
    with db.write() as s:
        user = get(s, User, user_id)
        return {"token": issue_token(s, user.id), "user": profile(s, user)}


@router.post("/demo", response_model=AuthOut)
def demo_login(
    data: DemoLogin,
    s: Session = Depends(write_session),
    settings: Settings = Depends(get_settings),
):
    if settings.mode != "demo":
        fail(404, "Маршрут недоступен")
    user = get(s, User, data.user_id)
    return {"token": issue_token(s, user.id), "user": profile(s, user)}


@router.post("/register", response_model=AuthOut)
def register(data: Registration, request: Request, db: Database = Depends(get_database)):
    email = checked_email(request, data.email)
    name = data.name.strip()
    if not name:
        fail(422, "Введите имя")
    # PBKDF2 is slow on purpose; compute it before taking the write lock.
    hashed = password_hash(data.password)
    try:
        with db.write() as s:
            if s.scalar(select(User.id).where(User.email == email)):
                fail(409, "Этот email уже зарегистрирован")
            user = User(
                name=name,
                email=email,
                password_hash=hashed,
                course=data.course,
                registered=True,
                is_admin=False,
            )
            s.add(user)
            s.flush()
            return {"token": issue_token(s, user.id), "user": profile(s, user)}
    except IntegrityError:
        fail(409, "Этот email уже зарегистрирован")


@router.post("/login", response_model=AuthOut)
def login(data: Credentials, request: Request, db: Database = Depends(get_database)):
    email = checked_email(request, data.email)
    with db.read() as s:
        row = s.execute(select(User.id, User.password_hash).where(User.email == email)).first()
    if row is None:
        burn_password_check(data.password)  # keep the missing-user branch equally slow
        fail(401, "Email или пароль не совпадают")
    if not verify_password(data.password, row.password_hash):
        fail(401, "Email или пароль не совпадают")
    return signed_in(db, row.id)


@router.post("/logout", response_model=Ok)
def logout(
    authorization: str | None = Header(default=None),
    user: User = Depends(read_user),
    db: Database = Depends(get_database),
):
    with db.write() as s:
        token = s.get(SessionToken, sha256(authorization[7:]))
        if token:
            s.delete(token)
            end_sessions(s, user.id, only_token=token.token_hash)
    return {"ok": True}


@router.post("/logout-all", response_model=Ok)
def logout_all(user: User = Depends(read_user), db: Database = Depends(get_database)):
    with db.write() as s:
        revoke_sessions(s, user.id)
        end_sessions(s, user.id)
    return {"ok": True, "message": "Вы вышли на всех устройствах"}


@router.post("/password", response_model=Ok)
def change_password(
    data: PasswordChange,
    request: Request,
    authorization: str | None = Header(default=None),
    user: User = Depends(read_user),
    db: Database = Depends(get_database),
):
    client = request.client.host if request.client else "local"
    if not limiter(request).hit(client, f"password:{user.id}"):
        fail(429, "Слишком много попыток. Попробуйте через минуту")
    if not user.password_hash:
        fail(409, "У демонстрационного аккаунта нет пароля")
    if not verify_password(data.current_password, user.password_hash):
        fail(403, "Текущий пароль не совпадает")
    if data.current_password == data.new_password:
        fail(422, "Новый пароль должен отличаться от текущего")
    hashed = password_hash(data.new_password)
    with db.write() as s:
        get(s, User, user.id).password_hash = hashed
        current = sha256(authorization[7:])
        revoke_sessions(s, user.id, keep_token_hash=current)
        end_sessions(s, user.id, keep_token=current)
    return {"ok": True, "message": "Пароль изменён. Остальные сессии завершены"}


@router.post("/reset", response_model=AuthOut)
def reset_password(
    data: PasswordReset,
    request: Request,
    db: Database = Depends(get_database),
):
    email = checked_email(request, data.email)
    code_hash = reset_code_hash(data.code)
    hashed = password_hash(data.new_password)
    with db.write() as s:
        user = s.scalar(select(User).where(User.email == email))
        code = s.get(PasswordResetCode, code_hash)
        if (
            not user
            or not code
            or code.user_id != user.id
            or code.used_at is not None
            or code.expires_at <= now()
        ):
            fail(400, "Код не подходит или устарел. Попросите новый у владельца сайта")
        code.used_at = now()
        user.password_hash = hashed
        revoke_sessions(s, user.id)
        end_sessions(s, user.id)
        user_id = user.id
    return signed_in(db, user_id)
