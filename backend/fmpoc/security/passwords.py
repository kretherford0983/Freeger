"""Argon2id password hashing and password policy (BR-089)."""
from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_ph = PasswordHasher()  # argon2id with library-recommended parameters
_DUMMY = _ph.hash("dummy-password-for-timing-equalisation")

MIN_LENGTH = 12
MAX_LENGTH = 128


def hash_password(pw: str) -> str:
    return _ph.hash(pw)


def verify_password(pw_hash: str | None, pw: str) -> bool:
    try:
        return _ph.verify(pw_hash or _DUMMY, pw) and pw_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def policy_errors(pw: str, username: str | None = None) -> list[str]:
    errs: list[str] = []
    if not isinstance(pw, str):
        return ["Password is required."]
    if len(pw) < MIN_LENGTH:
        errs.append(f"Password must be at least {MIN_LENGTH} characters.")
    if len(pw) > MAX_LENGTH:
        errs.append(f"Password must be at most {MAX_LENGTH} characters.")
    if not any(c.isalpha() for c in pw) or not any(c.isdigit() for c in pw):
        errs.append("Password must contain at least one letter and one digit.")
    if username and pw.strip().lower() == username.strip().lower():
        errs.append("Password must not equal the username.")
    return errs
