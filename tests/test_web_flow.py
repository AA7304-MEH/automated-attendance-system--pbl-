#!/usr/bin/env python3
"""End-to-end web flow tests using Flask's test client (no server needed).

Covers: auth, photo upload → AI → verify page (3 HITL branches), confirm
(auto/review/manual marking), roster defaults to absent, enrollment,
analytics and the read-only student view.

Run:  python tests/test_web_flow.py
"""

import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from database.models import Attendance, Student, db  # noqa: E402
from app import app  # noqa: E402

failures = []


def check(label, cond, extra=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}" + (f" — {extra}" if extra else ""))
    if not cond:
        failures.append(label)


def login(client):
    return client.post("/login", data={
        "email": "teacher@college.edu", "password": "teacher123",
    }, follow_redirects=True)


def parse_verify_form(html):
    """Extract student_<i> values and checked state exactly as a browser would send."""
    students = {int(i): v for i, v in re.findall(r'name="student_(\d+)"[^>]*>\s*<option value="([^"]*)"',
                                                 html) } if False else {}
    # hidden inputs (auto cards)
    for i, v in re.findall(r'name="student_(\d+)"\s+value="([^"]+)"', html):
        students[int(i)] = v
    # selects: capture selected option per student_i
    for block in re.findall(r'<select name="student_(\d+)">(.*?)</select>', html, re.S):
        i, opts = int(block[0]), block[1]
        m = re.search(r'<option value="([^"]+)" selected', opts) or \
            re.search(r'<option value="([^"]+)"\s+selected', opts) or \
            re.search(r'option value="([^"]+)"[^>]*selected[^>]*>', opts)
        if m:
            students[i] = m.group(1)
        else:
            m = re.search(r'<option value="([^"]+)"', opts)
            if m:
                students[i] = m.group(1)
    checked = {int(i) for i in re.findall(r'name="present_(\d+)"\s+checked', html)}
    checked |= {int(i) for i in re.findall(r'name="present_(\d+)" checked', html)}
    return students, checked


def marks_for(subject_id):
    with app.app_context():
        rows = Attendance.query.filter_by(subject_id=subject_id).all()
        out = defaultdict(dict)
        for r in rows:
            s = db.session.get(Student, r.student_id)
            out[s.student_id] = (r.status, r.method, r.confidence)
        return dict(out)


def _cleanup_st007():
    """Remove ST007 (test-enrolled stranger) from DB + encoding store so the
    test is hermetic and the demo state stays clean between runs."""
    from config import ENCODINGS_PATH, STUDENT_FACES_DIR
    from face_engine.encoder import FaceEncodingStore
    with app.app_context():
        s = Student.query.filter_by(student_id="ST007").first()
        if s:
            Attendance.query.filter_by(student_id=s.id).delete()
            db.session.delete(s)
            db.session.commit()
    store = FaceEncodingStore(ENCODINGS_PATH)
    if "ST007" in store.known_ids:
        store.remove_student("ST007")
        store.save()
    for leftover in (STUDENT_FACES_DIR).glob("ST007.*"):
        leftover.unlink()


