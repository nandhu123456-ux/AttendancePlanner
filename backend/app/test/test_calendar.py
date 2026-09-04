import os
import sys

# Add app directory to path so 'services' and 'api' can be imported directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from datetime import date, datetime

from services.calendar_service import (
    get_applicable_academic_calendar,
    get_applicable_calendar_events,
    is_blocked_class_date,
    get_upcoming_sessional,
    validate_planner_date,
    resolve_target_date,
    get_date_picker_range,
    get_student_year_from_batch,
    now_date,
    _event_applies_to_campus,
    _expand_date_range,
)
from services.prediction import future_class_instances


class StudentYearFromBatchTests(unittest.TestCase):
    """Test batch-to-year mapping for ODD semester 2026-2027."""

    def test_2025_batch_is_2nd_year(self):
        self.assertEqual(get_student_year_from_batch(2025), 2)

    def test_2024_batch_is_3rd_year(self):
        self.assertEqual(get_student_year_from_batch(2024), 3)

    def test_2023_batch_is_4th_year(self):
        self.assertEqual(get_student_year_from_batch(2023), 4)

    def test_2026_batch_is_1st_year(self):
        self.assertEqual(get_student_year_from_batch(2026), 1)

    def test_none_batch_returns_none(self):
        self.assertIsNone(get_student_year_from_batch(None))

    def test_out_of_range_batch(self):
        self.assertIsNone(get_student_year_from_batch(2019))


class CampusFilteringTests(unittest.TestCase):
    """Test BLR campus filtering logic."""

    def test_blr_event_applies_to_blr(self):
        self.assertTrue(_event_applies_to_campus({"campus": "BLR"}, "BLR"))

    def test_hyd_event_ignored_for_blr(self):
        self.assertFalse(_event_applies_to_campus({"campus": "HYD"}, "BLR"))

    def test_vsp_event_ignored_for_blr(self):
        self.assertFalse(_event_applies_to_campus({"campus": "VSP"}, "BLR"))

    def test_all_campus_applies_to_blr(self):
        self.assertTrue(_event_applies_to_campus({"campus": "ALL"}, "BLR"))

    def test_no_campus_applies_to_blr(self):
        self.assertTrue(_event_applies_to_campus({}, "BLR"))

    def test_none_campus_applies_to_blr(self):
        self.assertTrue(_event_applies_to_campus({"campus": None}, "BLR"))

    def test_lowercase_blr_event_applies(self):
        self.assertTrue(_event_applies_to_campus({"campus": "blr"}, "BLR"))


class ExpandDateRangeTests(unittest.TestCase):
    """Test date range expansion."""

    def test_single_day(self):
        result = _expand_date_range(date(2026, 9, 1), date(2026, 9, 1))
        self.assertEqual(result, {date(2026, 9, 1)})

    def test_multiple_days(self):
        result = _expand_date_range(date(2026, 9, 1), date(2026, 9, 3))
        self.assertEqual(result, {date(2026, 9, 1), date(2026, 9, 2), date(2026, 9, 3)})

    def test_datetime_input(self):
        result = _expand_date_range(datetime(2026, 9, 1), datetime(2026, 9, 2))
        self.assertEqual(result, {date(2026, 9, 1), date(2026, 9, 2)})

    def test_invalid_range(self):
        result = _expand_date_range(date(2026, 9, 5), date(2026, 9, 1))
        self.assertEqual(result, set())

    def test_none_input(self):
        result = _expand_date_range(None, None)
        self.assertEqual(result, set())


