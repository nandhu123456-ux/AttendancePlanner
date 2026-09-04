"""Academic calendar service for calendar-aware attendance planning.

Provides reusable functions to:
- Select the correct academic calendar based on student year/batch
- Filter calendar events by campus (BLR default)
- Determine blocked class dates (holidays, exams, breaks, etc.)
- Resolve automatic sessional targets
- Validate custom planner dates dynamically
"""
import os
import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.config.database import get_database

DEFAULT_TIMEZONE = os.getenv("PLANNER_TIMEZONE", "Asia/Kolkata")
DEFAULT_CAMPUS = os.getenv("PLANNER_CAMPUS", "BLR")


def _tz() -> ZoneInfo:
    return ZoneInfo(DEFAULT_TIMEZONE)


def now_date() -> date:
    """Current date in the application's configured timezone."""
    return datetime.now(_tz()).date()


def get_applicable_academic_calendar(student_year: int | None = None, student_batch: int | None = None, semester_type: str = "ODD") -> dict | None:
    """Select the correct academic calendar document from MongoDB.

    Calendars store applicable criteria as flat arrays:
    - ``applicable_batches``: admission batch values (int or str), e.g. ``[2026]`` / ``['2026']``
    - ``applicable_years``:    study years (ints),             e.g. ``[1, 2, 3, 4]``

    A legacy document shape uses ``applicable_years`` as an array of objects with
    ``admission_year`` / ``study_year`` fields; both shapes are matched here.

    Selection priority:
    1. Match by batch in ``applicable_batches``.
    2. Match by study year in ``applicable_years``.
    3. Fall back to the most recent ODD calendar.
    """
    db = get_database()
    collection = db.academic_calendars
    query = {"semester_type": semester_type}

    # 1. By admission batch (flat ``applicable_batches`` array; batch may be int or str).
    if student_batch is not None:
        batch_values = [student_batch, str(student_batch)]
        calendar = collection.find_one({**query, "applicable_batches": {"$in": batch_values}})
        if calendar:
            return calendar
        # Legacy object shape.
        calendar = collection.find_one({**query, "applicable_years.admission_year": str(student_batch)})
        if calendar:
            return calendar

    # 2. By study year (flat ``applicable_years`` array of ints).
    if student_year is not None:
        year_values = [student_year, str(student_year)]
        calendar = collection.find_one({**query, "applicable_years": {"$in": year_values}})
        if calendar:
            return calendar
        # Legacy object shape.
        calendar = collection.find_one({**query, "applicable_years.study_year": student_year})
        if calendar:
            return calendar

    # 3. Fallback: most recent ODD calendar
    return collection.find_one(query, sort=[("academic_year", -1)])


def _event_applies_to_campus(event, campus: str) -> bool:
    """Check whether a calendar event applies to the given campus.

    Rules:
    - event marked with specific campus suffix (e.g. 'BLR', 'HYD', 'VSP') -> only applicable to that campus
    - event with no campus marker or 'ALL' -> applicable to all campuses
    - event as string (no campus info) -> applicable to all campuses
    """
    if isinstance(event, str):
        return True
    event_campus = event.get("campus") or event.get("applicable_campus")
    if event_campus is None:
        return True
    event_campus = str(event_campus).upper().strip()
    if event_campus in ("ALL", ""):
        return True
    return event_campus == campus.upper()


def _expand_date_range(start_date, end_date) -> set[date]:
    """Expand a date range into a set of individual dates."""
    if not start_date or not end_date:
        return set()
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
    if isinstance(start_date, datetime):
        start_date = start_date.date()
    if isinstance(end_date, datetime):
        end_date = end_date.date()
    if start_date > end_date:
        return set()
    return {start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1)}


