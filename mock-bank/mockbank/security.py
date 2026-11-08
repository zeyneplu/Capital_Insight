"""Codes, tokens and how we store them.

- Codes and tokens come from `secrets` (cryptographically random), never `random`.
- We store HMAC digests, not the values: a leaked database can't be replayed.
  A 6-digit code has only 1,000,000 values, so a plain hash could be brute-forced;
  HMAC with a server secret can't be, without the secret.
- Comparisons use hmac.compare_digest, which takes the same time whether the first
  or the last character differs (no timing leak).
"""

import hashlib
import hmac
import secrets
import time
import uuid


def now() -> int:
    return int(time.time())


def new_id() -> str:
    return str(uuid.uuid4())


def same(a: str, b: str) -> bool:
    """Constant-time string comparison."""
    return hmac.compare_digest(a.encode(), b.encode())


def new_code() -> str:
    return f"{secrets.randbelow(10**6):06d}"


def new_token() -> str:
    return secrets.token_urlsafe(32)


def digest(secret: str, value: str) -> str:
    return hmac.new(secret.encode(), value.encode(), hashlib.sha256).hexdigest()


def matches(secret: str, value: str, expected: str) -> bool:
    return hmac.compare_digest(digest(secret, value), expected)