class CalendarEventsTests(unittest.TestCase):
    """Test calendar event extraction and filtering."""

    def setUp(self):
        self.sample_calendar = {
            "academic_year": "2026-2027",
            "semester_type": "ODD",
            "applicable_years": [2, 3, 4],
            "applicable_batches": [2025, 2024, 2023],
            "holidays": [
                {"start_date": date(2026, 10, 2), "end_date": date(2026, 10, 2), "name": "Gandhi Jayanti"},
                {"start_date": date(2026, 11, 14), "end_date": date(2026, 11, 14), "name": "Children's Day BLR", "campus": "BLR"},
                {"start_date": date(2026, 12, 25), "end_date": date(2026, 12, 25), "name": "Christmas HYD", "campus": "HYD"},
            ],
            "sessional_1": {"start_date": date(2026, 9, 20), "end_date": date(2026, 9, 25)},
            "sessional_2": {"start_date": date(2026, 11, 15), "end_date": date(2026, 11, 25)},
            "non_instructional_days": [
                {"start_date": date(2026, 10, 10), "end_date": date(2026, 10, 10)},
            ],
            "semester_break": [
                {"start_date": date(2026, 12, 20), "end_date": date(2026, 12, 31)},
            ],
            "timetable_overrides": [
                {"date": "2026-10-05", "follow_day_of_week": "Monday"},
            ],
        }

    def test_empty_calendar_returns_empty_sets(self):
        events = get_applicable_calendar_events(None)
        self.assertEqual(events["all_blocked"], set())
        self.assertIsNone(events["sessional_1_range"])
        self.assertIsNone(events["sessional_2_range"])

    def test_blr_holiday_applied(self):
        events = get_applicable_calendar_events(self.sample_calendar, "BLR")
        self.assertIn(date(2026, 11, 14), events["holidays"])

    def test_hyd_holiday_not_applied_for_blr(self):
        events = get_applicable_calendar_events(self.sample_calendar, "BLR")
        self.assertNotIn(date(2026, 12, 25), events["holidays"])

    def test_global_holiday_applied(self):
        events = get_applicable_calendar_events(self.sample_calendar, "BLR")
        self.assertIn(date(2026, 10, 2), events["holidays"])

    def test_sessional_dates_extracted(self):
        events = get_applicable_calendar_events(self.sample_calendar, "BLR")
        self.assertIn(date(2026, 9, 20), events["sessional_1"])
        self.assertIn(date(2026, 11, 25), events["sessional_2"])

    def test_sessional_ranges(self):
        events = get_applicable_calendar_events(self.sample_calendar, "BLR")
        self.assertEqual(events["sessional_1_range"], (date(2026, 9, 20), date(2026, 9, 25)))
        self.assertEqual(events["sessional_2_range"], (date(2026, 11, 15), date(2026, 11, 25)))

    def test_non_instructional_blocked(self):
        events = get_applicable_calendar_events(self.sample_calendar, "BLR")
        self.assertIn(date(2026, 10, 10), events["all_blocked"])

    def test_semester_break_blocked(self):
        events = get_applicable_calendar_events(self.sample_calendar, "BLR")
        self.assertIn(date(2026, 12, 25), events["semester_break"])

    def test_timetable_overrides_extracted(self):
        events = get_applicable_calendar_events(self.sample_calendar, "BLR")
        self.assertEqual(len(events["timetable_overrides"]), 1)


class BlockedDateTests(unittest.TestCase):
    """Test is_blocked_class_date function."""

    def test_blocked_date(self):
        events = {"all_blocked": {date(2026, 10, 2)}}
        self.assertTrue(is_blocked_class_date(date(2026, 10, 2), events))

    def test_unblocked_date(self):
        events = {"all_blocked": {date(2026, 10, 2)}}
        self.assertFalse(is_blocked_class_date(date(2026, 10, 3), events))


class UpcomingSessionalTests(unittest.TestCase):
    """Test automatic sessional detection."""

    def test_before_sessional_1(self):
        events = {
            "sessional_1_range": (date(2026, 9, 20), date(2026, 9, 25)),
            "sessional_2_range": (date(2026, 11, 15), date(2026, 11, 25)),
        }
        self.assertEqual(get_upcoming_sessional(events, date(2026, 9, 1)), "sessional_1")

    def test_after_sessional_1_switches_to_sessional_2(self):
        events = {
            "sessional_1_range": (date(2026, 9, 20), date(2026, 9, 25)),
            "sessional_2_range": (date(2026, 11, 15), date(2026, 11, 25)),
        }
        self.assertEqual(get_upcoming_sessional(events, date(2026, 10, 1)), "sessional_2")

    def test_on_sessional_1_end_date(self):
        events = {
            "sessional_1_range": (date(2026, 9, 20), date(2026, 9, 25)),
            "sessional_2_range": (date(2026, 11, 15), date(2026, 11, 25)),
        }
        self.assertEqual(get_upcoming_sessional(events, date(2026, 9, 25)), "sessional_1")


class ValidatePlannerDateTests(unittest.TestCase):
    """Test custom date validation."""

    def setUp(self):
        self.events = {
            "sessional_2_range": (date(2026, 11, 15), date(2026, 11, 25)),
            "all_blocked": set(),
        }

    def test_valid_date(self):
        result = validate_planner_date(date(2026, 10, 1), self.events, date(2026, 9, 15))
        self.assertTrue(result["valid"])

    def test_date_before_today_rejected(self):
        result = validate_planner_date(date(2026, 9, 10), self.events, date(2026, 9, 15))
        self.assertFalse(result["valid"])
        self.assertIn("before today", result["message"])

    def test_date_after_sessional_2_end_rejected(self):
        result = validate_planner_date(date(2026, 12, 1), self.events, date(2026, 9, 15))
        self.assertFalse(result["valid"])

    def test_date_exactly_at_sessional_2_end(self):
        result = validate_planner_date(date(2026, 11, 25), self.events, date(2026, 9, 15))
        self.assertTrue(result["valid"])


