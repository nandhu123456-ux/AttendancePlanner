"""MongoDB connection and collection constraints."""
import os

from pymongo import ASCENDING, MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URL = os.getenv("DATABASE_URL", "mongodb://localhost:27017/")
DATABASE_NAME = os.getenv("DATABASE_NAME", "attendance_planner")
client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
db = client[DATABASE_NAME]


def get_database():
    return db


def ensure_indexes():
    """Constraints for current, normalized portal data."""
    try:
        db.subjects.create_index([("student_id", ASCENDING), ("subjectCode", ASCENDING)], unique=True, name="subject_student_code")
        db.timetable_slots.create_index([("student_id", ASCENDING), ("dayOfWeek", ASCENDING), ("startTime", ASCENDING), ("endTime", ASCENDING), ("subjectCode", ASCENDING)], unique=True, name="timetable_slot_identity")
        db.planner_results.create_index("student_id", unique=True, name="planner_student")
        db.users.create_index("student_id", unique=True, name="user_student")
        db.adjustment_log.create_index([("student_id", ASCENDING), ("timestamp", ASCENDING)], name="adjustment_student_time")
    except Exception:
        # Index creation failures should not prevent the app from starting.
        # Indexes may already exist or the user may lack permissions.
        pass
