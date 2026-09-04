import unittest
from unittest.mock import patch

from fastapi import HTTPException
from api.routes import AdjustmentRequest, custom_adjustment


class Collection:
    def __init__(self, doc=None): self.doc, self.inserted = doc, []
    def find_one(self, *_args, **_kwargs): return self.doc
    def update_one(self, *_args, **_kwargs): pass
    def insert_one(self, value): self.inserted.append(value)


class Database:
    def __init__(self, count):
        self.users = Collection({"student_id": "student", "customAdjustmentMonth": "2026-08", "customAdjustmentCount": count})
        self.subjects = Collection({"_id": "subject", "subjectCode": "CS", "totalClasses": 10, "presentClasses": 8, "absentClasses": 2, "percentage": 80})
        self.adjustment_log = Collection()


class AdjustmentTests(unittest.TestCase):
    def test_monthly_adjustment_limit_is_enforced_server_side(self):
        db = Database(4)
        request = AdjustmentRequest(subject_code="CS", total_classes=11, present_classes=9)
        with patch("api.routes.get_database", return_value=db), patch("api.routes.date") as mocked_date:
            mocked_date.today.return_value.strftime.return_value = "2026-08"
            with self.assertRaises(HTTPException) as raised:
                custom_adjustment("student", request, {"student_id": "student"})
        self.assertEqual(raised.exception.status_code, 429)

    def test_invalid_adjustment_is_rejected_before_writing(self):
        request = AdjustmentRequest(subject_code="CS", total_classes=2, present_classes=3)
        with self.assertRaises(HTTPException) as raised:
            custom_adjustment("student", request, {"student_id": "student"})
        self.assertEqual(raised.exception.status_code, 422)
