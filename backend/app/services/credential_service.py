"""Envelope-free, server-side credential encryption. Tokens and cookies are never persisted."""
import os
from cryptography.fernet import Fernet, InvalidToken

ENCRYPTION_VERSION = 1


def _fernet() -> Fernet:
    key = os.getenv("CREDENTIAL_ENCRYPTION_KEY")
    if not key:
        raise RuntimeError("CREDENTIAL_ENCRYPTION_KEY must be configured before storing portal credentials")
    return Fernet(key.encode())


def encrypt_password(password: str) -> str:
    return _fernet().encrypt(password.encode()).decode()


def decrypt_password(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise RuntimeError("Stored portal credential cannot be decrypted") from exc