class ResolveTargetDateTests(unittest.TestCase):
    """Test target date resolution."""

    def setUp(self):
        self.events = {
            "sessional_1_range": (date(2026, 9, 20), date(2026, 9, 25)),
            "sessional_2_range": (date(2026, 11, 15), date(2026, 11, 25)),
            "all_blocked": set(),
        }

    def test_auto_before_sessional_1(self):
        result = resolve_target_date(self.events, "auto", current_date=date(2026, 9, 1))
        self.assertEqual(result["sessional"], "sessional_1")
        self.assertEqual(result["target_date"], date(2026, 9, 25))

    def test_auto_after_sessional_1(self):
        result = resolve_target_date(self.events, "auto", current_date=date(2026, 10, 1))
        self.assertEqual(result["sessional"], "sessional_2")

    def test_custom_date_valid(self):
        result = resolve_target_date(self.events, "custom", date(2026, 10, 15), current_date=date(2026, 9, 15))
        self.assertTrue(result["validation"]["valid"])
        self.assertEqual(result["target_type"], "custom")


class DatePickerRangeTests(unittest.TestCase):
    """Test date picker min/max generation."""

    def test_range_from_sessional_2(self):
        events = {"sessional_2_range": (date(2026, 11, 15), date(2026, 11, 25))}
        result = get_date_picker_range(events, date(2026, 9, 15))
        self.assertEqual(result["min_date"], "2026-09-15")
        self.assertEqual(result["max_date"], "2026-11-25")


class CalendarAwarePredictionTests(unittest.TestCase):
    """Test that future_class_instances respects blocked dates."""

    def test_blocked_date_excluded(self):
        slots = [{"dayOfWeek": "Monday", "startTime": "10:00", "endTime": "10:50", "subjectCode": "CS", "subjectName": "CS"}]
        blocked = {date(2026, 9, 7)}
        classes = future_class_instances(slots, datetime(2026, 9, 3, 8), date(2026, 9, 10), blocked_dates=blocked)
        dates = [c["date"] for c in classes]
        self.assertNotIn("2026-09-07", dates)

    def test_unblocked_date_included(self):
        slots = [{"dayOfWeek": "Monday", "startTime": "10:00", "endTime": "10:50", "subjectCode": "CS", "subjectName": "CS"}]
        classes = future_class_instances(slots, datetime(2026, 9, 3, 8), date(2026, 9, 10))
        dates = [c["date"] for c in classes]
        self.assertIn("2026-09-07", dates)

    def test_all_dates_blocked(self):
        slots = [{"dayOfWeek": "Monday", "startTime": "10:00", "endTime": "10:50", "subjectCode": "CS", "subjectName": "CS"}]
        blocked = {date(2026, 9, 7), date(2026, 9, 14)}
        classes = future_class_instances(slots, datetime(2026, 9, 3, 8), date(2026, 9, 20), blocked_dates=blocked)
        self.assertEqual(len(classes), 0)

    def test_saturday_classes_included(self):
        slots = [{"dayOfWeek": "Saturday", "startTime": "09:00", "endTime": "09:50", "subjectCode": "LABP", "subjectName": "Lab"}]
        classes = future_class_instances(slots, datetime(2026, 9, 1, 8), date(2026, 9, 5))
        self.assertEqual(len(classes), 1)

    def test_timetable_override_follow_day(self):
        slots = [{"dayOfWeek": "Monday", "startTime": "10:00", "endTime": "10:50", "subjectCode": "CS", "subjectName": "CS"}]
        overrides = [{"date": "2026-09-11", "follow_day_of_week": "Monday"}]
        classes = future_class_instances(slots, datetime(2026, 9, 8, 8), date(2026, 9, 14), timetable_overrides=overrides)
        dates = [c["date"] for c in classes]
        self.assertIn("2026-09-11", dates)

    def test_current_time_filters_today(self):
        slots = [{"dayOfWeek": "Thursday", "startTime": "10:00", "endTime": "10:50", "subjectCode": "CS", "subjectName": "CS"}]
        classes = future_class_instances(slots, datetime(2026, 9, 3, 11, 0), date(2026, 9, 3))
        self.assertEqual(len(classes), 0)

    def test_no_mutation_of_slots(self):
        slots = [{"dayOfWeek": "Monday", "startTime": "10:00", "endTime": "10:50", "subjectCode": "CS", "subjectName": "CS"}]
        original_slots = [dict(s) for s in slots]
        future_class_instances(slots, datetime(2026, 9, 3, 8), date(2026, 9, 10))
        self.assertEqual(slots, original_slots)