def get_applicable_calendar_events(calendar: dict, campus: str = DEFAULT_CAMPUS) -> dict:
    """Extract and filter calendar events by campus.

    Returns a structured dict with categorized event date sets.
    """
    if not calendar:
        return {
            "holidays": set(),
            "sessional_1": set(),
            "sessional_2": set(),
            "non_instructional_days": set(),
            "semester_break": set(),
            "other_blocked": set(),
            "timetable_overrides": [],
            "all_blocked": set(),
            "sessional_1_range": None,
            "sessional_2_range": None,
        }

    holidays = set()
    for event in calendar.get("holidays", []):
        if isinstance(event, dict) and _event_applies_to_campus(event, campus):
            holidays |= _expand_date_range(event.get("start_date"), event.get("end_date"))

    sessional_1 = set()
    s1_range = None
    s1_config = calendar.get("sessional_1") or calendar.get("sessional_I")
    if not s1_config and calendar.get("exams"):
        exams = calendar.get("exams")
        if isinstance(exams, list) and len(exams) > 0:
            s1_config = exams[0]
        elif isinstance(exams, dict):
            s1_config = exams.get("sessional_1") or exams.get("sessional_I")
    if s1_config:
        s1_start = s1_config.get("start_date")
        s1_end = s1_config.get("end_date")
        if s1_start and s1_end:
            sessional_1 = _expand_date_range(s1_start, s1_end)
            if isinstance(s1_start, datetime):
                s1_start = s1_start.date()
            if isinstance(s1_end, datetime):
                s1_end = s1_end.date()
            s1_range = (s1_start, s1_end)

    sessional_2 = set()
    s2_range = None
    s2_config = calendar.get("sessional_2") or calendar.get("sessional_II")
    if not s2_config and calendar.get("exams"):
        exams = calendar.get("exams")
        if isinstance(exams, list) and len(exams) > 1:
            s2_config = exams[1]
        elif isinstance(exams, dict):
            s2_config = exams.get("sessional_2") or exams.get("sessional_II")
    if s2_config:
        s2_start = s2_config.get("start_date")
        s2_end = s2_config.get("end_date")
        if s2_start and s2_end:
            sessional_2 = _expand_date_range(s2_start, s2_end)
            if isinstance(s2_start, datetime):
                s2_start = s2_start.date()
            if isinstance(s2_end, datetime):
                s2_end = s2_end.date()
            s2_range = (s2_start, s2_end)

    non_instructional = set()
    for event in calendar.get("non_instructional_days", []):
        if isinstance(event, dict) and _event_applies_to_campus(event, campus):
            non_instructional |= _expand_date_range(event.get("start_date"), event.get("end_date"))

    semester_break = set()
    for event in calendar.get("semester_break", []):
        if isinstance(event, dict) and _event_applies_to_campus(event, campus):
            semester_break |= _expand_date_range(event.get("start_date"), event.get("end_date"))

    other_blocked = set()
    for event in calendar.get("blocked_dates", []):
        if isinstance(event, dict) and _event_applies_to_campus(event, campus):
            other_blocked |= _expand_date_range(event.get("start_date"), event.get("end_date"))

    timetable_overrides = calendar.get("timetable_overrides", [])

    # Extract classwork range (last working day)
    classwork_range = None
    classwork = calendar.get("classwork")
    if classwork:
        cw_start = classwork.get("start_date")
        cw_end = classwork.get("end_date")
        if cw_start and cw_end:
            if isinstance(cw_start, str):
                cw_start = datetime.strptime(cw_start, "%Y-%m-%d").date()
            if isinstance(cw_end, str):
                cw_end = datetime.strptime(cw_end, "%Y-%m-%d").date()
            classwork_range = (cw_start, cw_end)

    all_blocked = holidays | sessional_1 | sessional_2 | non_instructional | semester_break | other_blocked

    return {
        "holidays": holidays,
        "sessional_1": sessional_1,
        "sessional_2": sessional_2,
        "non_instructional_days": non_instructional,
        "semester_break": semester_break,
        "other_blocked": other_blocked,
        "timetable_overrides": timetable_overrides,
        "all_blocked": all_blocked,
        "sessional_1_range": s1_range,
        "sessional_2_range": s2_range,
        "classwork_range": classwork_range,
    }


def is_blocked_class_date(check_date: date, events: dict) -> bool:
    """Return True if the given date is blocked (no classes can occur)."""
    return check_date in events["all_blocked"]


def get_upcoming_sessional(events: dict, current_date: date | None = None) -> str:
    """Determine the automatic target sessional.

    Returns 'sessional_1' if Sessional-I has not yet started or is in progress.
    Returns 'sessional_2' if Sessional-I is over.
    """
    if current_date is None:
        current_date = now_date()

    s1_range = events.get("sessional_1_range")
    if s1_range:
        s1_end = s1_range[1]
        if current_date <= s1_end:
            return "sessional_1"

    return "sessional_2"


def get_sessional_end_date(events: dict, sessional: str) -> date | None:
    """Get the end date for a given sessional."""
    if sessional == "sessional_1":
        rng = events.get("sessional_1_range")
    elif sessional == "sessional_2":
        rng = events.get("sessional_2_range")
    else:
        return None
    return rng[1] if rng else None


def get_sessional_start_date(events: dict, sessional: str) -> date | None:
    """Get the start date for a given sessional."""
    if sessional == "sessional_1":
        rng = events.get("sessional_1_range")
    elif sessional == "sessional_2":
        rng = events.get("sessional_2_range")
    else:
        return None
    return rng[0] if rng else None


