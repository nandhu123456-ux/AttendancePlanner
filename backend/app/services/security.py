import os
from datetime import datetime, timedelta, timezone

from fastapi import Header, HTTPException, status
from jose import JWTError, jwt
from dotenv import load_dotenv

from app.config.database import get_database

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = int(os.getenv("TOKEN_EXPIRE_HOURS", "8"))


def _secret_key():
    if not SECRET_KEY:
        raise RuntimeError("SECRET_KEY must be configured in the environment")
    return SECRET_KEY


def create_access_token(student_id: str) -> str:
    issued_at = datetime.now(timezone.utc)
    expires_at = issued_at + timedelta(hours=TOKEN_EXPIRE_HOURS)
    return jwt.encode(
        {"student_id": student_id, "exp": expires_at, "iat": int(issued_at.timestamp())},
        _secret_key(),
        algorithm=ALGORITHM,
    )


def _invalidated_before(student_id: str) -> int | None:
    """Epoch seconds before which every TRACK_75 token for this student is rejected.

    Used to invalidate still-valid JWTs when the GITAM portal session can no
    longer be refreshed (the client must then log in again). Tokens issued
    before the iat claim existed are treated as issued at epoch 0.
    """
    doc = get_database().users.find_one({"student_id": student_id}, {"token_invalidated_at": 1})
    value = (doc or {}).get("token_invalidated_at")
    return int(value) if value else None


def verify_token(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or malformed token")
    try:
        payload = jwt.decode(authorization.removeprefix("Bearer "), _secret_key(), algorithms=[ALGORITHM])
        if not payload.get("student_id"):
            raise JWTError("Missing student identity")
        invalidated_before = _invalidated_before(payload["student_id"])
        if invalidated_before is not None and int(payload.get("iat", 0)) < invalidated_before:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired. Please log in again.",
            )
        return payload
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token is invalid or expired") from exc


def invalidate_user_tokens(student_id: str) -> None:
    """Reject every TRACK_75 token issued so far for this student.

    Called when the stored portal credentials can no longer refresh the GITAM
    session, so a valid JWT can never keep serving stale attendance as current.
    The next request from that client receives 401 and must log in again.
    """
    get_database().users.update_one(
        {"student_id": student_id},
        {"$set": {"token_invalidated_at": int(datetime.now(timezone.utc).timestamp())}},
    )

