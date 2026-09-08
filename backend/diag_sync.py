"""TEMPORARY read-only diagnostic: last sync state + subjects vs snapshot consistency.
No writes, no secrets. Delete after use.
"""
import sys, os, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from datetime import datetime, timezone
from app.config.database import db

now = datetime.utcnow()
print("NOW (UTC):", now.isoformat())

targets = sys.argv[1:] or [d["student_id"] for d in db.users.find({}, {"student_id": 1})]
for sid in targets:
    subs = list(db.subjects.find({"student_id": sid}, {"_id": 0, "subjectCode": 1, "totalClasses": 1,
                                                       "presentClasses": 1, "absentClasses": 1, "percentage": 1, "updatedAt": 1}))
    db_p = sum(s.get("presentClasses", 0) for s in subs)
    db_t = sum(s.get("totalClasses", 0) for s in subs)
    by_code = {s["subjectCode"]: s for s in subs}
    user = db.users.find_one({"student_id": sid}, {"_id": 0, "lastSyncAt": 1, "last_sync_status": 1, "custom_target_date": 1})
    plan = db.planner_results.find_one({"student_id": sid}, {"_id": 0, "overall": 1, "generated_at": 1, "subjects": 1})
    o = (plan or {}).get("overall", {})
    print(f"\n== {sid}")
    print(f"   lastSyncAt={user.get('lastSyncAt')} status={user.get('last_sync_status')}")
    print(f"   subjects  : present={db_p} total={db_t} absent={db_t-db_p} docs={len(subs)}")
    if plan:
        print(f"   snapshot  : present={o.get('present_classes')} total={o.get('total_classes')} "
              f"absent={o.get('absent_classes')} cur={o.get('current_percentage')}% generated_at={plan.get('generated_at')}")
        mism = []
        snap_codes = set()
        for name, v in (plan.get("subjects") or {}).items():
            code = v.get("course_code"); snap_codes.add(code)
            s = by_code.get(code)
            if s is None:
                mism.append(f"{code}: snapshot-only")
            elif s.get("presentClasses") != v.get("present") or s.get("totalClasses") != v.get("conducted"):
                mism.append(f"{code}: snap(p={v.get('present')},t={v.get('conducted')}) != db(p={s.get('presentClasses')},t={s.get('totalClasses')})")
        for code in by_code:
            if code not in snap_codes:
                mism.append(f"{code}: db-only (missing from snapshot)")
        print(f"   mismatches: {mism if mism else 'NONE'}")
    else:
        print("   snapshot  : NONE")
    recent = [s for s in subs if s.get("updatedAt") and (now - s["updatedAt"]).total_seconds() < 3600]
    if recent:
        print(f"   subjects updated in last hour: {[s['subjectCode'] for s in recent]}")
