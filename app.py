"""Flask web app for the Automated Student Attendance System.

Flow (Human-in-the-Loop):
    teacher login → upload classroom photo → AI recognition (3-state policy)
    → verification page (auto ✅ / confirm 🔄 / assign ❓) → confirm
    → attendance written to SQLite → analytics & alerts → email digest.

Phases:
    3  web app: auth, upload, verification UI, attendance, analytics
    4  CSV exports, alerts dashboard, Docker
    5  email digests, multi-teacher + admin role, security hardening
       (CSRF tokens, security headers, login rate limiting)

Run:  python app.py   → http://localhost:8000  (binds 0.0.0.0)
Demo logins (seeded on first run):
    admin:   teacher@college.edu / teacher123
    teacher: arjun@college.edu   / teacher123
"""

import io
import json
import re
import secrets
import time
import uuid
from collections import defaultdict
from datetime import date, timedelta
from functools import wraps
from pathlib import Path

import cv2
import pandas as pd
from flask import (
    Flask, Response, abort, flash, redirect, render_template, request,
    send_from_directory, session, url_for,
)
from flask_login import (
    LoginManager, current_user, login_required, login_user, logout_user,
)
from werkzeug.security import check_password_hash, generate_password_hash

from config import (
    ALERT_RECIPIENTS, ATTENDANCE_THRESHOLD, AUTO_APPROVE_DISTANCE, BASE_DIR,
    DATA_DIR, ENCODINGS_PATH, FACE_MATCH_TOLERANCE, LOGIN_MAX_ATTEMPTS,
    LOGIN_WINDOW_SECONDS, RUNTIME_UPLOADS_DIR, STUDENT_FACES_DIR, UPLOADS_DIR,
    WEB_SESSIONS_DIR,
)
from database.models import (
    Attendance, AttendanceSession, Student, Subject, Teacher, db, now_ist,
)
from database.seed import seed_if_needed
from face_engine.detector import crop_face
from face_engine.encoder import FaceEncodingStore
from face_engine.recognizer import FaceRecognizer
from mailer import build_digest, send_digest
from reports import split_risk, student_pct, student_summary

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
DB_PATH = DATA_DIR / "attendance.db"

app = Flask(__name__)

_keyfile = BASE_DIR / ".secret_key"
if not _keyfile.exists():
    try:
        with open(_keyfile, "x") as _kf:
            _kf.write(secrets.token_hex(32))
    except FileExistsError:
        pass  # another worker created it first — read the same one below
app.config["SECRET_KEY"] = _keyfile.read_text()
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB upload cap
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

# Face engine — reload the encoding store automatically if the pkl changes
_engine = {"mtime": None, "recognizer": None}


def get_recognizer() -> FaceRecognizer:
    mtime = ENCODINGS_PATH.stat().st_mtime if ENCODINGS_PATH.exists() else None
    if _engine["recognizer"] is None or _engine["mtime"] != mtime:
        _engine["recognizer"] = FaceRecognizer(
            ENCODINGS_PATH, FACE_MATCH_TOLERANCE, AUTO_APPROVE_DISTANCE
        )
        _engine["mtime"] = mtime
    return _engine["recognizer"]


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Teacher, int(user_id))


with app.app_context():
    seed_if_needed(app)


# ---------------------------------------------------------------------------
# Security plumbing (Phase 5)
# ---------------------------------------------------------------------------
@app.before_request
def csrf_protect():
    """Reject any POST without the session's CSRF token."""
    if request.method == "POST":
        token = session.get("_csrf")
        if not token or request.form.get("csrf_token") != token:
            abort(400, description="CSRF token missing or invalid.")


def _csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_hex(32)
    return session["_csrf"]


app.context_processor(lambda: {"csrf_token": _csrf_token})


@app.after_request
def security_headers(resp):
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "same-origin")
    resp.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:",
    )
    return resp


# Naive per-IP login rate limiting (demo-grade; use Redis in real production)
_failed_logins = defaultdict(list)


