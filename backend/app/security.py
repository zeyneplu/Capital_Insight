"""Password hashing, opaque session tokens, and encrypted provider credentials."""

import base64
import hashlib
import hmac
import os
import secrets

from cryptography.fernet import Fernet

from .config import BACKEND_ROOT, Settings


def make_cipher(settings: Settings) -> Fernet:
    if settings.encryption_key is not None:
        key = settings.encryption_key.get_secret_value().encode("ascii")
    elif settings.environment == "production":
        raise ValueError("ENCRYPTION_KEY is required in production")
    else:
        # This stable, ignored file preserves local connections across restarts.
        directory = BACKEND_ROOT / "data"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "encryption.key"
        try:
            with path.open("xb") as output:
                key = Fernet.generate_key()
                output.write(key)
            os.chmod(path, 0o600)
        except FileExistsError:
            key = path.read_bytes().strip()
    try:
        return Fernet(key)
    except (ValueError, TypeError) as exc:
        raise ValueError("ENCRYPTION_KEY must be a valid Fernet key") from exc


def encrypt_token(cipher: Fernet, token: str) -> str:
    return cipher.encrypt(token.encode("utf-8")).decode("ascii")


def decrypt_token(cipher: Fernet, encrypted_token: str) -> str:
    return cipher.decrypt(encrypted_token.encode("ascii")).decode("utf-8")


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=16384, r=8, p=1)
    return "$".join(
        ("scrypt", "16384", "8", "1", base64.b64encode(salt).decode("ascii"),
         base64.b64encode(derived).decode("ascii"))
    )


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, n, r, p, salt, expected = stored_hash.split("$")
        # Only the supported format may choose scrypt's resource requirements.
        if (algorithm, n, r, p) != ("scrypt", "16384", "8", "1"):
            return False
        derived = hashlib.scrypt(
            password.encode("utf-8"), salt=base64.b64decode(salt, validate=True),
            n=16384, r=8, p=1,
        )
        return hmac.compare_digest(derived, base64.b64decode(expected, validate=True))
    except (ValueError, TypeError):
        return False
