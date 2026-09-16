import os
import threading
import time
from datetime import datetime, timedelta, timezone
import logging

from app.config.database import get_database
from .credential_service import decrypt_password
from .gitam_portal import InvalidCredentials, PortalData, PortalError, attempt_relogin, fetch_current_data
from .security import invalidate_user_tokens
from .session_store import get_session, remove_session, save_session

logger = logging.getLogger(__name__)

def _now(): return datetime.now(timezone.utc)

# How long MongoDB data is trusted as current without contacting the portal.
FRESHNESS_MINUTES = float(os.getenv("SYNC_FRESHNESS_MINUTES", "15"))
# Minimum spacing between silent portal re-login attempts per student, so a
# portal that enforces its CAPTCHA is never hammered with failed logins.
REAUTH_COOLDOWN_SECONDS = float(os.getenv("REAUTH_COOLDOWN_SECONDS", "120"))

_locks_guard = threading.Lock()
_student_locks: dict[str, threading.Lock] = {}
_last_reauth_attempt: dict[str, float] = {}


def _lock_for(student_id: str) -> threading.Lock:
    with _locks_guard:
        lock = _student_locks.get(student_id)
        if lock is None:
            lock = threading.Lock()
            _student_locks[student_id] = lock
        return lock


def _as_aware(value):
    """pymongo returns naive UTC datetimes; make comparisons tz-safe."""
    if isinstance(value, datetime) and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _is_fresh(last_sync_at, now=None) -> bool:
    last_sync_at = _as_aware(last_sync_at)
    if not isinstance(last_sync_at, datetime):
        return False
    return (_now() if now is None else now) - last_sync_at <= timedelta(minutes=FRESHNESS_MINUTES)


def _rebuild_plan(student_id: str) -> None:
    """Best-effort planner rebuild so stored snapshots match fresh attendance."""
    try:
        from .plan_service import build_plan_from_database

        build_plan_from_database(student_id)
    except Exception as exc:
        logger.warning("FRESHNESS: planner rebuild deferred for user=%s: %s", student_id, exc)


def _sync_from_session(student_id: str, session) -> None:
    data = fetch_current_data(session)
    sync_portal_data(student_id, data)
    _rebuild_plan(student_id)