def _prune_fails(ip):
    cutoff = time.time() - LOGIN_WINDOW_SECONDS
    _failed_logins[ip] = [t for t in _failed_logins[ip] if t > cutoff]


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if current_user.role != "admin":
            abort(403)
        return view(*args, **kwargs)
    return wrapped


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
ALLOWED_UPLOAD_EXTS = {".jpg", ".jpeg", ".png"}

def _save_upload(fileobj) -> Path:
    ext = Path(fileobj.filename).suffix.lower()
    if ext not in ALLOWED_UPLOAD_EXTS:
        raise ValueError("Only .jpg / .jpeg / .png photos are allowed.")
    path = RUNTIME_UPLOADS_DIR / f"{uuid.uuid4().hex}{ext}"
    fileobj.save(path)
    return path


def _visible_subjects():
    q = Subject.query.order_by(Subject.code)
    if current_user.role != "admin":
        q = q.filter_by(teacher_id=current_user.id)
    return q.all()


def _own_session(sess):
    return current_user.role == "admin" or sess.teacher_id == current_user.id




# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        ip = request.remote_addr or "unknown"
        _prune_fails(ip)
        if len(_failed_logins[ip]) >= LOGIN_MAX_ATTEMPTS:
            flash(
                f"Too many failed attempts — wait {LOGIN_WINDOW_SECONDS}s and try again.",
                "error",
            )
            return redirect(url_for("login"))
        teacher = Teacher.query.filter_by(
            email=request.form.get("email", "").strip().lower()
        ).first()
        if teacher and teacher.check_password(request.form.get("password", "")):
            _failed_logins.pop(ip, None)
            login_user(teacher, remember=True)
            return redirect(url_for("dashboard"))
        _failed_logins[ip].append(time.time())
        flash("Invalid email or password.", "error")
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Teacher dashboard + attendance flow
# ---------------------------------------------------------------------------
@app.route("/teacher/dashboard")
@login_required
def dashboard():
    subjects = _visible_subjects()
    today = now_ist().date()
    todays_marks = Attendance.query.filter_by(date=today).all()

    sess_q = AttendanceSession.query.order_by(AttendanceSession.created_at.desc())
    if current_user.role != "admin":
        sess_q = sess_q.filter_by(teacher_id=current_user.id)
    recent = sess_q.limit(8).all()

    recent_stats = {
        s.id: {
            "present": sum(1 for m in s.marks if m.status == "Present"),
            "total": len(s.marks),
        }
        for s in recent
    }
    return render_template(
        "teacher_dashboard.html",
        subjects=subjects,
        recent=recent,
        recent_stats=recent_stats,
        today_present=sum(1 for m in todays_marks if m.status == "Present"),
        today_total=len(todays_marks),
        threshold=ATTENDANCE_THRESHOLD,
    )


