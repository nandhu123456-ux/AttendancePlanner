import os
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.config.database import get_database

from app.services.credential_service import (
    ENCRYPTION_VERSION,
    encrypt_password,
)

from app.services.gitam_portal import (
    InvalidCredentials,
    PortalError,
    authenticate,
    fetch_current_data,
)

from app.services.plan_service import (
    build_plan_from_database,
    get_preferences,
)

from app.services.planner_db import get_latest_plan

from app.services.prediction import future_class_instances

from app.services.security import (
    create_access_token,
    verify_token,
)

from app.services.session_store import (
    get_session,
    save_session,
)

from app.services.sync_service import sync_portal_data

from app.services.calendar_service import (
    get_applicable_academic_calendar,
    get_applicable_calendar_events,
    get_batch_from_student_id,
    get_date_picker_range,
    get_student_year_from_batch,
    now_date,
    DEFAULT_CAMPUS,
)

router = APIRouter()
MAX_ADJUSTMENTS = int(os.getenv("MAX_CUSTOM_ADJUSTMENTS_PER_MONTH", "4"))

class LoginRequest(BaseModel):
    username: str = Field(
        min_length=3,
        max_length=64,
        pattern=r"^[A-Za-z0-9_-]+$"
    )

    password: str = Field(
        min_length=1,
        max_length=256
    )

class PreferencesRequest(BaseModel):
    target_percentage: int = Field(ge=1, le=100)
    exam_date: date
    notifications_enabled: bool = False
class AdjustmentRequest(BaseModel):
    subject_code: str = Field(min_length=1, max_length=64)
    total_classes: int = Field(ge=0)
    present_classes: int = Field(ge=0)
    reason: str | None = Field(default=None, max_length=300)
class SimulationRequest(BaseModel):
    from_date: date
    to_date: date
    attend_class_ids: list[str] = []
    bunk_class_ids: list[str] = []

class TargetTypeRequest(BaseModel):
    target_type: str = Field(pattern=r"^custom$")
    custom_target_date: date | None = None
    campus: str | None = None
    batch: int | None = None
    year: int | None = None

def _student_for(student_id, user):
    if student_id != user["student_id"]: raise HTTPException(403, "You may only access your own data")
    return student_id
def _plan_or_404(student_id):
    result = get_latest_plan(student_id)
    if not result: raise HTTPException(404, "No attendance data found. Sync after logging in.")
    return result

@router.post("/login")
def login(data: LoginRequest):
    try:
        session = authenticate(data.username, data.password)
    except InvalidCredentials as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    except (PortalError, RuntimeError) as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    now = datetime.now(timezone.utc)
    get_database().users.update_one(
        {"student_id": data.username},
        {"$set": {"username": data.username, "encryptedPassword": encrypt_password(data.password), "encryptionVersion": ENCRYPTION_VERSION, "lastLoginAt": now},
         "$setOnInsert": {"target_percentage": 75, "notifications_enabled": False, "custom_target_date": (date.today() + timedelta(days=30)).isoformat()}},
        upsert=True
    )
    save_session(data.username, session)
    return {"token": create_access_token(data.username), "student_id": data.username, "needs_initial_sync": get_database().subjects.find_one({"student_id": data.username}) is None}

@router.post("/sync/{student_id}")
def sync_data(student_id: str, user=Depends(verify_token)):
    _student_for(student_id, user); session = get_session(student_id)
    if session is None: raise HTTPException(401, "Portal session expired. Please log in again.")
    try:
        status_data = sync_portal_data(student_id, fetch_current_data(session))
        result = build_plan_from_database(student_id)
    except PortalError as exc:
        raise HTTPException(502, str(exc)) from exc
    except ValueError as exc:
        # Return sync status even if plan building fails (e.g., no target date set)
        return {"message": "Attendance synchronized but plan needs configuration", "sync": status_data, "error": str(exc), "needs_target_date": True}
    return {"message": "Attendance synchronized", "sync": status_data, "result": result}

@router.get("/planner/{student_id}")
def get_planner(student_id: str, user=Depends(verify_token)):
    student_id = _student_for(student_id, user); result = _plan_or_404(student_id)
    account = get_database().users.find_one({"student_id": student_id}, {"_id": 0, "lastSyncAt": 1, "last_sync_status": 1, "customAdjustmentCount": 1, "customAdjustmentMonth": 1}) or {}
    used = account.get("customAdjustmentCount", 0) if account.get("customAdjustmentMonth") == date.today().strftime("%Y-%m") else 0
    result["sync_status"] = {"last_portal_sync_at": account.get("lastSyncAt"), **account.get("last_sync_status", {})}
    result["custom_adjustments"] = {"used": used, "limit": MAX_ADJUSTMENTS}
    return result

