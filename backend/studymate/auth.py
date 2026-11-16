"""Passwords, session tokens, local reset codes and login rate limiting."""

import hashlib
import hmac
import re
import secrets
import threading
import time
from collections import deque

from sqlalchemy import delete
from sqlalchemy.orm import Session

from .models import PasswordResetCode, SessionToken

ITERATIONS = 600_000
SESSION_SECONDS = 12 * 3600
RESET_CODE_SECONDS = 30 * 60
EMAIL_RE = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")


def normalize_email(email: str) -> str | None:
    email = email.strip().lower()
    return email if EMAIL_RE.fullmatch(email) else None


def password_hash(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, stored: str | None) -> bool:
    try:
        algorithm, rounds, salt, expected = (stored or "").split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(rounds))
        return hmac.compare_digest(expected, digest.hex())
    except (ValueError, TypeError):
        return False


# A valid hash for timing-equalisation when the account does not exist.
_DUMMY_HASH = password_hash(secrets.token_hex(8))


def burn_password_check(password: str) -> None:
    verify_password(password, _DUMMY_HASH)


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def issue_token(session: Session, user_id: int) -> str:
    token = secrets.token_urlsafe(40)
    session.add(
        SessionToken(
            token_hash=sha256(token),
            user_id=user_id,
            expires_at=int(time.time()) + SESSION_SECONDS,
        )
    )
    return token


def revoke_sessions(session: Session, user_id: int, keep_token_hash: str | None = None) -> None:
    query = delete(SessionToken).where(SessionToken.user_id == user_id)
    if keep_token_hash:
        query = query.where(SessionToken.token_hash != keep_token_hash)
    session.execute(query)


def issue_reset_code(session: Session, user_id: int) -> str:
    """Create a one-time code; earlier unused codes of the user stop working."""
    session.execute(delete(PasswordResetCode).where(PasswordResetCode.user_id == user_id))
    code = "-".join(secrets.token_hex(2).upper() for _ in range(3))
    session.add(
        PasswordResetCode(
            code_hash=sha256(code.replace("-", "")),
            user_id=user_id,
            expires_at=int(time.time()) + RESET_CODE_SECONDS,
        )
    )
    return code


def reset_code_hash(code: str) -> str:
    return sha256(code.strip().upper().replace("-", "").replace(" ", ""))


class RateLimiter:
    """In-process sliding-window limiter.

    Two windows: per (client, email) so one person's typos do not lock out
    everybody behind the same address (on 127.0.0.1 every visitor shares it),
    and a looser per-client window against spraying many emails.
    """

    def __init__(self, per_account=10, per_client=60, window=60.0, max_keys=10_000):
        self.per_account, self.per_client = per_account, per_client
        self.window, self.max_keys = window, max_keys
        self._hits: dict[tuple, deque] = {}
        self._lock = threading.Lock()

    def _prune(self, cutoff):
        for key in [k for k, q in self._hits.items() if not q or q[-1] < cutoff]:
            del self._hits[key]

    def hit(self, client: str, email: str) -> bool:
        """Register an attempt; return False when the caller must wait."""
        now = time.monotonic()
        cutoff = now - self.window
        with self._lock:
            if len(self._hits) > self.max_keys:
                self._prune(cutoff)
            queues = []
            for key, limit in (
                (("account", client, email), self.per_account),
                (("client", client), self.per_client),
            ):
                queue = self._hits.setdefault(key, deque())
                while queue and queue[0] < cutoff:
                    queue.popleft()
                if len(queue) >= limit:
                    return False
                queues.append(queue)
            for queue in queues:
                queue.append(now)
            return True

    def __len__(self):
        return len(self._hits)