@app.route("/take_attendance", methods=["POST"])
@login_required
def take_attendance():
    subject = db.session.get(Subject, int(request.form.get("subject_id", 0)))
    if not subject:
        flash("Pick a subject first.", "error")
        return redirect(url_for("dashboard"))
    if subject.teacher_id != current_user.id and current_user.role != "admin":
        flash("That subject is not assigned to you.", "error")
        return redirect(url_for("dashboard"))

    if request.form.get("demo_photo"):
        # sandbox/demo convenience: analyze the bundled classroom photo directly
        photo_path = UPLOADS_DIR / "classroom_demo.jpg"
        if not photo_path.exists():
            flash("Demo photo not found on disk.", "error")
            return redirect(url_for("dashboard"))
    else:
        if "photo" not in request.files or request.files["photo"].filename == "":
            flash("Choose a classroom photo to upload.", "error")
            return redirect(url_for("dashboard"))
        try:
            photo_path = _save_upload(request.files["photo"])
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("dashboard"))

    # --- AI pass -----------------------------------------------------------
    recognizer = get_recognizer()
    results = recognizer.recognize(photo_path)
    if not results:
        flash("No faces detected in that photo — try a clearer, closer shot.", "error")
        return redirect(url_for("dashboard"))

    sess = AttendanceSession(
        subject_id=subject.id,
        teacher_id=current_user.id,
        photo_path=str(photo_path),
        status="pending",
        results_json="",
    )
    db.session.add(sess)
    db.session.commit()

    # --- crops + annotated image for the verify page ------------------------
    out_dir = WEB_SESSIONS_DIR / str(sess.id)
    out_dir.mkdir(parents=True, exist_ok=True)
    recognizer.annotate(photo_path, results, out_dir / "annotated.jpg")
    bgr = cv2.imread(str(photo_path))

    items, seen, dupes = [], set(), 0
    ordered = sorted(results, key=lambda r: (r.location[0], r.location[3]))
    for r in ordered:
        if r.student_id != "Unknown":
            if r.student_id in seen:      # same student detected twice → keep best
                dupes += 1
                continue
            seen.add(r.student_id)
        idx = len(items)
        crop = crop_face(bgr, r.location)
        cv2.imwrite(str(out_dir / f"face_{idx}.jpg"), crop)

        stu = Student.query.filter_by(student_id=r.student_id).first() \
            if r.student_id != "Unknown" else None
        items.append({
            "i": idx,
            "status": r.status,
            "ai_student_id": r.student_id,
            "similarity": r.similarity,
            "distance": r.distance,
            "crop": f"face_{idx}.jpg",
            "reg_name": stu.full_name if stu else None,
            "reg_photo": stu.photo_path if stu else None,
        })

    sess.results_json = json.dumps({
        "items": items,
        "annotated": "annotated.jpg",
        "faces_detected": len(ordered),
        "duplicates_ignored": dupes,
    })
    sess.created_at = now_ist()
    db.session.commit()
    return redirect(url_for("verify", sid=sess.id))


def _roster_options(unmatched, include=None):
    """Identity options for a face card: unmatched students (dicts), with the
    AI's current guess — which may be a matched student — placed first."""
    opts = [{"student_id": s.student_id, "full_name": s.full_name} for s in unmatched]
    if include and include not in [o["student_id"] for o in opts]:
        g = Student.query.filter_by(student_id=include).first()
        opts.insert(0, {"student_id": include,
                        "full_name": g.full_name if g else include})
    return opts


@app.route("/session/<int:sid>/verify")
@login_required
def verify(sid):
    sess = db.session.get(AttendanceSession, sid)
    if not sess or sess.status != "pending":
        abort(404)
    if not _own_session(sess):
        abort(403)
    data = json.loads(sess.results_json or "{}")
    items = data.get("items", [])

    matched = {it["ai_student_id"] for it in items if it["ai_student_id"] != "Unknown"}
    unmatched = Student.query.filter(
        Student.active.is_(True), ~Student.student_id.in_(matched)
    ).order_by(Student.student_id).all() if matched else \
        Student.query.filter_by(active=True).order_by(Student.student_id).all()

    for it in items:
        guess = it["ai_student_id"] if it["ai_student_id"] != "Unknown" else None
        it["options"] = _roster_options(unmatched, guess)

    counts = defaultdict(int)
    for it in items:
        counts[it["status"]] += 1

    return render_template(
        "verify_attendance.html",
        sess=sess,
        items=items,
        unmatched=unmatched,
        roster_total=Student.query.filter_by(active=True).count(),
        counts=dict(counts),
        annotated=data.get("annotated"),
        faces_detected=data.get("faces_detected", len(items)),
        threshold=ATTENDANCE_THRESHOLD,
    )


