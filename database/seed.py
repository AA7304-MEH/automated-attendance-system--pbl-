"""Idempotent demo seeding + lightweight migration.

Demo staff (all synthetic):
    Dr. Kavita Rao   admin   teacher@college.edu / teacher123
    Prof. Arjun Nair teacher arjun@college.edu   / teacher123  (owns CS405)

6 AI-generated students, 3 subjects, ~3 weeks of deterministic history
(ST005 is a chronic absentee so the at-risk views have real data).

Migration: databases created before Phase 5 lack teachers.role — we ALTER in
place and promote the first teacher to admin.
"""

import random
from datetime import date, time, timedelta

from config import ENCODINGS_PATH, STUDENT_FACES_DIR
from face_engine.encoder import FaceEncodingStore
from .models import db, Teacher, Student, Subject, Attendance

DEMO_ADMIN = {"name": "Dr. Kavita Rao", "email": "teacher@college.edu",
              "password": "teacher123", "role": "admin"}
DEMO_TEACHER2 = {"name": "Prof. Arjun Nair", "email": "arjun@college.edu",
                 "password": "teacher123", "role": "teacher"}

DEMO_STUDENTS = [
    ("ST001", "Aarav", "Sharma", "Computer Engineering", "Sem 5"),
    ("ST002", "Meera", "Iyer", "Computer Engineering", "Sem 5"),
    ("ST003", "Daniel", "D'Souza", "Information Technology", "Sem 5"),
    ("ST004", "Zoya", "Khan", "Computer Engineering", "Sem 5"),
    ("ST005", "Rohan", "Verma", "Information Technology", "Sem 5"),
    ("ST006", "Ananya", "Nair", "Computer Engineering", "Sem 5"),
]

# (name, code, owner: 'admin' | 'teacher2')
DEMO_SUBJECTS = [
    ("Data Structures", "CS201", "admin"),
    ("Database Systems", "CS302", "admin"),
    ("Machine Learning", "CS405", "teacher2"),
]

# per-student probability of attending a class (demo history flavour)
_PRESENT_PROB = {"ST001": 0.92, "ST002": 0.95, "ST003": 0.80, "ST004": 0.88,
                 "ST005": 0.55, "ST006": 0.90}


def ensure_encodings():
    """Make sure the pkl has an encoding for every demo portrait."""
    store = FaceEncodingStore(ENCODINGS_PATH)
    changed = False
    for sid, *_ in DEMO_STUDENTS:
        photo = STUDENT_FACES_DIR / f"{sid}.jpg"
        if photo.exists() and sid not in store.known_ids:
            store.add_student(photo, sid)
            changed = True
    if changed:
        store.save()
    return len(store)


def _migrate(app):
    """Add teachers.role to pre-Phase-5 databases and promote the first teacher."""
    with db.engine.connect() as conn:
        cols = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(teachers)")]
        if "role" not in cols:
            conn.exec_driver_sql(
                "ALTER TABLE teachers ADD COLUMN role VARCHAR(10) "
                "NOT NULL DEFAULT 'teacher'"
            )
            conn.commit()
            app.logger.info("migrated teachers table: added role column")
    if not Teacher.query.filter_by(role="admin").first():
        first = Teacher.query.order_by(Teacher.id).first()
        if first:
            first.role = "admin"
            db.session.commit()


def ensure_demo_staff(app):
    """Guarantee the two demo accounts + CS405 assignment exist (any DB age)."""
    changed = False
    admin = Teacher.query.filter_by(email=DEMO_ADMIN["email"]).first()
    if not admin:
        admin = Teacher(name=DEMO_ADMIN["name"], email=DEMO_ADMIN["email"],
                        role=DEMO_ADMIN["role"])
        admin.set_password(DEMO_ADMIN["password"])
        db.session.add(admin)
        db.session.flush()
        changed = True

    t2 = Teacher.query.filter_by(email=DEMO_TEACHER2["email"]).first()
    if not t2:
        t2 = Teacher(name=DEMO_TEACHER2["name"], email=DEMO_TEACHER2["email"],
                     role=DEMO_TEACHER2["role"])
        t2.set_password(DEMO_TEACHER2["password"])
        db.session.add(t2)
        db.session.flush()
        changed = True

    ml = Subject.query.filter_by(code="CS405").first()
    if ml and ml.teacher_id in (None, admin.id):
        ml.teacher_id = t2.id
        changed = True

    if changed:
        db.session.commit()
        app.logger.info("ensured demo staff accounts")
    return changed


def seed_if_needed(app):
    with app.app_context():
        db.create_all()
        _migrate(app)

        if Teacher.query.first():
            ensure_encodings()
            ensure_demo_staff(app)
            return False  # already seeded

        admin = Teacher(name=DEMO_ADMIN["name"], email=DEMO_ADMIN["email"],
                        role=DEMO_ADMIN["role"])
        admin.set_password(DEMO_ADMIN["password"])
        db.session.add(admin)
        db.session.flush()

        t2 = Teacher(name=DEMO_TEACHER2["name"], email=DEMO_TEACHER2["email"],
                     role=DEMO_TEACHER2["role"])
        t2.set_password(DEMO_TEACHER2["password"])
        db.session.add(t2)
        db.session.flush()

        owners = {"admin": admin, "teacher2": t2}
        subjects = [
            Subject(name=name, code=code, teacher_id=owners[owner].id)
            for name, code, owner in DEMO_SUBJECTS
        ]
        db.session.add_all(subjects)

        students = []
        for sid, first, last, dept, sem in DEMO_STUDENTS:
            photo = f"{sid}.jpg" if (STUDENT_FACES_DIR / f"{sid}.jpg").exists() else None
            students.append(
                Student(
                    student_id=sid, first_name=first, last_name=last,
                    email=f"{sid.lower()}@college.edu", department=dept,
                    semester=sem, photo_path=photo,
                )
            )
        db.session.add_all(students)
        db.session.flush()

        ensure_encodings()

        # ---- deterministic demo history: previous 14 weekdays x 3 subjects ----
        rng = random.Random(42)
        today = date.today()
        days = []
        d = today - timedelta(days=1)
        while len(days) < 14:
            if d.weekday() < 5:  # Mon-Fri only
                days.append(d)
            d -= timedelta(days=1)

        for day in days:
            for subj in subjects:
                for stu in students:
                    present = rng.random() < _PRESENT_PROB.get(stu.student_id, 0.85)
                    db.session.add(
                        Attendance(
                            session_id=None,
                            student_id=stu.id,
                            subject_id=subj.id,
                            date=day,
                            time=time(rng.randint(9, 16), rng.choice([0, 15, 30, 45])),
                            status="Present" if present else "Absent",
                            confidence=None,
                            method="manual",
                            verified_by=subj.teacher_id,
                        )
                    )
        db.session.commit()
        app.logger.info("Seeded 2 demo staff, %d subjects, %d students, "
                        "%d attendance rows", len(subjects), len(students),
                        len(days) * len(subjects) * len(students))
        return True
