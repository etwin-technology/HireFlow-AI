"""Lightweight security helpers: hashing, token generation, optional encryption.

These primitives are used for:
- generating unique hash IDs for jobs (deduplication)
- optionally encrypting sensitive on-disk configuration (proxy credentials)
- generating one-shot tokens for the local API
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.core.config import settings


# ---------------------------------------------------------------------------
# Hashing helpers
# ---------------------------------------------------------------------------
def stable_hash(*parts: str, length: int = 32) -> str:
    """Return a deterministic SHA-256 hex hash of the given string parts.

    Used by the deduplication service to compute a job's unique identifier.
    The output is lowercase-only and trimmed to ``length`` characters.
    """
    normalized = "||".join((p or "").strip().lower() for p in parts)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return digest[:length]


def quick_hash(value: str) -> str:
    """Return a short (12 char) hash of ``value`` — used for filenames etc."""
    return hashlib.md5(value.encode("utf-8")).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------
def generate_token(num_bytes: int = 32) -> str:
    """Return a cryptographically-random URL-safe token."""
    return secrets.token_urlsafe(num_bytes)


# ---------------------------------------------------------------------------
# Symmetric encryption (Fernet, AES-128-CBC under the hood)
# ---------------------------------------------------------------------------
def _derive_fernet_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=200_000,
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))


class Cipher:
    """Convenience wrapper around Fernet with key derivation from settings."""

    def __init__(
        self,
        password: Optional[str] = None,
        salt: Optional[str] = None,
    ) -> None:
        pwd = password or settings.secret_key
        salt_value = (salt or settings.encryption_salt).encode("utf-8")
        self._fernet = Fernet(_derive_fernet_key(pwd, salt_value))

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")

    def decrypt(self, token: str) -> str:
        try:
            return self._fernet.decrypt(token.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise ValueError("Invalid or tampered ciphertext") from exc