@app.route("/session/<int:sid>/confirm", methods=["POST"])
@login_required
def confirm(sid):
    sess = db.session.get(AttendanceSession, sid)
    if not sess or sess.status != "pending":
        abort(404)
    if not _own_session(sess):
        abort(403)
    data = json.loads(sess.results_json or "{}")
    items = data.get("items", [])
    today = now_ist().date()
    t = now_ist().time()

    # present: {student PK: (method, confidence)}
    present = {}

    for it in items:
        i = it["i"]
        chosen_sid = request.form.get(f"student_{i}", "").strip()
        if not chosen_sid or f"present_{i}" not in request.form:
            continue  # unchecked or unassigned → stays absent
        stu = Student.query.filter_by(student_id=chosen_sid, active=True).first()
        if not stu:
            continue
        if chosen_sid == it["ai_student_id"] and it["status"] in ("auto_approved", "needs_review"):
            method = "auto" if it["status"] == "auto_approved" else "review"
            conf = it["similarity"]
        else:
            method, conf = "manual", None
        present[stu.id] = (method, conf)

    # extra students the teacher marks present manually (undetected in photo)
    for sid_str in request.form.getlist("extra_present"):
        stu = Student.query.filter_by(student_id=sid_str, active=True).first()
        if stu and stu.id not in present:
            present[stu.id] = ("manual", None)

    # write Present marks
    for stu_id, (method, conf) in present.items():
        _upsert_mark(sess, stu_id, sess.subject_id, today, t,
                     "Present", method, conf, current_user.id)

    # everyone else in the roster → Absent
    for stu in Student.query.filter_by(active=True).all():
        if stu.id not in present:
            _upsert_mark(sess, stu.id, sess.subject_id, today, t,
                         "Absent", "system", None, current_user.id)

    sess.status = "verified"
    sess.decided_at = now_ist()
    db.session.commit()
    flash(f"Attendance saved — {len(present)} present, "
          f"{Student.query.filter_by(active=True).count() - len(present)} absent.", "ok")
    return redirect(url_for("session_detail", sid=sess.id))


def _upsert_mark(sess, stu_id, subject_id, day, t, status, method, conf, teacher_id):
    row = Attendance.query.filter_by(
        student_id=stu_id, subject_id=subject_id, date=day
    ).first()
    if row is None:
        row = Attendance(student_id=stu_id, subject_id=subject_id, date=day)
        db.session.add(row)
    row.session_id = sess.id
    row.time = t
    row.status = status
    row.method = method
    row.confidence = conf
    row.verified_by = teacher_id
    return row


@app.route("/session/<int:sid>")
@login_required
def session_detail(sid):
    sess = db.session.get(AttendanceSession, sid)
    if not sess:
        abort(404)
    if not _own_session(sess):
        abort(403)
    present = [m for m in sess.marks if m.status == "Present"]
    absent = [m for m in sess.marks if m.status == "Absent"]
    return render_template(
        "session_detail.html", sess=sess, present=present, absent=absent,
        results=json.loads(sess.results_json or "{}"),
    )


# ---------------------------------------------------------------------------
# Student management (enrollment)
# ---------------------------------------------------------------------------
@app.route("/students", methods=["GET", "POST"])
@login_required
def students():
    if request.method == "POST":
        first = request.form.get("first_name", "").strip()
        last = request.form.get("last_name", "").strip()
        sid = request.form.get("student_id", "").strip().upper()
        if not (first and last and sid):
            flash("First name, last name and roll number are required.", "error")
            return redirect(url_for("students"))
        if Student.query.filter_by(student_id=sid).first():
            flash(f"Roll number {sid} already exists.", "error")
            return redirect(url_for("students"))

        photo_file = request.files.get("photo")
        photo_name = None
        if photo_file and photo_file.filename:
            ext = Path(photo_file.filename).suffix.lower()
            if ext not in ALLOWED_UPLOAD_EXTS:
                flash("Portrait must be .jpg / .jpeg / .png.", "error")
                return redirect(url_for("students"))
            photo_name = f"{sid}{ext}"
            photo_file.save(STUDENT_FACES_DIR / photo_name)
            try:
                store = get_recognizer().store
                store.add_student(STUDENT_FACES_DIR / photo_name, sid)
                store.save()
            except ValueError as exc:
                (STUDENT_FACES_DIR / photo_name).unlink(missing_ok=True)
                flash(f"Face enrollment failed: {exc}", "error")
                return redirect(url_for("students"))

        pin = request.form.get("portal_pin", "").strip() or "1234"
        db.session.add(Student(
            student_id=sid, first_name=first, last_name=last,
            email=request.form.get("email", "").strip() or None,
            department=request.form.get("department", "").strip() or None,
            semester=request.form.get("semester", "").strip() or None,
            photo_path=photo_name,
            portal_pin=generate_password_hash(pin),
        ))
        db.session.commit()
        flash(f"Enrolled {first} {last} ({sid}) — face encoding saved.", "ok")
        return redirect(url_for("students"))

    roster = Student.query.filter_by(active=True).order_by(Student.student_id).all()
    marks = Attendance.query.all()
    by_student = defaultdict(list)
    for m in marks:
        by_student[m.student_id].append(m)

    roster_stats = {}
    for s in roster:
        pct, present, total = student_pct(by_student.get(s.id, []))
        roster_stats[s.id] = (pct, present, total)
    return render_template("students.html", roster=roster, stats=roster_stats,
                           threshold=ATTENDANCE_THRESHOLD)


