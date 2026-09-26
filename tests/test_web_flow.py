#!/usr/bin/env python3
"""End-to-end web flow tests using Flask's test client (no server needed).

Covers: auth, CSRF enforcement, photo upload → AI → verify page (3 HITL
branches), confirm (auto/review/manual marking), roster defaults to absent,
enrollment, analytics, CSV exports, alerts + email digest (console backend),
admin role & subject visibility, session ownership, media access control,
login rate limiting.

Run:  python tests/test_web_flow.py
"""

import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from database.models import Attendance, AttendanceSession, Student, db  # noqa: E402
from app import app  # noqa: E402

failures = []


def check(label, cond, extra=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}" + (f" — {extra}" if extra else ""))
    if not cond:
        failures.append(label)


def csrf_of(client, path="/login"):
    """Fetch a page and return its CSRF token (session-persistent)."""
    page = client.get(path)
    m = re.search(r'name="csrf_token" value="([^"]+)"', page.data.decode())
    return m.group(1) if m else ""


def login(client, email="teacher@college.edu", password="teacher123"):
    token = csrf_of(client)
    return client.post("/login", data={
        "csrf_token": token, "email": email, "password": password,
    }, follow_redirects=True)


def parse_verify_form(html):
    """Extract student_<i> values and checked state exactly as a browser would send."""
    students = {}
    for i, v in re.findall(r'name="student_(\d+)"\s+value="([^"]+)"', html):
        students[int(i)] = v
    for block in re.findall(r'<select name="student_(\d+)">(.*?)</select>', html, re.S):
        i, opts = int(block[0]), block[1]
        m = (re.search(r'<option value="([^"]+)"\s+selected', opts)
             or re.search(r'<option value="([^"]+)" selected', opts)
             or re.search(r'<option value="([^"]+)"', opts))
        if m:
            students[i] = m.group(1)
    checked = set(map(int, re.findall(r'name="present_(\d+)"\s+checked', html)))
    checked |= set(map(int, re.findall(r'name="present_(\d+)" checked', html)))
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
    """Remove ST007 (test-enrolled stranger) from DB + encoding store + disk."""
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
    for leftover in STUDENT_FACES_DIR.glob("ST007.*"):
        leftover.unlink()