@router.get("/subjects/{student_id}")
def get_subjects(student_id: str, user=Depends(verify_token)): return {"subjects": _plan_or_404(_student_for(student_id, user))["subjects"]}
@router.get("/overall/{student_id}")
def get_overall(student_id: str, user=Depends(verify_token)): return {"overall": _plan_or_404(_student_for(student_id, user))["overall"]}
@router.get("/history/{student_id}")
def get_history(student_id: str, user=Depends(verify_token)):
    _student_for(student_id, user)
    return {"records": list(get_database().sync_history.find({"student_id": student_id}, {"_id": 0}).sort("timestamp", -1).limit(50))}

@router.get("/settings/{student_id}")
def get_settings(student_id: str, user=Depends(verify_token)):
    student_id = _student_for(student_id, user)
    prefs = get_preferences(student_id)
    account = get_database().users.find_one({"student_id": student_id}, {"_id": 0, "customAdjustmentCount": 1, "customAdjustmentMonth": 1, "batch": 1, "year": 1, "campus": 1, "target_type": 1, "custom_target_date": 1}) or {}
    used = account.get("customAdjustmentCount", 0) if account.get("customAdjustmentMonth") == date.today().strftime("%Y-%m") else 0

    # Get calendar-aware date picker range
    batch = account.get("batch")
    year = account.get("year")
    campus = account.get("campus") or DEFAULT_CAMPUS
    if batch is None:
        batch = get_batch_from_student_id(student_id)
    if year is None and batch is not None:
        year = get_student_year_from_batch(batch)

    calendar = get_applicable_academic_calendar(student_year=year, student_batch=batch)
    events = get_applicable_calendar_events(calendar, campus)
    date_picker = get_date_picker_range(events)

    custom_target_date = account.get("custom_target_date")
    # The stored value may be a datetime (from set_target_type) OR an
    # ISO-formatted string (default from $setOnInsert on account creation).
    # Normalize to a date (or None if unparseable) so the response is a
    # consistent ISO date string.
    if isinstance(custom_target_date, datetime):
        custom_target_date = custom_target_date.date()
    elif isinstance(custom_target_date, str):
        try:
            custom_target_date = datetime.fromisoformat(custom_target_date).date()
        except ValueError:
            custom_target_date = None

    return {
        **prefs,
        "exam_date": prefs["exam_date"].isoformat(),
        "exam_year": calendar.get("academic_year") if calendar else now_date().year,
        "custom_adjustments_used": used,
        "custom_adjustments_limit": MAX_ADJUSTMENTS,
        "target_type": account.get("target_type", "custom"),
        "custom_target_date": custom_target_date.isoformat() if custom_target_date else None,
        "campus": campus,
        "batch": batch,
        "year": year,
        "date_picker": date_picker,
        "calendar_info": {
            "academic_year": calendar.get("academic_year") if calendar else None,
            "semester_type": calendar.get("semester_type") if calendar else None,
        },
    }


@router.put("/settings/{student_id}")
def update_settings(student_id: str, data: PreferencesRequest, user=Depends(verify_token)):
    _student_for(student_id, user)
    if data.exam_date < date.today():
        raise HTTPException(422, "Exam date must be today or later")
    db = get_database()
    month = date.today().strftime("%Y-%m")
    account = db.users.find_one({"student_id": student_id}) or {}
    current_month = account.get("customAdjustmentMonth")
    used = account.get("customAdjustmentCount", 0) if current_month == month else 0
    db.users.update_one(
        {"student_id": student_id},
        {"$set": {
            "target_percentage": data.target_percentage,
            "exam_date": datetime.combine(data.exam_date, datetime.min.time()),
            "notifications_enabled": data.notifications_enabled,
            "customAdjustmentMonth": month,
            "customAdjustmentCount": used,
        }},
        upsert=True,
    )
    return {"message": "Settings saved", "result": build_plan_from_database(student_id)}


