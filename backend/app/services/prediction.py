from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo


def future_class_instances(slots, start: datetime | None, end_date: date | None, timezone_name="Asia/Kolkata", blocked_dates: set | None = None, timetable_overrides: list | None = None):
    """Expand weekly slots into concrete class instances between start and end_date.

    Calendar-aware: skips dates blocked by the academic calendar.
    Supports timetable overrides (e.g., 'Monday timetable on X date').
    A class at or before the current time is not counted as future.
    """
    tz = ZoneInfo(timezone_name)
    now = start or datetime.now(tz)
    now = now.astimezone(tz) if now.tzinfo else now.replace(tzinfo=tz)
    if end_date is None or end_date < now.date():
        return []

    blocked = blocked_dates or set()
    overrides = timetable_overrides or []

    # Build a lookup for overrides by date
    override_by_date = {}
    for override in overrides:
        override_date = override.get("date")
        if override_date:
            if isinstance(override_date, str):
                override_date = date.fromisoformat(override_date)
            elif isinstance(override_date, datetime):
                override_date = override_date.date()
            override_by_date[override_date] = override

    instances = []
    total_days = (end_date - now.date()).days + 1

    for offset in range(total_days):
        class_date = now.date() + timedelta(days=offset)

        # Skip blocked dates
        if class_date in blocked:
            continue

        # Determine effective day of week for this date
        effective_day = class_date.strftime("%A")

        # Check for timetable override on this date
        if class_date in override_by_date:
            override = override_by_date[class_date]
            override_day = override.get("follow_day_of_week")
            if override_day:
                effective_day = override_day
            # If override explicitly says no classes, skip
            if override.get("no_classes", False):
                continue

        for slot in slots:
            if slot.get("dayOfWeek") != effective_day:
                continue
            try:
                start_time = time.fromisoformat(slot["startTime"])
            except (KeyError, ValueError):
                continue
            if class_date == now.date() and datetime.combine(class_date, start_time, tz) <= now:
                continue
            identifier = f"{class_date.isoformat()}|{slot['startTime']}|{slot['subjectCode']}"
            instances.append({
                "id": identifier,
                "date": class_date.isoformat(),
                "day": slot["dayOfWeek"],
                "startTime": slot["startTime"],
                "endTime": slot.get("endTime"),
                "subjectCode": slot["subjectCode"],
                "subjectName": slot.get("subjectName", slot["subjectCode"]),
            })

    return sorted(instances, key=lambda item: (item["date"], item["startTime"], item["subjectCode"]))


def predict_future_classes(timetable, current_datetime, end_date, blocked_dates: set | None = None, timetable_overrides: list | None = None):
    """Compatibility helper returning a per-subject count.

    Calendar-aware: accepts blocked_dates and timetable_overrides.
    """
    slots = timetable if isinstance(timetable, list) else [
        {"dayOfWeek": lesson["day"], "startTime": lesson["start_time"], "endTime": lesson.get("end_time"), "subjectCode": code, "subjectName": course.get("subject")}
        for code, course in timetable.items() for lesson in course.get("classes", [])
    ]
    counts = {}
    for item in future_class_instances(slots, current_datetime, end_date, blocked_dates=blocked_dates, timetable_overrides=timetable_overrides):
        counts[item["subjectCode"]] = counts.get(item["subjectCode"], 0) + 1
    return counts
