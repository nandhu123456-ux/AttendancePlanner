import math


def attendance_metrics(total, present, target=75):
    """Mathematically correct values calculated from actual current counts."""
    total, present = max(0, int(total)), min(max(0, int(present)), max(0, int(total)))
    percentage = round(100 * present / total, 2) if total else 0.0
    
    # For target = 100%: impossible if present < total, 0 if present >= total
    if target >= 100:
        if present >= total:
            needed = 0
            # safe bunks = 0 when already at or above 100%
            # verify loop will keep bunks at 0
            bunks = 0
        else:
            needed = None  # impossible
            bunks = 0
        ratio = 1.0  # avoid division issues below
    else:
        ratio = target / 100
        # Find smallest integer x s.t. (present + x) / (total + x) >= target/100
        # Solve: present + x >= ratio * (total + x)
        #       present + x >= ratio*total + ratio*x
        #       present - ratio*total >= x*(ratio - 1)
        #       (present - ratio*total) / (ratio - 1) <= x  (note: ratio-1 is negative, flips inequality)
        #       x >= (ratio*total - present) / (1 - ratio)
        needed = math.ceil((ratio * total - present) / (1 - ratio)) if ratio > 0 else 0
        needed = max(0, needed)
        # Verify the final percentage
        while needed and round(100 * (present + needed) / (total + needed), 10) < target - 0.001:
            needed += 1
        # Verify safe bunks
        bunks = max(0, math.floor(present / ratio - total)) if total and percentage >= target else 0
        while bunks and present / (total + bunks) < ratio:
            bunks -= 1
    
    return {"percentage": percentage, "classes_required_to_target": needed, "safe_bunks": bunks}


def attendance_window_metrics(conducted, present, future_classes, target=75):
    """Attendance decisions for a fixed future window (today through exam date)."""
    total = conducted + future_classes
    if total == 0:
        return {"safe_skips": 0, "required_attendance": 0, "after_attending_all": 0, "target_reachable": True}
    required = math.ceil((target / 100) * total - present)
    required = max(0, required)
    target_reachable = required <= future_classes
    required_in_window = min(required, future_classes)
    safe_skips = max(0, future_classes - required_in_window) if target_reachable else 0
    return {
        "safe_skips": safe_skips,
        "required_attendance": required_in_window,
        "after_attending_all": round(100 * (present + future_classes) / total, 2),
        "target_reachable": target_reachable,
    }


def overall_recommendation(planner_data,target_percentage):
    conducted = sum(item["conducted"] for item in planner_data.values())
    present = sum(item["present"] for item in planner_data.values())
    future = sum(item.get("future_classes", 0) for item in planner_data.values())
    metrics = attendance_window_metrics(conducted, present, future, target_percentage)
    return {
        "current_percentage": round(100 * present / conducted, 2) if conducted else 0,
        "future_classes": future,
        "after_attending_all": metrics["after_attending_all"],
        "can_skip": metrics["safe_skips"],
        "need_to_attend": metrics["required_attendance"],
        "target_percentage": target_percentage,
        "target_reachable_in_window": metrics["target_reachable"],
    }


def overall_skip_limit(conducted, present, future_classes, target_percentage):
    return attendance_window_metrics(conducted, present, future_classes, target_percentage)["safe_skips"]


def overall_classes_needed(conducted, present, future_classes, target_percentage):
    return attendance_window_metrics(conducted, present, future_classes, target_percentage)["required_attendance"]


def subject_warnings(planner_data, target_percentage=75):
    warnings = []
    for subject, data in planner_data.items():
        if data["current_percentage"] < target_percentage:
            warnings.append({"subject": subject, "percentage": data["current_percentage"], "message": f"{subject} is below {target_percentage}%"})
    return warnings