def main():
    app.config["TESTING"] = True
    _cleanup_st007()
    c = app.test_client()

    print("Auth")
    r = c.get("/")
    check("unauthenticated / redirects to login",
          r.status_code == 302 and "/login" in r.headers["Location"])
    r = c.post("/login", data={"email": "teacher@college.edu", "password": "nope"})
    check("wrong password rejected", b"Invalid email" in r.data)
    r = login(c)
    check("login renders dashboard", b"Teacher dashboard" in r.data)

    print("Session A — good photo: all auto-approved")
    with open(ROOT / "data/uploads/classroom_demo.jpg", "rb") as f:
        r = c.post("/take_attendance", data={"subject_id": "1", "photo": (f, "g.jpg")},
                   content_type="multipart/form-data")
    check("upload redirects to verify", r.status_code == 302 and "/verify" in r.headers["Location"])
    r = c.get(r.headers["Location"])
    check("6 green cards", r.data.count(b"fc-green") == 6, f"got {r.data.count(b'fc-green')}")
    students, checked = parse_verify_form(r.data.decode())
    check("6 faces carry identities", len(students) == 6, str(sorted(students.values())))
    check("all 6 pre-checked by AI", len(checked) == 6)
    data = {f"student_{i}": v for i, v in students.items()}
    data.update({f"present_{i}": "on" for i in checked})
    r = c.post(f"/session/{_sid(r)}/confirm", data=data, follow_redirects=True)
    check("confirmed → session detail 6 present", b"Present (6)" in r.data)
    m = marks_for(1)
    auto_rows = [v for v in m.values() if v[0] == "Present" and v[1] == "auto"]
    check("6 rows method=auto with confidence", len(auto_rows) == 6 and
          all(v[2] and v[2] >= 55 for v in auto_rows))

    print("Session B — degraded photo: review + teacher correction")
    with open(ROOT / "data/uploads/classroom_demo_hard.jpg", "rb") as f:
        r = c.post("/take_attendance", data={"subject_id": "2", "photo": (f, "h.jpg")},
                   content_type="multipart/form-data")
    r = c.get(r.headers["Location"])
    check("2 amber review cards", r.data.count(b"fc-amber") == 2)
    students, checked = parse_verify_form(r.data.decode())
    data = {f"student_{i}": v for i, v in students.items()}
    data.update({f"present_{i}": "on" for i in checked})
    # teacher corrects the face on card index max(i) to ST002 (not the AI guess)
    wrong_i = max(students)
    data[f"student_{wrong_i}"] = "ST002"
    sid_b = _sid(r)
    r = c.post(f"/session/{sid_b}/confirm", data=data, follow_redirects=True)
    m = marks_for(2)
    present = [k for k, v in m.items() if v[0] == "Present"]
    check("2 present, 4 absent by default", len(present) == 2 and len(m) == 6, str(m))
    review_rows = [v for v in m.values() if v[1] == "review"]
    manual_rows = [v for v in m.values() if v[1] == "manual"]
    check("one review-confirmed row", len(review_rows) == 1)
    check("corrected row marked manual", len(manual_rows) == 1)

    print("Session C — stranger photo: unknown → teacher assigns")
    with open(ROOT / "data/uploads/stranger_test.jpg", "rb") as f:
        r = c.post("/take_attendance", data={"subject_id": "3", "photo": (f, "s.jpg")},
                   content_type="multipart/form-data")
    r = c.get(r.headers["Location"])
    check("1 red unknown card", r.data.count(b"fc-red") == 1)
    students, checked = parse_verify_form(r.data.decode())
    data = {f"student_{i}": v for i, v in students.items()}
    i = next(iter(students))          # the single unknown face
    data[f"student_{i}"] = "ST001"    # teacher says it's ST001 (it is not — but that's the point)
    data[f"present_{i}"] = "on"
    c.post(f"/session/{_sid(r)}/confirm", data=data)
    m = marks_for(3)
    check("ST001 present via manual override", m.get("ST001", ("?",))[0:2] == ("Present", "manual"), str(m.get("ST001")))
    check("everyone else absent", sum(1 for v in m.values() if v[0] == "Absent") == 5)

    print("Enrollment")
    with open(ROOT / "data/uploads/stranger_test.jpg", "rb") as f:
        r = c.post("/students", data={
            "student_id": "ST007", "first_name": "Vikram", "last_name": "Mehta",
            "department": "IT", "semester": "Sem 5", "photo": (f, "p.jpg"),
        }, content_type="multipart/form-data", follow_redirects=True)
    check("ST007 enrolled", b"ST007" in r.data and b"Vikram Mehta" in r.data)
    with app.app_context():
        s = Student.query.filter_by(student_id="ST007").first()
        check("ST007 has photo + encoding", s.photo_path == "ST007.jpg" and
              "ST007" in __import__("face_engine.encoder", fromlist=["FaceEncodingStore"])
              .FaceEncodingStore(ROOT / "data/face_encodings.pkl").known_ids)

    print("Analytics + student view")
    r = c.get("/analytics")
    check("analytics renders", r.status_code == 200 and b"Per student" in r.data)
    check("trend chart drawn", b"<svg" in r.data and b"at-risk line" in r.data)
    r = c.get("/student?student_id=ST005")
    check("student view works", r.status_code == 200 and b"Rohan Verma" in r.data)
    r = c.get("/student?student_id=ST999")
    check("unknown roll handled", b"No student" in r.data)

    print("Exports & alerts (Phase 4)")
    r = c.get("/export/attendance.csv")
    check("raw attendance CSV downloads", r.status_code == 200 and
          b"student_id,student_name" in r.data and r.mimetype == "text/csv")
    check("CSV has data rows", r.data.count(b"Present") + r.data.count(b"Absent") > 10)
    r = c.get("/export/students.csv")
    check("student summary CSV downloads", r.status_code == 200 and
          b"attendance_pct" in r.data and b"ST005" in r.data)
    check("ST005 flagged at-risk in CSV",
          b"ST005" in r.data and b",YES" in r.data)
    r = c.get("/alerts")
    check("alerts page renders", r.status_code == 200 and b"At-risk students" in r.data)
    check("alerts lists ST005 with trend", b"ST005" in r.data and
          (b"improving" in r.data or b"declining" in r.data))
    r2 = app.test_client().get("/alerts")
    check("alerts auth-protected", r2.status_code == 302)

    print("Media access control")
    r = c.get("/media/1/face_0.jpg")
    check("logged-in can view session media", r.status_code == 200)
    r2 = app.test_client().get("/media/1/face_0.jpg")
    check("anonymous blocked from media", r2.status_code == 302)
    r = c.get("/media/1/../../etc/passwd")
    check("path traversal blocked", r.status_code in (404, 308, 301))

    print()
    _cleanup_st007()   # teardown: leave the demo in its clean 6-student state
    if failures:
        sys.exit(f"{len(failures)} FAILED: {failures}")
    print("All web flow tests passed ✅")


_confirm_urls = {}


def _sid(r):
    m = re.search(r"/session/(\d+)/verify", r.headers.get("Location", ""))
    if not m:  # already followed redirects; fall back to latest session
        with app.app_context():
            from database.models import AttendanceSession
            return AttendanceSession.query.order_by(AttendanceSession.id.desc()).first().id
    return int(m.group(1))


if __name__ == "__main__":
    main()
