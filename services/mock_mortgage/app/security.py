"""Small HMAC-signed, bank-scoped mock tokens (not JWTs or real bank login)."""
import base64
import hashlib
import hmac
import json
import secrets
import time


def digest(secret: str, value: str) -> str:
    return hmac.new(secret.encode(), value.encode(), hashlib.sha256).hexdigest()


def issue_token(secret: str, bank: str, customer: str, ttl: int) -> str:
    payload = {"sub": customer, "aud": bank, "exp": int(time.time())+ttl, "nonce": secrets.token_hex(8)}
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return encoded+"."+digest(secret, encoded)


def token_customer(secret: str, bank: str, token: str) -> str:
    try:
        payload, signature = token.split(".")
        if not hmac.compare_digest(digest(secret, payload), signature):
            raise ValueError()
        data = json.loads(base64.urlsafe_b64decode(payload+"="*(-len(payload)%4)))
        if data["aud"] != bank or data["exp"] <= time.time() or not isinstance(data["sub"], str):
            raise ValueError()
        return data["sub"]
    except (ValueError, KeyError, TypeError, UnicodeError) as exc:
        raise ValueError("Invalid or expired access token") from exc
