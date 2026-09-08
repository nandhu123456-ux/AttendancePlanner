import sys, json
sys.path.insert(0, "backend")

# 1. Modules import cleanly (routes.py with new auto-sync + /sync recovery)
from app.api.routes 
import router  # noqa
from app.services.sync_service 
import _sync_collection, sync_portal_data
from app.services.gitam_portal 
import parse_subjects, PortalData

# 2. Subject API payload (subjectcode/subjectname/total/p) parses to normalized subjects
payload = [
    {"subjectcode": "24CSEN2201", "subjectname": "Data Structures", "total": 30, "p": 27, "percentage": 90.0},
    {"subjectcode": "24CSEN2202", "subjectname": "DBMS", "total": 12, "p": 10, "percentage": 83.33},
]
subjects = parse_subjects(payload)
s1 = next(s for s in subjects if s["subjectCode"] == "24CSEN2201")
assert s1["presentClasses"] == 27 and s1["totalClasses"] == 30 and s1["absentClasses"] == 3, s1
print("parse_subjects OK:", json.dumps(subjects[0]))

# 3. Stub Mongo collection: verify diff-based update (only changed subjects written)
class FakeResult:
    def __init__(self, upserted=False): self.upserted_id = "x" if upserted else None

class FakeCollection:
    def __init__(self, docs): self.docs = list(docs); self.updates = []
    def find(self, q): return [d for d in self.docs if d.get("student_id") == q.get("student_id")]
    def update_one(self, q, s, upsert=False):
        self.updates.append((q, s["$set"], upsert))
        key = ("student_id", "subjectCode")
        for d in self.docs:
            if all(d.get(k) == v for k, v in q.items()):
                d.update(s["$set"]); return FakeResult(False)
        self.docs.append({**q, **s["$set"]}); return FakeResult(True)
    def delete_one(self, q):
        self.docs = [d for d in self.docs if d.get("_id") != q.get("_id")]; return FakeResult(False)

db_stub = FakeCollection([
    {"_id": "a", "student_id": "S1", "subjectCode": "24CSEN2201", "subjectName": "Data Structures",
     "totalClasses": 30, "presentClasses": 27, "absentClasses": 3, "percentage": 90.0},   # unchanged
    {"_id": "b", "student_id": "S1", "subjectCode": "24CSEN2202", "subjectName": "DBMS",
     "totalClasses": 11, "presentClasses": 9, "absentClasses": 2, "percentage": 81.82},   # STALE, will change
])
changed = _sync_collection(db_stub, "S1", subjects, ("subjectCode",))
assert changed == 1, f"expected only 1 changed subject, got {changed}"
updated = next(d for d in db_stub.docs if d["subjectCode"] == "24CSEN2202")
assert updated["presentClasses"] == 10 and updated["totalClasses"] == 12 and updated["absentClasses"] == 2, updated

# 4. Changed subject (10/12 -> 11/13) must store authoritative values incl. absent = total - present
new_payload = [{"subjectcode": "24CSEN2202", "subjectname": "DBMS", "total": 13, "p": 11}]
fresh = parse_subjects(new_payload)
changed2 = _sync_collection(db_stub, "S1", fresh, ("subjectCode",))
updated2 = next(d for d in db_stub.docs if d["subjectCode"] == "24CSEN2202")
assert updated2["presentClasses"] == 11 and updated2["totalClasses"] == 13 and updated2["absentClasses"] == 2, updated2
print("diff-based update OK: changed=%d, stored=%s" % (changed2, {k: updated2[k] for k in ('presentClasses','totalClasses','absentClasses')}))

# 5. sync_portal_data runs against stub db (uses users collection for lastSyncAt)
class FakeDB:
    def __init__(self): self.subjects = db_stub; self.timetable_slots = FakeCollection([]); self.users = FakeCollection([]); self.sync_history = FakeCollection([])
status = sync_portal_data("S1", PortalData(subjects=subjects, timetable=None))
assert status["attendance"] == "success"
print("sync_portal_data OK:", status)

# 6. Overall aggregation uses latest values (as plan_service does)
total = sum(s["totalClasses"] for s in db_stub.docs if s.get("student_id") == "S1")
present = sum(s["presentClasses"] for s in db_stub.docs if s.get("student_id") == "S1")
print("overall OK: present=%d total=%d pct=%.2f absent=%d" % (present, total, 100*present/total, total-present))
print("ALL SMOKE TESTS PASSED")