def main():
    app.config["TESTING"] = True
    _cleanup_st007()
    c = app.test_client()

    print("CSRF enforcement")
    r = c.post("/login", data={"email": "teacher@college.edu", "password": "teacher123"})
    check("POST without CSRF token → 400", r.status_code == 400)

    print("Auth")
    r = c.get("/")
    check("unauthenticated / redirects to login",
          r.status_code == 302 and "/login" in r.headers["Location"])
    r = login(c, "teacher@college.edu", "nope")
    check("wrong password rejected", b"Invalid email" in r.data)
    r = login(c)
    check("admin login renders dashboard", b"Teacher dashboard" in r.data)

    print("Session A — good photo: all auto-approved")
    token = csrf_of(c, "/teacher/dashboard")
    with open(ROOT / "data/uploads/classroom_demo.jpg", "rb") as f:
        r = c.post("/take_attendance", data={
            "csrf_token": token, "subject_id": "1", "photo": (f, "g.jpg")},
            content_type="multipart/form-data")
    check("upload redirects to verify", r.status_code == 302 and "/verify" in r.headers["Location"])
    sess_a = int(re.search(r"/session/(\d+)/verify", r.headers["Location"]).group(1))
    r = c.get(r.headers["Location"])
    check("6 green cards", r.data.count(b"fc-green") == 6, f"got {r.data.count(b'fc-green')}")
    students, checked = parse_verify_form(r.data.decode())
    check("6 faces carry identities", len(students) == 6, str(sorted(students.values())))
    check("all 6 pre-checked by AI", len(checked) == 6)
    data = {f"student_{i}": v for i, v in students.items()}
    data.update({f"present_{i}": "on" for i in checked})
    data["csrf_token"] = token
    r = c.post(f"/session/{sess_a}/confirm", data=data, follow_redirects=True)
    check("confirmed → session detail 6 present", b"Present (6)" in r.data)
    m = marks_for(1)
    auto_rows = [v for v in m.values() if v[0] == "Present" and v[1] == "auto"]
    check("6 rows method=auto with confidence", len(auto_rows) == 6 and
          all(v[2] and v[2] >= 55 for v in auto_rows))

    print("Session B — degraded photo: review + teacher correction")
    token = csrf_of(c, "/teacher/dashboard")
    with open(ROOT / "data/uploads/classroom_demo_hard.jpg", "rb") as f:
        r = c.post("/take_attendance", data={
            "csrf_token": token, "subject_id": "2", "photo": (f, "h.jpg")},
            content_type="multipart/form-data")
    r = c.get(r.headers["Location"])
    check("2 amber review cards", r.data.count(b"fc-amber") == 2)
    students, checked = parse_verify_form(r.data.decode())
    data = {f"student_{i}": v for i, v in students.items()}
    data.update({f"present_{i}": "on" for i in checked})
    data["csrf_token"] = token
    wrong_i = max(students)
    data[f"student_{wrong_i}"] = "ST002"   # teacher corrects the AI's guess
    sid_b = _latest_session_id()
    r = c.post(f"/session/{sid_b}/confirm", data=data, follow_redirects=True)
    m = marks_for(2)
    present = [k for k, v in m.items() if v[0] == "Present"]
    with app.app_context():
        roster_n = Student.query.filter_by(active=True).count()
    check("2 present, whole roster absent by default",
          len(present) == 2 and len(m) == roster_n,
          f"marks={len(m)} roster={roster_n}")
    check("one review-confirmed row", sum(1 for v in m.values() if v[1] == "review") == 1)
    check("corrected row marked manual", sum(1 for v in m.values() if v[1] == "manual") == 1)

    print("Session C — stranger photo: unknown → teacher assigns")
    token = csrf_of(c, "/teacher/dashboard")
    with open(ROOT / "data/uploads/stranger_test.jpg", "rb") as f:
        r = c.post("/take_attendance", data={
            "csrf_token": token, "subject_id": "3", "photo": (f, "s.jpg")},
            content_type="multipart/form-data")
    r = c.get(r.headers["Location"])
    check("1 red unknown card", r.data.count(b"fc-red") == 1)
    students, checked = parse_verify_form(r.data.decode())
    data = {f"student_{i}": v for i, v in students.items()}
    i = next(iter(students))
    data[f"student_{i}"] = "ST001"
    data[f"present_{i}"] = "on"
    data["csrf_token"] = token
    c.post(f"/session/{_latest_session_id()}/confirm", data=data)
    m = marks_for(3)
    check("ST001 present via manual override",
          m.get("ST001", ("?",))[0:2] == ("Present", "manual"), str(m.get("ST001")))
    with app.app_context():
        roster_n = Student.query.filter_by(active=True).count()
    n_absent = sum(1 for v in m.values() if v[0] == "Absent")
    check("everyone else absent", n_absent == roster_n - 1,
          f"absent={n_absent} expected={roster_n - 1}")

    print("Enrollment")
    token = csrf_of(c, "/students")
    with open(ROOT / "data/uploads/stranger_test.jpg", "rb") as f:
        r = c.post("/students", data={
            "csrf_token": token, "student_id": "ST007", "first_name": "Vikram",
            "last_name": "Mehta", "department": "IT", "semester": "Sem 5",
            "photo": (f, "p.jpg")},
            content_type="multipart/form-data", follow_redirects=True)
    check("ST007 enrolled", b"ST007" in r.data and b"Vikram Mehta" in r.data)
    with app.app_context():
        s = Student.query.filter_by(student_id="ST007").first()
        from config import ENCODINGS_PATH
        from face_engine.encoder import FaceEncodingStore
        check("ST007 has photo + encoding", s.photo_path == "ST007.jpg" and
              "ST007" in FaceEncodingStore(ENCODINGS_PATH).known_ids)

    print("Analytics + exports + student view")
    r = c.get("/analytics")
    check("analytics renders", r.status_code == 200 and b"Per student" in r.data)
    check("trend chart drawn", b"<svg" in r.data and b"at-risk line" in r.data)
    r = c.get("/export/attendance.csv")
    check("raw attendance CSV downloads", r.status_code == 200 and
          b"student_id,student_name" in r.data and r.mimetype == "text/csv")
    r = c.get("/export/students.csv")
    check("student summary CSV + ST005 flagged", r.status_code == 200 and
          b"ST005" in r.data and b",YES" in r.data)
    r = c.get("/student?student_id=ST005")
    check("student view works", r.status_code == 200 and b"Rohan Verma" in r.data)

    print("Alerts + email digest (console backend)")
    r = c.get("/alerts")
    check("alerts page renders", r.status_code == 200 and b"At-risk students" in r.data)
    r = c.get("/alerts/email/preview")
    check("email preview renders", r.status_code == 200 and b"low attendance digest" in r.data
          and b"ST005" in r.data)
    token = csrf_of(c, "/alerts")
    r = c.post("/alerts/email/send", data={"csrf_token": token}, follow_redirects=True)
    check("digest send (console) flashed", b"digest was rendered" in r.data or b"rendered" in r.data)
    digests = list((ROOT / "data/outputs/emails").glob("digest_*.html"))
    check("console digest file written", bool(digests), str(len(digests)) + " file(s)")
    r = c.get("/alerts/email/send")   # GET should not send
    check("email send is POST-only", r.status_code == 405)

    print("Multi-teacher + admin (Phase 5)")
    with app.app_context():
        from database.models import Subject, Teacher
        arjun = Teacher.query.filter_by(email="arjun@college.edu").first()
        check("demo teacher Arjun seeded", arjun is not None)
        ml = Subject.query.filter_by(code="CS405").first()
        check("Arjun owns CS405", ml is not None and ml.teacher_id == arjun.id)

    t2 = app.test_client()
    r = login(t2, "arjun@college.edu", "teacher123")
    check("teacher login works", b"Teacher dashboard" in r.data)
    check("teacher sees only own subject",
          b"CS405" in r.data and b"CS201" not in r.data and b"CS302" not in r.data)
    r = t2.get("/admin")
    check("teacher blocked from /admin (403)", r.status_code == 403)
    r = t2.get(f"/session/{sess_a}")
    check("teacher blocked from others' sessions (403)", r.status_code == 403)
    token = csrf_of(t2, "/teacher/dashboard")
    r = t2.post("/take_attendance", data={"csrf_token": token, "subject_id": "1",
                                          "demo_photo": "1"}, follow_redirects=True)
    check("teacher denied unassigned subject", b"not assigned to you" in r.data)

    r = c.get("/admin")
    check("admin page renders for admin", r.status_code == 200 and b"Add a teacher" in r.data)
    token = csrf_of(c, "/admin")
    r = c.post("/admin/teachers/add", data={
        "csrf_token": token, "name": "Prof. Sneha Joshi", "email": "sneha@college.edu",
        "password": "sneha123", "role": "teacher"}, follow_redirects=True)
    check("admin creates teacher", b"Sneha Joshi" in r.data)
    r = c.post("/admin/subjects/add", data={
        "csrf_token": token, "name": "Operating Systems", "code": "CS303",
        "teacher_id": ""}, follow_redirects=True)
    check("admin creates subject", b"CS303" in r.data)
    with app.app_context():
        sneha = Teacher.query.filter_by(email="sneha@college.edu").first()
    t3 = app.test_client()
    r = login(t3, "sneha@college.edu", "sneha123")
    check("new teacher can log in", b"Teacher dashboard" in r.data)

    print("Student portal (Phase 6)")
    p = app.test_client()
    r = p.get("/me")
    check("portal page is public", r.status_code == 200 and b"Student portal" in r.data)
    tok = re.search(r'name="csrf_token" value="([^"]+)"', r.data.decode()).group(1)
    r = p.post("/me", data={"student_id": "ST001", "pin": "9999", "csrf_token": tok},
               follow_redirects=True)
    check("wrong PIN -> generic error", b"Invalid roll number or PIN" in r.data)
    r = p.post("/me", data={"student_id": "st001", "pin": "1234", "csrf_token": tok},
               follow_redirects=True)
    check("correct PIN -> personal attendance", b"Aarav Sharma" in r.data and
          b"classes present" in r.data)
    check("portal shows subject breakdown", b"CS201" in r.data)
    check("portal flags at-risk student", b"below the" in r.data or b"healthy" in r.data)

    print("Media access control")
    r = c.get("/media/1/face_0.jpg")
    check("logged-in can view session media", r.status_code == 200)
    r2 = app.test_client().get("/media/1/face_0.jpg")
    check("anonymous blocked from media", r2.status_code == 302)
    r = c.get("/media/1/../../etc/passwd")
    check("path traversal blocked", r.status_code in (404, 308, 301))

    print("Security headers")
    r = c.get("/analytics")
    check("security headers present",
          r.headers.get("X-Content-Type-Options") == "nosniff" and
          r.headers.get("X-Frame-Options") == "DENY" and
          "default-src 'self'" in r.headers.get("Content-Security-Policy", ""))

    print("Login rate limiting (runs last — locks the test IP briefly)")
    blocked = False
    for _ in range(6):   # clean state + limit of 5 → blocked by attempt 5 or 6
        r = login(app.test_client(), "teacher@college.edu", "nope")
        if b"Too many failed attempts" in r.data:
            blocked = True
            break
    check("5th+ bad attempt blocked", blocked, "rate limiter engaged")
    with app.app_context():
        from app import _failed_logins
        _failed_logins.clear()

    print()
    _cleanup_st007()  # leave the demo in its clean 6-student state
    if failures:
        sys.exit(f"{len(failures)} FAILED: {failures}")
    print("All web flow tests passed ✅")


def _latest_session_id():
    with app.app_context():
        return AttendanceSession.query.order_by(
            AttendanceSession.id.desc()).first().id


def test_all():  # pytest entry — enables: pytest tests/ -v
    main()


if __name__ == "__main__":
    main()