# ---------------------------------------------------------------------------
# Analytics + student read-only view
# ---------------------------------------------------------------------------
@app.route("/analytics")
@login_required
def analytics():
    marks = Attendance.query.all()
    if not marks:
        return render_template("analytics.html", empty=True, threshold=ATTENDANCE_THRESHOLD)

    total = len(marks)
    present = sum(1 for m in marks if m.status == "Present")
    overall_pct = present / total * 100

    by_student = defaultdict(list)
    for m in marks:
        by_student[m.student_id].append(m)
    students = {s.id: s for s in Student.query.all()}
    student_stats = []
    for stu_id, rows in by_student.items():
        pct, p, t = student_pct(rows)
        student_stats.append({
            "student": students.get(stu_id), "pct": pct,
            "present": p, "total": t,
        })
    student_stats.sort(key=lambda x: -x["pct"])
    at_risk = [s for s in student_stats if s["pct"] < ATTENDANCE_THRESHOLD]

    by_subject = defaultdict(lambda: [0, 0])
    for m in marks:
        by_subject[m.subject_id][1] += 1
        if m.status == "Present":
            by_subject[m.subject_id][0] += 1
    subject_rows = [
        {"subject": db.session.get(Subject, s_id),
         "pct": v[0] / v[1] * 100 if v[1] else 0, "present": v[0], "total": v[1]}
        for s_id, v in by_subject.items()
    ]
    subject_rows.sort(key=lambda x: -(x["pct"] or 0))

    by_date = defaultdict(lambda: [0, 0])
    for m in marks:
        by_date[m.date][1] += 1
        if m.status == "Present":
            by_date[m.date][0] += 1
    trend = sorted(
        ({"date": d, "pct": v[0] / v[1] * 100} for d, v in by_date.items()),
        key=lambda x: x["date"],
    )

    today = now_ist().date()
    today_marks = [m for m in marks if m.date == today]
    today_present = sum(1 for m in today_marks if m.status == "Present")

    return render_template(
        "analytics.html",
        empty=False,
        overall_pct=overall_pct, total_marks=total, total_present=present,
        student_stats=student_stats, at_risk=at_risk, subject_rows=subject_rows,
        trend_svg=_trend_svg(trend),
        today_total=len(today_marks), today_present=today_present,
        today_pct=(today_present / len(today_marks) * 100) if today_marks else None,
        threshold=ATTENDANCE_THRESHOLD,
    )


