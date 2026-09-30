"""Authentication, sessions, password changes and failed-login rate limiting."""
from __future__ import annotations

import datetime as dt
import secrets
import threading
import time
from collections import defaultdict, deque

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .. import audit
from ..deps import hash_token
from ..errors import AppError
from ..models import AuthSession, User, utcnow
from ..security.passwords import hash_password, policy_errors, verify_password
from . import mfa


class LoginRateLimiter:
    """Basic in-process failed-login limiter keyed by username and client IP."""

    def __init__(self, max_failures: int, window_seconds: int):
        self.max, self.window = max_failures, window_seconds
        self._fails: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float):
        q = self._fails[key]
        while q and q[0] < now - self.window:
            q.popleft()
        return q

    def blocked(self, *keys: str) -> bool:
        now = time.monotonic()
        with self._lock:
            return any(len(self._prune(k, now)) >= self.max for k in keys)

    def fail(self, *keys: str) -> None:
        now = time.monotonic()
        with self._lock:
            for k in keys:
                self._prune(k, now).append(now)

    def reset(self, *keys: str) -> None:
        with self._lock:
            for k in keys:
                self._fails.pop(k, None)


def create_session(db: Session, settings, user: User, mfa_pending: str | None = None) -> tuple[str, AuthSession]:
    token = secrets.token_urlsafe(32)
    now = utcnow()
    life = (dt.timedelta(minutes=mfa.PENDING_MINUTES) if mfa_pending
            else dt.timedelta(hours=settings.session_absolute_hours))
    sess = AuthSession(
        token_hash=hash_token(token), user_id=user.id, csrf_token=secrets.token_urlsafe(32),
        created_at=now, last_seen_at=now, expires_at=now + life, mfa_pending=mfa_pending,
    )
    db.add(sess)
    db.flush()
    return token, sess


def revoke_user_sessions(db: Session, user_id: int, except_session_id: int | None = None) -> int:
    stmt = update(AuthSession).where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
    if except_session_id is not None:
        stmt = stmt.where(AuthSession.id != except_session_id)
    return db.execute(stmt.values(revoked_at=utcnow())).rowcount or 0


def mfa_state(db: Session, settings, user: User, trusted_token: str | None) -> tuple[str | None, str]:
    """v1.4.1 CR-018: (pending state for the new session, how MFA was satisfied)."""
    if mfa.enabled(db, user):
        if mfa.check_trusted(db, user, trusted_token):
            return None, "trusted_browser"
        return "VERIFY", "pending"
    if mfa.required(settings):
        return "ENROLL", "pending"
    return None, "not_enabled"


def login(db: Session, settings, limiter: LoginRateLimiter, ctx, username: str, password: str, prior_token: str | None,
          trusted_token: str | None = None):
    uname = (username or "").strip().lower()
    keys = (f"u:{uname}", f"ip:{ctx.ip}")
    if limiter.blocked(*keys):
        audit.record(db, ctx, "LOGIN_RATE_LIMITED", "user", None, None, {"username": uname[:64]}, category="SECURITY")
        db.commit()
        raise AppError(429, "RATE_LIMITED", "Too many failed sign-in attempts. Try again later.")
    user = db.scalar(select(User).where(User.username_normalized == uname))
    ok = verify_password(user.password_hash if user else None, password or "")
    if not ok or user is None or not user.active:
        limiter.fail(*keys)
        audit.record(db, ctx, "LOGIN_FAILED", "user", user.id if user else None, None,
                     {"username": uname[:64]}, category="SECURITY")
        db.commit()
        raise AppError(401, "INVALID_CREDENTIALS", "Invalid username or password.")
    limiter.reset(*keys)
    # Session rotation: any session presented with the login request is revoked.
    if prior_token:
        db.execute(update(AuthSession).where(AuthSession.token_hash == hash_token(prior_token))
                   .values(revoked_at=utcnow()))
    pending, how = mfa_state(db, settings, user, trusted_token)
    token, sess = create_session(db, settings, user, pending)
    ctx.user, ctx.workspace_id = user, user.workspace_id
    audit.record(db, ctx, "LOGIN" if not pending else "LOGIN_PASSWORD_ACCEPTED", "user", user.id, None,
                 {"session_ref": sess.id, "mfa": how if not pending else pending.lower()}, category="SECURITY")
    db.commit()
    return user, token, sess


def logout(db: Session, ctx) -> None:
    if ctx.session is not None:
        ctx.session.revoked_at = utcnow()
        audit.record(db, ctx, "LOGOUT", "user", ctx.user.id, None, None, category="SECURITY")
        db.commit()


def change_own_password(db: Session, ctx, current: str, new: str, confirm: str) -> None:
    """BR-SEC-SELF-001/002."""
    user = ctx.user
    if not verify_password(user.password_hash, current or ""):
        audit.record(db, ctx, "PASSWORD_CHANGE_FAILED", "user", user.id, None, {"reason": "incorrect_current_password"},
                     category="SECURITY")
        db.commit()
        raise AppError(400, "INCORRECT_PASSWORD", "The current password is incorrect.")
    if new != confirm:
        raise AppError(422, "VALIDATION_ERROR", "New password and confirmation do not match.",
                       errors=[{"field": "new_password_confirmation", "message": "Passwords do not match."}])
    errs = policy_errors(new, user.username)
    if new == current:
        errs.append("New password must differ from the current password.")
    if errs:
        raise AppError(422, "PASSWORD_POLICY", " ".join(errs),
                       errors=[{"field": "new_password", "message": e} for e in errs])
    user.password_hash = hash_password(new)
    user.password_changed_at = utcnow()
    revoked = revoke_user_sessions(db, user.id, except_session_id=ctx.session.id)
    trusted = mfa.revoke_trusted(db, user.id)  # v1.4.1 CR-018
    audit.record(db, ctx, "PASSWORD_CHANGED", "user", user.id, None,
                 {"self_service": True, "other_sessions_revoked": revoked, "trusted_browsers_revoked": trusted},
                 category="SECURITY")
    db.commit()


def complete_mfa(db: Session, settings, ctx, how: str) -> tuple[str, AuthSession]:
    """Replaces the MFA-pending session with a full session (new token - session rotation on privilege change)."""
    old = ctx.session
    old.revoked_at = utcnow()
    token, sess = create_session(db, settings, ctx.user, None)
    audit.record(db, ctx, "LOGIN", "user", ctx.user.id, None, {"session_ref": sess.id, "mfa": how},
                 category="SECURITY")
    ctx.session, ctx.mfa_pending = sess, None
    return token, sess
