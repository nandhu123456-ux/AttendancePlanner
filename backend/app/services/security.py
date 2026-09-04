import os
from datetime import datetime, timedelta, timezone

from fastapi import Header, HTTPException, status
from jose import JWTError, jwt
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = int(os.getenv("TOKEN_EXPIRE_HOURS", "8"))


def _secret_key():
    if not SECRET_KEY:
        raise RuntimeError("SECRET_KEY must be configured in the environment")
    return SECRET_KEY


def create_access_token(student_id: str) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS)
    return jwt.encode({"student_id": student_id, "exp": expires_at}, _secret_key(), algorithm=ALGORITHM)


def verify_token(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or malformed token")
    try:
        payload = jwt.decode(authorization.removeprefix("Bearer "), _secret_key(), algorithms=[ALGORITHM])
        if not payload.get("student_id"):
            raise JWTError("Missing student identity")
        return payload
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token is invalid or expired") from exc