@router.post("/target-type/{student_id}")
def set_target_type(student_id: str, data: TargetTypeRequest, user=Depends(verify_token)):
    """Set the planner target type (custom date) with validation."""
    _student_for(student_id, user)

    # Update student context if provided
    update_fields = {"target_type": "custom"}
    if data.campus is not None:
        update_fields["campus"] = data.campus
    if data.batch is not None:
        update_fields["batch"] = data.batch
    if data.year is not None:
        update_fields["year"] = data.year

    if data.custom_target_date is not None:
        # Validate the custom date against the calendar
        batch = data.batch or get_database().users.find_one({"student_id": student_id}, {"batch": 1}).get("batch")
        if batch is None:
            batch = get_batch_from_student_id(student_id)
        year = data.year
        campus = data.campus or get_database().users.find_one({"student_id": student_id}, {"campus": 1}).get("campus") or DEFAULT_CAMPUS
        if year is None and batch is not None:
            year = get_student_year_from_batch(batch)

        calendar = get_applicable_academic_calendar(student_year=year, student_batch=batch)
        events = get_applicable_calendar_events(calendar, campus)

        from app.services.calendar_service import validate_planner_date
        validation = validate_planner_date(data.custom_target_date, events)
        if not validation["valid"]:
            raise HTTPException(422, validation["message"])

        update_fields["custom_target_date"] = datetime.combine(data.custom_target_date, datetime.min.time())

    get_database().users.update_one(
        {"student_id": student_id},
        {"$set": update_fields},
        upsert=True,
    )
    return {"message": "Target type updated", "result": build_plan_from_database(student_id)}

@router.post("/custom-adjustment/{student_id}")
def custom_adjustment(student_id: str, data: AdjustmentRequest, user=Depends(verify_token)):
    _student_for(student_id, user)
    if data.present_classes > data.total_classes: raise HTTPException(422, "Present classes cannot exceed total classes")
    db = get_database(); month = date.today().strftime("%Y-%m"); account = db.users.find_one({"student_id": student_id}) or {}; used = account.get("customAdjustmentCount", 0) if account.get("customAdjustmentMonth") == month else 0
    if used >= MAX_ADJUSTMENTS: raise HTTPException(429, f"You have used all {MAX_ADJUSTMENTS} adjustments for this month.")
    old = db.subjects.find_one({"student_id": student_id, "subjectCode": data.subject_code})
    if not old: raise HTTPException(404, "Subject not found")
    now = datetime.now(timezone.utc)
    new = {"totalClasses": data.total_classes, "presentClasses": data.present_classes}
    db.subjects.update_one({"_id": old["_id"]}, {"$set": {**new, "updatedAt": now, "isCustomAdjusted": True}})
    db.users.update_one({"student_id": student_id}, {"$set": {"customAdjustmentMonth": month, "customAdjustmentCount": used+1}})
    db.adjustment_log.insert_one({"student_id": student_id, "subjectCode": data.subject_code, "oldValue": {k: old[k] for k in new}, "newValue": new, "reason": data.reason, "timestamp": now})
    return {"message": "Custom adjustment saved", "used": used+1, "limit": MAX_ADJUSTMENTS, "result": build_plan_from_database(student_id)}

@router.post("/planner/simulate/{student_id}")
def simulate(student_id: str, data: SimulationRequest, user=Depends(verify_token)):
    _student_for(student_id, user)
    if data.to_date < data.from_date:
        raise HTTPException(422, "To date must be on or after from date")

    # Load student context and calendar
    account = get_database().users.find_one({"student_id": student_id}, {"_id": 0, "batch": 1, "year": 1, "campus": 1}) or {}
    batch = account.get("batch")
    year = account.get("year")
    campus = account.get("campus") or DEFAULT_CAMPUS
    if batch is None:
        batch = get_batch_from_student_id(student_id)
    if year is None and batch is not None:
        year = get_student_year_from_batch(batch)

    calendar = get_applicable_academic_calendar(student_year=year, student_batch=batch)
    events = get_applicable_calendar_events(calendar, campus)

    slots = list(get_database().timetable_slots.find({"student_id": student_id}, {"_id": 0, "student_id": 0}))
    start = datetime.combine(data.from_date, datetime.min.time())
    classes = future_class_instances(
        slots, start, data.to_date,
        blocked_dates=events["all_blocked"],
        timetable_overrides=events.get("timetable_overrides"),
    )
    selected_attend, selected_bunk = set(data.attend_class_ids), set(data.bunk_class_ids)
    if selected_attend & selected_bunk:
        raise HTTPException(422, "A class cannot be both attended and bunked")
    subjects = list(get_database().subjects.find({"student_id": student_id}, {"_id": 0, "student_id": 0}))
    simulated = {}
    for subject in subjects:
        code = subject["subjectCode"]
        attend = sum(item["id"] in selected_attend and item["subjectCode"] == code for item in classes)
        bunk = sum(item["id"] in selected_bunk and item["subjectCode"] == code for item in classes)
        total = subject["totalClasses"] + attend + bunk
        present = subject["presentClasses"] + attend
        simulated[code] = {
            "totalClasses": total,
            "presentClasses": present,
            "absentClasses": total - present,
            "percentage": round(100 * present / total, 2) if total else 0,
        }
    return {"classes": classes, "simulation": simulated}
