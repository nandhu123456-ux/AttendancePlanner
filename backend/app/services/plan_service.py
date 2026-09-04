import os
from collections import Counter
from datetime import date, datetime, timedelta, timezone

from app.config.database import get_database
from .calculator import attendance_metrics
from .planner_db import save_planner_result
from .prediction import future_class_instances
from .calendar_service import (
    get_applicable_academic_calendar,
    get_applicable_calendar_events,
    get_batch_from_student_id,
    get_date_picker_range,
    get_student_year_from_batch,
    now_date,
    DEFAULT_CAMPUS,
)

DEFAULT_TARGET = 75


def get_student_context(student_id):
    """Retrieve student context (year, batch, campus) from stored user data."""
    user = get_database().users.find_one(
        {"student_id": student_id},
        {"_id": 0, "batch": 1, "year": 1, "campus": 1, "target_percentage": 1, "exam_date": 1, "notifications_enabled": 1, "target_type": 1, "custom_target_date": 1}
    ) or {}

    batch = user.get("batch")
    year = user.get("year")
    campus = user.get("campus") or DEFAULT_CAMPUS

    # If batch isn't stored, infer it from the roll number prefix (e.g. 2026347090 -> 2026).
    if batch is None:
        batch = get_batch_from_student_id(student_id)

    # If year not explicitly set, derive from batch
    if year is None and batch is not None:
        year = get_student_year_from_batch(batch)

    return {
        "batch": batch,
        "year": year,
        "campus": campus,
        "target_percentage": user.get("target_percentage", DEFAULT_TARGET),
        "exam_date": user.get("exam_date"),
        "notifications_enabled": user.get("notifications_enabled", False),
        "target_type": user.get("target_type", "custom"),
        "custom_target_date": user.get("custom_target_date"),
    }


def get_preferences(student_id):
    """Get student preferences with calendar-aware date resolution."""
    ctx = get_student_context(student_id)

    exam_date = ctx["exam_date"]
    if isinstance(exam_date, datetime):
        exam_date = exam_date.date()

    return {
        "target_percentage": ctx["target_percentage"],
        "exam_date": exam_date or (date.today() + timedelta(days=30)),
        "notifications_enabled": ctx["notifications_enabled"],
        "target_type": ctx.get("target_type", "custom"),
        "custom_target_date": ctx.get("custom_target_date"),
    }


def build_plan_from_database(student_id):
    """Build a calendar-aware attendance plan for the student."""
    ctx = get_student_context(student_id)
    db = get_database()

    # Load calendar for blocked dates
    calendar = get_applicable_academic_calendar(
        student_year=ctx["year"],
        student_batch=ctx["batch"],
    )
    events = get_applicable_calendar_events(calendar, ctx["campus"])

    # Get custom target date (always use custom date now)
    custom_date = ctx.get("custom_target_date")
    if isinstance(custom_date, datetime):
        custom_date = custom_date.date()
    if isinstance(custom_date, str):
        custom_date = datetime.strptime(custom_date, "%Y-%m-%d").date()

    if not custom_date:
        raise ValueError("No target date set. Please select a target date in Settings.")

    target_date = custom_date
    target_type = "custom"

    # Load data
    subjects = list(db.subjects.find({"student_id": student_id}, {"_id": 0, "student_id": 0}))
    slots = list(db.timetable_slots.find({"student_id": student_id}, {"_id": 0, "student_id": 0}))

    # Generate calendar-aware future instances
    instances = future_class_instances(
        slots,
        datetime.now(),
        target_date,
        blocked_dates=events["all_blocked"],
        timetable_overrides=events.get("timetable_overrides"),
    )

    # Count per weekday
    instance_days = Counter(item.get("day") for item in instances)

    future = {}
    for item in instances:
        future[item["subjectCode"]] = future.get(item["subjectCode"], 0) + 1

    # Build per-subject planner
    planner, warnings = {}, []
    for subject in subjects:
        metric = attendance_metrics(subject["totalClasses"], subject["presentClasses"], ctx["target_percentage"])
        code = subject["subjectCode"]
        planner[subject["subjectName"]] = {
            "course_code": code,
            "conducted": subject["totalClasses"],
            "present": subject["presentClasses"],
            "absent": subject["absentClasses"],
            "current_percentage": metric["percentage"],
            "future_classes": future.get(code, 0),
            "safe_skips": metric["safe_bunks"],
            "required_attendance": metric["classes_required_to_target"],
        }
        if metric["percentage"] < ctx["target_percentage"]:
            warnings.append({
                "subject": subject["subjectName"],
                "percentage": metric["percentage"],
                "message": f"{subject['subjectName']} is below {ctx['target_percentage']}%",
            })

    # Overall metrics
    total = sum(x["totalClasses"] for x in subjects)
    present = sum(x["presentClasses"] for x in subjects)
    metric = attendance_metrics(total, present, ctx["target_percentage"])
    future_total = len(instances)
    after = round(100 * (present + future_total) / (total + future_total), 2) if total + future_total else 0

    # Compile blocked dates info for transparency
    blocked_info = sorted([d.isoformat() for d in events["all_blocked"] if d >= now_date()])

    result = {
        "overall": {
            "current_percentage": metric["percentage"],
            "total_classes": total,
            "present_classes": present,
            "absent_classes": total - present,
            "future_classes": future_total,
            "after_attending_all": after,
            "can_skip": metric["safe_bunks"],
            "need_to_attend": metric["classes_required_to_target"],
            "target_percentage": ctx["target_percentage"],
            "target_reachable_in_window": after >= ctx["target_percentage"],
        },
        "warnings": warnings,
        "subjects": planner,
        "today_remaining_classes": [x for x in instances if x["date"] == date.today().isoformat()],
        "upcoming_classes": instances[:100],
        "exam_date": target_date.isoformat() if target_date else None,
        "target_type": target_type,
        "target_percentage": ctx["target_percentage"],
        "generated_at": datetime.now(timezone.utc),
        "calendar_info": {
            "academic_year": calendar.get("academic_year") if calendar else None,
            "semester_type": calendar.get("semester_type") if calendar else None,
            "blocked_dates_count": len(blocked_info),
            "blocked_dates_preview": blocked_info[:20],
        },
        "date_picker": get_date_picker_range(events),
    }

    save_planner_result(student_id, result)
    return result
