"""Password hashing (Argon2 via pwdlib) and random tokens stored only as hashes"""

import hashlib
import hmac
import secrets
from functools import cache

from pwdlib import PasswordHash

MIN_PASSWORD_LENGTH = 10
# Long enough for passphrases, short enough that hashing can't be used to tie up the server
MAX_PASSWORD_LENGTH = 256

_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _hasher.verify(password, password_hash)


@cache
def _dummy_hash() -> str:
    return hash_password(secrets.token_urlsafe(16))


def verify_dummy_password(password: str) -> None:
    """Spend the same time as a real check when the username is unknown, so login timing
    doesn't reveal which usernames have accounts"""
    verify_password(password, _dummy_hash())


def new_token(num_bytes: int = 32) -> str:
    """A random URL-safe token (32 bytes = 256 bits by default)"""
    return secrets.token_urlsafe(num_bytes)


def hash_token(token: str) -> str:
    """SHA-256 of a session token or invite code, which is all the database stores"""
    return hashlib.sha256(token.encode()).hexdigest()


def tokens_match(given: str | None, expected: str) -> bool:
    return given is not None and hmac.compare_digest(given.encode(), expected.encode())
