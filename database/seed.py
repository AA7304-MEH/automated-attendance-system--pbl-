"""Idempotent demo seeding: 1 teacher, 3 subjects, 6 students (the AI-generated
demo portraits), plus ~3 weeks of deterministic attendance history so the
analytics page is alive on first login. ST005 is deliberately a chronic
absentee so the at-risk list has a real entry.

Everything is synthetic demo data — no real people.
"""

import random
from datetime import date, time, timedelta

from config import ATTENDANCE_THRESHOLD, ENCODINGS_PATH, STUDENT_FACES_DIR
from face_engine.encoder import FaceEncodingStore
from .models import db, Teacher, Student, Subject, Attendance

DEMO_TEACHER = {"name": "Dr. Kavita Rao", "email": "teacher@college.edu", "password": "teacher123"}

DEMO_STUDENTS = [
    # (student_id, first, last, department, semester)
    ("ST001", "Aarav", "Sharma", "Computer Engineering", "Sem 5"),
    ("ST002", "Meera", "Iyer", "Computer Engineering", "Sem 5"),
    ("ST003", "Daniel", "D'Souza", "Information Technology", "Sem 5"),
    ("ST004", "Zoya", "Khan", "Computer Engineering", "Sem 5"),
    ("ST005", "Rohan", "Verma", "Information Technology", "Sem 5"),
    ("ST006", "Ananya", "Nair", "Computer Engineering", "Sem 5"),
]

DEMO_SUBJECTS = [
    ("Data Structures", "CS201"),
    ("Database Systems", "CS302"),
    ("Machine Learning", "CS405"),
]

# per-student probability of attending a class (demo history flavour)
_PRESENT_PROB = {"ST001": 0.92, "ST002": 0.95, "ST003": 0.80, "ST004": 0.88, "ST005": 0.55, "ST006": 0.90}


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


def seed_if_needed(app):
    with app.app_context():
        db.create_all()

        if Teacher.query.first():
            ensure_encodings()
            return False  # already seeded

        teacher = Teacher(name=DEMO_TEACHER["name"], email=DEMO_TEACHER["email"])
        teacher.set_password(DEMO_TEACHER["password"])
        db.session.add(teacher)
        db.session.flush()

        subjects = [
            Subject(name=name, code=code, teacher_id=teacher.id)
            for name, code in DEMO_SUBJECTS
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
                            verified_by=teacher.id,
                        )
                    )
        db.session.commit()
        app.logger.info("Seeded demo teacher/subjects/students + %d attendance rows", len(days) * 3 * len(students))
        return True
