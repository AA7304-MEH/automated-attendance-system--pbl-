"""SQLAlchemy models (Phase 3, extended in Phase 5).

Design note vs the blueprint: face encodings are NOT duplicated into the
students table. data/face_encodings.pkl (owned by face_engine) stays the
single source of truth for biometrics; the DB stores profile data and a
photo_path reference. One writer, no sync bugs.

Attendance rows record HOW each mark was made:
    method 'auto'    d <= 0.45, teacher may still uncheck (AI confident)
    method 'review'  0.45 < d <= 0.60, teacher confirmed the AI suggestion
    method 'manual'  teacher-assigned/overridden (no reliable AI match)
    method 'system'  absent rows (default for unmarked roster students)
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()
_IST = ZoneInfo("Asia/Kolkata")


def now_ist():
    return datetime.now(_IST)


class Teacher(UserMixin, db.Model):
    __tablename__ = "teachers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(10), default="teacher", nullable=False)  # teacher | admin

    subjects = db.relationship("Subject", backref="teacher", lazy=True)

    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):
        return check_password_hash(self.password_hash, raw)


class Student(db.Model):
    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(20), unique=True, nullable=False)  # roll no, e.g. ST001
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100))
    department = db.Column(db.String(50))
    semester = db.Column(db.String(20))
    photo_path = db.Column(db.String(200))          # filename inside data/student_faces/
    portal_pin = db.Column(db.String(200))          # hashed PIN for the /me self-service portal
    active = db.Column(db.Boolean, default=True, nullable=False)

    marks = db.relationship("Attendance", backref="student", lazy=True)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class Subject(db.Model):
    __tablename__ = "subjects"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teachers.id"))

    sessions = db.relationship("AttendanceSession", backref="subject", lazy=True)
    marks = db.relationship("Attendance", backref="subject", lazy=True)


class AttendanceSession(db.Model):
    """One classroom-photo upload (one recognition run + teacher decision)."""

    __tablename__ = "attendance_sessions"

    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teachers.id"), nullable=False)
    photo_path = db.Column(db.String(300))          # original upload (may be None for seeded history)
    results_json = db.Column(db.Text)               # AI output for the verify page
    status = db.Column(db.String(10), default="pending", nullable=False)  # pending | verified
    created_at = db.Column(db.DateTime, default=now_ist, nullable=False)
    decided_at = db.Column(db.DateTime)

    marks = db.relationship("Attendance", backref="session", lazy=True)


class Attendance(db.Model):
    __tablename__ = "attendance"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("attendance_sessions.id"), nullable=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.Time, nullable=False)
    status = db.Column(db.String(10), nullable=False)   # Present | Absent
    confidence = db.Column(db.Float)                    # AI similarity % (Present marks only)
    method = db.Column(db.String(10), default="system", nullable=False)
    verified_by = db.Column(db.Integer, db.ForeignKey("teachers.id"))
    created_at = db.Column(db.DateTime, default=now_ist, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("student_id", "subject_id", "date", name="uq_student_subject_date"),
    )
