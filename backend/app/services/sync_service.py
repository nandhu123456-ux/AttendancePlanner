from datetime import datetime, timezone

from app.config.database import get_database
from .gitam_portal import PortalData


def _now(): return datetime.now(timezone.utc)


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
    db.users.update_one({"student_id": student_id}, {"$set": {"lastSyncAt": _now(), "last_sync_status": status}})
    if status["subjectsChanged"] or status["timetableChanged"]:
        db.sync_history.insert_one({"student_id": student_id, "timestamp": _now(), "subjectsChanged": status["subjectsChanged"], "timetableChanged": status["timetableChanged"]})
    return status