def ensure_fresh_portal_data(student_id: str) -> dict:
    """Make sure attendance data is fresh before it is served as current.

    Returns {"status": "fresh"|"resynced"|"unreachable"|"invalidated", "reason": str|None}:

    - fresh:       MongoDB data is within the freshness window; nothing to do.
    - resynced:    fresh portal data was fetched and committed to MongoDB.
    - unreachable: the portal could not be reached (transient). Stored data
                   must be served flagged as stale, never as current.
    - invalidated: the GITAM session expired and silent re-authentication with
                   the stored encrypted credentials failed definitively. All
                   TRACK_75 tokens for the student have been invalidated; the
                   client must log in again.
    """
    db = get_database()
    projection = {"lastSyncAt": 1, "encryptedPassword": 1}
    account = db.users.find_one({"student_id": student_id}, projection) or {}
    if _is_fresh(account.get("lastSyncAt")):
        return {"status": "fresh", "reason": None}

    with _lock_for(student_id):
        # Re-check under the lock: a concurrent request may have just synced.
        account = db.users.find_one({"student_id": student_id}, projection) or {}
        if _is_fresh(account.get("lastSyncAt")):
            return {"status": "fresh", "reason": None}

        # 1) Reuse the live in-memory portal session when one exists. This
        #    covers the common case: GLearn SSO expired but the GStudent
        #    session is still alive (the fetch re-mints the SSO silently).
        session = get_session(student_id)
        if session is not None:
            try:
                _sync_from_session(student_id, session)
                return {"status": "resynced", "reason": None}
            except Exception:
                # The session is dead or the portal hiccuped; drop it and
                # fall through to stored-credential re-authentication.
                remove_session(student_id)

        # 2) Silent re-login with the stored encrypted credentials - the same
        #    credentials the existing login flow encrypts and stores.
        encrypted = account.get("encryptedPassword")
        if not encrypted:
            invalidate_user_tokens(student_id)
            return {"status": "invalidated", "reason": "No stored portal credentials; login required"}

        now_monotonic = time.monotonic()
        if now_monotonic - _last_reauth_attempt.get(student_id, 0.0) < REAUTH_COOLDOWN_SECONDS:
            # A re-login was attempted moments ago; do not hammer the portal.
            return {"status": "unreachable", "reason": "Portal re-authentication is cooling down"}
        _last_reauth_attempt[student_id] = now_monotonic

        try:
            password = decrypt_password(encrypted)
        except RuntimeError as exc:
            invalidate_user_tokens(student_id)
            return {"status": "invalidated", "reason": f"Stored portal credentials cannot be decrypted; login required ({exc})"}

        try:
            session = attempt_relogin(student_id, password)
        except InvalidCredentials:
            # The portal enforced its CAPTCHA or rejected the stored password:
            # fresh data can no longer be produced for this TRACK_75 session.
            logger.info("FRESHNESS: re-auth failed for user=%s; invalidating session", student_id)
            invalidate_user_tokens(student_id)
            return {"status": "invalidated", "reason": "GITAM session expired and could not be refreshed; login required"}
        except PortalError as exc:
            # Transient portal/network problem - do not log the user out.
            return {"status": "unreachable", "reason": str(exc)}

        save_session(student_id, session)
        _sync_from_session(student_id, session)
        return {"status": "resynced", "reason": None}



def _sync_collection(collection, student_id, items, identity_fields):
    current = {tuple(doc.get(field) for field in identity_fields): doc for doc in collection.find({"student_id": student_id})}
    changed = 0
    desired_keys = set()
    for item in items:
        key = tuple(item[field] for field in identity_fields); desired_keys.add(key)
        existing = current.get(key)
        comparable = {**item, "student_id": student_id}
        if not existing or any(existing.get(k) != v for k, v in comparable.items()):
            collection.update_one({"student_id": student_id, **dict(zip(identity_fields, key))}, {"$set": {**comparable, "updatedAt": _now()}}, upsert=True)
            changed += 1
    for key in set(current) - desired_keys:
        collection.delete_one({"_id": current[key]["_id"]}); changed += 1
    return changed


def sync_portal_data(student_id: str, data: PortalData) -> dict:
    """Each stage commits independently so a future partial failure cannot erase data."""
    db = get_database(); status = {"attendance": "failed", "timetable": "failed", "subjectsChanged": 0, "timetableChanged": 0}
    if data.subjects is not None:
        status["subjectsChanged"] = _sync_collection(db.subjects, student_id, data.subjects, ("subjectCode",)); status["attendance"] = "success"
    if data.timetable is not None:
        status["timetableChanged"] = _sync_collection(db.timetable_slots, student_id, data.timetable, ("dayOfWeek", "startTime", "endTime", "subjectCode")); status["timetable"] = "success"
    elif data.timetable_error:
        status["timetableError"] = data.timetable_error
    # Safe debug counters only - never credentials, cookies, or tokens.
    logger.info(
        "SYNC_DB: student=%s subjects received=%s subjects changed=%s attendance=%s timetable changed=%s",
        student_id, len(data.subjects or []), status["subjectsChanged"], status["attendance"], status["timetableChanged"],
    )
    db.users.update_one({"student_id": student_id}, {"$set": {"lastSyncAt": _now(), "last_sync_status": status}})
    if status["subjectsChanged"] or status["timetableChanged"]:
        db.sync_history.insert_one({"student_id": student_id, "timestamp": _now(), "subjectsChanged": status["subjectsChanged"], "timetableChanged": status["timetableChanged"]})
    return status
