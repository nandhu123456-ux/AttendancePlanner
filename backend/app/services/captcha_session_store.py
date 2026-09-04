import secrets
import time
from threading import Timer

# Temporary CAPTCHA sessions: token -> {session, username, password, form_fields, created_at}
_captcha_sessions = {}
SESSION_TIMEOUT = 300  # 5 minutes


def create_captcha_session(session, username: str, password: str, form_fields: dict) -> str:
    """Store temporary portal session for CAPTCHA flow. Returns a short-lived token."""
    cleanup_expired()
    token = secrets.token_urlsafe(32)
    _captcha_sessions[token] = {
        "session": session,
        "username": username,
        "password": password,
        "form_fields": form_fields,
        "created_at": time.time(),
    }
    return token


def get_captcha_session(token: str):
    """Retrieve and validate temporary CAPTCHA session."""
    entry = _captcha_sessions.get(token)
    if entry is None:
        return None
    if time.time() - entry["created_at"] > SESSION_TIMEOUT:
        del _captcha_sessions[token]
        return None
    return entry


def remove_captcha_session(token: str):
    """Remove a CAPTCHA session after use or expiration."""
    _captcha_sessions.pop(token, None)


def cleanup_expired():
    """Remove expired sessions to prevent memory leaks."""
    now = time.time()
    expired = [t for t, e in _captcha_sessions.items() if now - e["created_at"] > SESSION_TIMEOUT]
    for t in expired:
        del _captcha_sessions[t]