import os
import sys

# Add app directory to path so 'services' and 'api' can be imported directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from datetime import date, datetime

from services.calculator import attendance_metrics
from services.prediction import future_class_instances


class PlannerMathTests(unittest.TestCase):
    def test_75_percent_calculations(self):
        self.assertEqual(attendance_metrics(100, 60)["classes_required_to_target"], 60)
        self.assertEqual(attendance_metrics(100, 80)["safe_bunks"], 6)
        self.assertEqual(attendance_metrics(4, 3)["safe_bunks"], 0)
        self.assertEqual(attendance_metrics(0, 0)["percentage"], 0)

    def test_same_start_time_is_not_a_future_class(self):
        slots = [{"dayOfWeek": "Monday", "startTime": "10:00", "endTime": "10:50", "subjectCode": "AI", "subjectName": "AI"}, {"dayOfWeek": "Monday", "startTime": "14:00", "endTime": "14:50", "subjectCode": "NET", "subjectName": "Networks"}]
        classes = future_class_instances(slots, datetime(2026, 8, 31, 10, 0), date(2026, 8, 31))
        self.assertEqual([item["subjectCode"] for item in classes], ["NET"])

    def test_custom_range_includes_saturday(self):
        slots = [{"dayOfWeek": "Saturday", "startTime": "09:00", "endTime": "09:50", "subjectCode": "LABP", "subjectName": "Lab"}]
        self.assertEqual(len(future_class_instances(slots, datetime(2026, 8, 28, 8), date(2026, 8, 29))), 1)
