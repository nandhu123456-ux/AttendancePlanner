import os
import sys

# Add app directory to path so 'services' and 'api' can be imported directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import unittest
from unittest.mock import Mock, patch

from services.gitam_portal import authenticate, fetch_current_data, parse_attendance_html, parse_subjects, parse_timetable


class Response:
    def __init__(self, url="https://glearn.gitam.edu", text="", headers=None, json_data=None, content=b""):
        self.url, self.text, self.headers, self._json = url, text, headers or {}, json_data
        self.content = content
        self.status_code = 200

    def raise_for_status(self): pass

    def json(self): return self._json


class PortalParsingTests(unittest.TestCase):
    def test_authentication_uses_one_session_across_gstudent_and_glearn(self):
        login_form = "".join(f"<input name='{name}' value='x'>" for name in ("__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION", "hiddenCsrfToken"))
        session = Mock()
        session.post.return_value = Response(headers={"Location": "/callback"})
        session.get.side_effect = [Response(text=login_form), Response(url="https://login.gitam.edu/callback"), Response(url="https://gstudent.gitam.edu/Home"), Response(text="window.location.href='https://glearn.gitam.edu/sso'"), Response(url="https://glearn.gitam.edu/sso"), Response(url="https://glearn.gitam.edu/student/std_dashboard_main")]
        with patch("services.gitam_portal.get_image_text", return_value="ABC123"):
            self.assertIs(authenticate("student", "password", session), session)
        self.assertEqual(session.get.call_count, 6)


    def test_fetches_subject_json_and_timetable_from_authenticated_glearn(self):
        session = Mock()
        dashboard = Response(url="https://glearn.gitam.edu/student/std_dashboard_main", text='<img src="https://doeresults.gitam.edu/photo/img.aspx?id=student%201">')
        report = Response(url="https://glearn.gitam.edu/student/std_attendance_report")
        subjects = Response(json_data=[{"subjectcode": "CS", "subjectname": "Networks", "total": 4, "p": 3}])
        table = "<table class='table table-bordered'><thead><tr><th>Session</th><th>Monday</th></tr></thead><tbody><tr><td>08:00 - 08:50</td><td>CS</td></tr></tbody></table>"
        session.get.side_effect = [dashboard, report, subjects, Response(url="https://glearn.gitam.edu/student/std_timetable", text=table)]
        data = fetch_current_data(session)
        self.assertEqual(data.subjects[0]["absentClasses"], 1)
        self.assertEqual(data.timetable[0]["subjectCode"], "CS")

    def test_timetable_failure_keeps_successful_attendance_available(self):
        session = Mock()
        dashboard = Response(url="https://glearn.gitam.edu/student/std_dashboard_main", text='<img src="https://doeresults.gitam.edu/photo/img.aspx?id=student">')
        report = Response(url="https://glearn.gitam.edu/student/std_attendance_report")
        subjects = Response(json_data=[{"subjectcode": "CS", "subjectname": "Networks", "total": 4, "p": 3}])
        session.get.side_effect = [dashboard, report, subjects, Response(url="https://glearn.gitam.edu/login")]
        data = fetch_current_data(session)
        self.assertIsNone(data.timetable)
        self.assertEqual(data.subjects[0]["subjectCode"], "CS")
    def test_subject_json_is_normalized_and_deduplicated(self):
        subjects = parse_subjects([
            {"subjectcode": "24CSEN2041", "subjectname": "Networks", "total": "19", "p": "16", "percentage": "bad"},
            {"subjectcode": "24CSEN2041", "subjectname": "Networks", "total": 20, "p": 25},
            {"subjectcode": "", "subjectname": "Ignored", "total": 1, "p": 1},
        ])
        self.assertEqual(subjects, [{"subjectCode": "24CSEN2041", "subjectName": "Networks", "totalClasses": 20, "presentClasses": 20, "absentClasses": 0, "percentage": 100.0}])

    def test_timetable_normalizes_slots_and_ignores_empty_cells(self):
        html = """<table class='table table-bordered'><thead><tr><th>Session</th><th>Monday</th><th>Saturday</th></tr></thead><tbody><tr><td>08:00 AM - 08:50 AM</td><td>24CSEN2041</td><td>-</td></tr></tbody></table>"""
        slots = parse_timetable(html, [{"subjectCode": "24CSEN2041", "subjectName": "Networks"}])
        self.assertEqual(slots, [{"dayOfWeek": "Monday", "startTime": "08:00", "endTime": "08:50", "subjectCode": "24CSEN2041", "subjectName": "Networks"}])

    def test_timetable_can_match_a_subject_name_when_code_is_not_rendered(self):
        html = """<table class='table table-bordered'><thead><tr><th>Session</th><th>Monday</th><th>Tuesday</th></tr></thead><tbody><tr><td>09:00 - 09:50</td><td>-</td><td>Computer Networks</td></tr></tbody></table>"""
        slots = parse_timetable(html, [{"subjectCode": "24CSEN2041", "subjectName": "Computer Networks"}])
        self.assertEqual(slots[0]["subjectCode"], "24CSEN2041")

    def test_attendance_html_parser_recovers_present_total_and_percentage(self):
        html = """<table class='table table-bordered'><thead><tr><th>Course Code</th><th>Course Name</th><th>Present</th><th>Total</th><th>Percentage</th></tr></thead><tbody>
<tr><td>24CSEN2041</td><td>Computer Networks</td><td>16</td><td>19</td><td>84.21</td></tr>
<tr><td>24CSEN2202P</td><td>Networks Lab</td><td>13</td><td>15</td><td>86.67</td></tr>
</tbody></table>"""
        subjects = parse_attendance_html(html)
        by_code = {s["subjectCode"]: s for s in subjects}
        self.assertEqual(by_code["24CSEN2041"]["presentClasses"], 16)
        self.assertEqual(by_code["24CSEN2041"]["totalClasses"], 19)
        self.assertEqual(by_code["24CSEN2041"]["percentage"], 84.21)
        self.assertEqual(by_code["24CSEN2202P"]["presentClasses"], 13)
        self.assertEqual(by_code["24CSEN2202P"]["totalClasses"], 15)