def validate_planner_date(custom_date: date, events: dict, current_date: date | None = None) -> dict:
    """Validate a custom planner date against the academic calendar.

    Rules:
    - Cannot be before today
    - Cannot be after classwork end date (last working day)
    - Returns validation result with message
    """
    if current_date is None:
        current_date = now_date()

    # Use classwork end date as max (last working day)
    classwork_range = events.get("classwork_range")
    max_date = classwork_range[1] if classwork_range else None

    # Convert string to date if needed
    if isinstance(max_date, str):
        max_date = datetime.strptime(max_date, "%Y-%m-%d").date()

    if custom_date < current_date:
        return {
            "valid": False,
            "message": f"Selected date ({custom_date.isoformat()}) is before today ({current_date.isoformat()}).",
            "min_date": current_date.isoformat(),
            "max_date": max_date.isoformat() if max_date else None,
        }

    if max_date and custom_date > max_date:
        return {
            "valid": False,
            "message": f"Selected date ({custom_date.isoformat()}) is after the semester end ({max_date.isoformat()}).",
            "min_date": current_date.isoformat(),
            "max_date": max_date.isoformat(),
        }

    return {
        "valid": True,
        "message": "Date is valid.",
        "min_date": current_date.isoformat(),
        "max_date": max_date.isoformat() if max_date else None,
    }


def resolve_target_date(events: dict, target_type: str = "auto", custom_date: date | None = None, current_date: date | None = None) -> dict:
    """Resolve the effective target date for the planner.

    Args:
        events: Calendar events dict from get_applicable_calendar_events
        target_type: 'auto' for automatic sessional, 'custom' for user-selected
        custom_date: The user-selected date (required if target_type='custom')
        current_date: Override for current date (for testing)

    Returns:
        Dict with target_date, target_type, sessional info, and validation
    """
    if current_date is None:
        current_date = now_date()

    if target_type == "custom" and custom_date is not None:
        validation = validate_planner_date(custom_date, events, current_date)
        return {
            "target_date": custom_date,
            "target_type": "custom",
            "sessional": None,
            "validation": validation,
        }

    # Automatic: determine upcoming sessional
    upcoming = get_upcoming_sessional(events, current_date)
    end_date = get_sessional_end_date(events, upcoming)
    start_date = get_sessional_start_date(events, upcoming)

    return {
        "target_date": end_date,
        "target_type": "auto",
        "sessional": upcoming,
        "sessional_start": start_date,
        "sessional_end": end_date,
        "validation": {
            "valid": True,
            "message": f"Targeting {upcoming.replace('_', '-').upper()} (ends {end_date.isoformat() if end_date else 'unknown'}).",
            "min_date": current_date.isoformat(),
            "max_date": events.get("sessional_2_range", (None, None))[1].isoformat() if events.get("sessional_2_range") and events.get("sessional_2_range")[1] else None,
        },
    }


def get_date_picker_range(events: dict, current_date: date | None = None) -> dict:
    """Get the min/max dates for the frontend date picker.

    Min: today
    Max: classwork end date (last working day) from the calendar
    """
    if current_date is None:
        current_date = now_date()

    # Use classwork end date as max (last working day)
    classwork_range = events.get("classwork_range")
    max_date = classwork_range[1] if classwork_range else None

    # Convert string to date if needed
    if isinstance(max_date, str):
        max_date = datetime.strptime(max_date, "%Y-%m-%d").date()

    return {
        "min_date": current_date.isoformat(),
        "max_date": max_date.isoformat() if max_date else None,
    }


def get_student_year_from_batch(batch: int | None, current_year: int | None = None) -> int | None:
    """Map admission batch to current academic year.

    For ODD semester 2026-2027:
    - 2026 batch -> 1st year
    - 2025 batch -> 2nd year
    - 2024 batch -> 3rd year
    - 2023 batch -> 4th year
    """
    if batch is None:
        return None
    if current_year is None:
        current_year = now_date().year

    diff = current_year - batch
    if 0 <= diff <= 3:
        return diff + 1
    return None


def get_batch_from_student_id(student_id: str | None) -> int | None:
    """Infer the admission batch (year) from a roll-number style student ID.

    GITAM roll numbers begin with the admission year, e.g. ``2026347090`` -> 2026.
    Returns None when the prefix is not a plausible recent year.
    """
    if not student_id:
        return None
    match = re.match(r"\s*(\d{4})", str(student_id))
    if not match:
        return None
    year = int(match.group(1))
    this_year = now_date().year
    if 1980 <= year <= this_year:
        return year
    return None