def _trend_svg(trend, w=680, h=190, pad=34):
    """Dependency-free SVG line chart: daily attendance % over time."""
    if not trend:
        return ""
    pts = trend if len(trend) > 1 else [trend[0], trend[0]]
    n = len(pts)
    xs = [pad + i * (w - 2 * pad) / (n - 1) for i in range(n)]
    ys = [h - pad - (p["pct"] / 100) * (h - 2 * pad) for p in pts]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
    dots = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.4" fill="#3b6ef5">'
        f'<title>{p["date"].strftime("%d %b")}: {p["pct"]:.0f}%</title></circle>'
        for x, y, p in zip(xs, ys, pts)
    )
    grid = "".join(
        f'<line x1="{pad}" y1="{h - pad - v / 100 * (h - 2 * pad):.1f}" '
        f'x2="{w - pad}" y2="{h - pad - v / 100 * (h - 2 * pad):.1f}" '
        f'stroke="#e3e8f2" stroke-width="1"/>'
        f'<text x="{pad - 6}" y="{h - pad - v / 100 * (h - 2 * pad) + 4:.1f}" '
        f'text-anchor="end" font-size="10" fill="#8a93a8">{v}%</text>'
        for v in (0, 50, 100)
    )
    step = max(1, n // 8)
    labels = "".join(
        f'<text x="{x:.1f}" y="{h - 10}" text-anchor="middle" font-size="10" fill="#8a93a8">'
        f'{p["date"].strftime("%d %b")}</text>'
        for i, (x, p) in enumerate(zip(xs, pts))
        if i % step == 0 or i == n - 1
    )
    threshold_y = h - pad - ATTENDANCE_THRESHOLD / 100 * (h - 2 * pad)
    threshold_line = (
        f'<line x1="{pad}" y1="{threshold_y:.1f}" x2="{w - pad}" y2="{threshold_y:.1f}" '
        f'stroke="#d64545" stroke-width="1.4" stroke-dasharray="5 4"/>'
        f'<text x="{w - pad}" y="{threshold_y - 5:.1f}" text-anchor="end" '
        f'font-size="10" fill="#d64545">at-risk line {ATTENDANCE_THRESHOLD:.0f}%</text>'
    )
    return (
        f'<svg viewBox="0 0 {w} {h}" role="img" style="width:100%;height:auto">'
        f'{grid}{threshold_line}'
        f'<polyline points="{line}" fill="none" stroke="#3b6ef5" stroke-width="2.4"/>'
        f'{dots}{labels}</svg>'
    )


# ---------------------------------------------------------------------------
# Exports & alerts (Phase 4/5)
# ---------------------------------------------------------------------------
@app.route("/export/attendance.csv")
@login_required
def export_attendance():
    """Raw attendance log, one row per mark."""
    rows = (Attendance.query.join(Student, Attendance.student_id == Student.id)
            .join(Subject, Attendance.subject_id == Subject.id)
            .order_by(Attendance.date, Attendance.time).all())
    df = pd.DataFrame([{
        "date": r.date.isoformat(),
        "time": r.time.strftime("%H:%M"),
        "student_id": r.student.student_id,
        "student_name": r.student.full_name,
        "subject_code": r.subject.code,
        "subject": r.subject.name,
        "status": r.status,
        "method": r.method,
        "ai_confidence_pct": None if r.confidence is None else round(r.confidence, 1),
        "verified_by": current_user.name,
    } for r in rows])
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return Response(
        buf.getvalue(), mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=attendance_raw.csv"},
    )


@app.route("/alerts")
@login_required
def alerts():
    summary = student_summary()
    for s in summary:
        d = s["delta"]
        icon, color = ("→", "var(--muted)")
        if d >= 2:
            icon, color = ("▲ improving", "var(--green)")
        elif d <= -2:
            icon, color = ("▼ declining", "var(--red)")
        s["trend_icon"] = f'<span style="color:{color};font-weight:700">{icon}</span>'

    at_risk, borderline = split_risk(summary)
    return render_template("alerts.html", at_risk=at_risk, borderline=borderline,
                           threshold=ATTENDANCE_THRESHOLD)


@app.route("/alerts/email/preview")
@login_required
def email_preview():
    """Show exactly what the digest email looks like."""
    subject, _text, html = build_digest()
    return html


@app.route("/alerts/email/send", methods=["POST"])
@login_required
def email_send():
    recipients = ALERT_RECIPIENTS or [
        t.email for t in Teacher.query.all() if t.email
    ]
    status = send_digest(recipients)
    if status.startswith("console"):
        flash("Email backend is 'console' (no SMTP configured) — the digest was "
              "rendered to data/outputs/emails/. Set EMAIL_BACKEND=smtp + SMTP_* "
              "env vars for real delivery. Preview: Alerts → 'Preview email'.", "ok")
    elif status == "smtp:ok":
        flash(f"Digest emailed to {len(recipients)} recipient(s).", "ok")
    else:
        flash(f"Nothing sent: {status}", "error")
    return redirect(url_for("alerts"))



@app.route("/export/students.csv")
@login_required
def export_students():
    """Per-student summary with at-risk flag."""
    summary = student_summary()
    df = pd.DataFrame([{
        "student_id": s["student"].student_id,
        "name": s["student"].full_name,
        "department": s["student"].department or "",
        "semester": s["student"].semester or "",
        "classes_total": s["total"],
        "classes_present": s["present"],
        "attendance_pct": round(s["pct"], 1),
        "last7d_pct": round(s["recent_pct"], 1) if s["recent_total"] else "",
        "trend_vs_overall_pct": round(s["delta"], 1) if s["recent_total"] else "",
        "worst_subject": s["worst_subject"] or "",
        "at_risk": "YES" if s["pct"] < ATTENDANCE_THRESHOLD else "no",
    } for s in summary])
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return Response(
        buf.getvalue(), mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=students_summary.csv"},
    )


# ---------------------------------------------------------------------------
# Admin — teachers & subjects (Phase 5)
# ---------------------------------------------------------------------------
@app.route("/admin")
@admin_required
def admin():
    teachers = Teacher.query.order_by(Teacher.role, Teacher.name).all()
    subjects = Subject.query.order_by(Subject.code).all()
    return render_template("admin.html", teachers=teachers, subjects=subjects)


@app.route("/admin/teachers/add", methods=["POST"])
@admin_required
def admin_add_teacher():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    role = request.form.get("role", "teacher")
    if not (name and email and len(password) >= 6):
        flash("Name, email and a password of 6+ characters are required.", "error")
        return redirect(url_for("admin"))
    if Teacher.query.filter_by(email=email).first():
        flash("A user with that email already exists.", "error")
        return redirect(url_for("admin"))
    t = Teacher(name=name, email=email, role=role if role in ("admin", "teacher") else "teacher")
    t.set_password(password)
    db.session.add(t)
    db.session.commit()
    flash(f"Created {role}: {name} <{email}>", "ok")
    return redirect(url_for("admin"))


@app.route("/admin/subjects/add", methods=["POST"])
@admin_required
def admin_add_subject():
    name = request.form.get("name", "").strip()
    code = request.form.get("code", "").strip().upper()
    teacher_id = request.form.get("teacher_id", "").strip()
    if not (name and code):
        flash("Subject name and code are required.", "error")
        return redirect(url_for("admin"))
    if Subject.query.filter_by(code=code).first():
        flash(f"Subject code {code} already exists.", "error")
        return redirect(url_for("admin"))
    teacher = db.session.get(Teacher, int(teacher_id)) if teacher_id else None
    db.session.add(Subject(name=name, code=code, teacher_id=teacher.id if teacher else None))
    db.session.commit()
    flash(f"Added subject {code} — {name}" +
          (f" (assigned to {teacher.name})" if teacher else " (unassigned)"), "ok")
    return redirect(url_for("admin"))


@app.route("/admin/subjects/<int:sid>/assign", methods=["POST"])
@admin_required
def admin_assign_subject(sid):
    subject = db.session.get(Subject, sid)
    if not subject:
        abort(404)
    teacher_id = request.form.get("teacher_id", "").strip()
    subject.teacher_id = int(teacher_id) if teacher_id else None
    db.session.commit()
    teacher = db.session.get(Teacher, subject.teacher_id) if subject.teacher_id else None
    flash(f"{subject.code} reassigned to {teacher.name if teacher else 'nobody'}.", "ok")
    return redirect(url_for("admin"))


# ---------------------------------------------------------------------------
# Student self-service portal (Phase 6, public read-only)
# ---------------------------------------------------------------------------
@app.route("/me", methods=["GET", "POST"])
def student_portal():
    """Roll number + PIN -> read-only personal attendance. No staff login needed.

    PINs are stored hashed (demo default 1234, set at enrollment). Failed
    attempts share the per-IP login rate limit; failures never reveal whether
    the roll number exists.
    """
    if request.method == "POST":
        ip = request.remote_addr or "unknown"
        key = f"portal:{ip}"
        _prune_fails(key)
        if len(_failed_logins[key]) >= LOGIN_MAX_ATTEMPTS:
            flash(
                f"Too many attempts — wait {LOGIN_WINDOW_SECONDS}s and try again.",
                "error",
            )
            return redirect(url_for("student_portal"))
        sid = request.form.get("student_id", "").strip().upper()
        pin = request.form.get("pin", "").strip()
        student = Student.query.filter_by(student_id=sid, active=True).first()
        ok = False
        if student and student.portal_pin and pin:
            try:
                ok = check_password_hash(student.portal_pin, pin)
            except ValueError:
                ok = False
        if not ok:
            _failed_logins[key].append(time.time())
            flash("Invalid roll number or PIN.", "error")
            return redirect(url_for("student_portal"))
        _failed_logins.pop(key, None)

        rows = (Attendance.query.filter_by(student_id=student.id)
                .order_by(Attendance.date.desc(), Attendance.time.desc()).all())
        pct, present, total = student_pct(rows)
        per_subject = defaultdict(lambda: [0, 0])
        for m in rows:
            per_subject[m.subject_id][1] += 1
            if m.status == "Present":
                per_subject[m.subject_id][0] += 1
        subjects = {s.id: s for s in Subject.query.all()}
        subject_rows = sorted(
            ({"subject": subjects[s_id], "present": v[0], "total": v[1],
              "pct": v[0] / v[1] * 100 if v[1] else 0}
             for s_id, v in per_subject.items()),
            key=lambda x: -(x["pct"] or 0),
        )
        return render_template(
            "portal.html", student=student, rows=rows[:40],
            pct=pct, present=present, total=total,
            subject_rows=subject_rows, threshold=ATTENDANCE_THRESHOLD,
        )
    return render_template("portal.html", student=None)


# ---------------------------------------------------------------------------
# Student read-only view + secure media
# ---------------------------------------------------------------------------
@app.route("/student", methods=["GET"])
@login_required
def student_view():
    sid = request.args.get("student_id", "").strip().upper()
    student = Student.query.filter_by(student_id=sid).first() if sid else None
    rows = (
        Attendance.query.filter_by(student_id=student.id)
        .order_by(Attendance.date.desc(), Attendance.time.desc()).all()
        if student else []
    )
    pct, present, total = student_pct(rows)
    return render_template(
        "student_view.html", sid=sid, student=student, rows=rows,
        pct=pct, present=present, total=total, threshold=ATTENDANCE_THRESHOLD,
    )


@app.route("/media/<int:sid>/<name>")
@login_required
def media(sid, name):
    if not re.fullmatch(r"(face_\d+|annotated)\.(jpg|jpeg|png)", name):
        abort(404)
    return send_from_directory(WEB_SESSIONS_DIR / str(sid), name)


@app.route("/photo/<name>")
@login_required
def photo(name):
    if not re.fullmatch(r"ST\d+\.(jpg|jpeg|png)", name):
        abort(404)
    return send_from_directory(STUDENT_FACES_DIR, name)


if __name__ == "__main__":
    print("\n  Automated Student Attendance System — Phase 5")
    print("  admin login:   teacher@college.edu / teacher123")
    print("  teacher login: arjun@college.edu   / teacher123")
    print("  → http://0.0.0.0:8000\n")
    app.run(host="0.0.0.0", port=8000, debug=False)
