"""Idempotent demo seeding + lightweight migrations.

Demo staff (all synthetic):
    Dr. Kavita Rao   admin   teacher@college.edu / teacher123
    Prof. Arjun Nair teacher arjun@college.edu   / teacher123  (owns CS405)

6 AI-generated students, 3 subjects, ~3 weeks of deterministic history
(ST005 is a chronic absentee so the at-risk views have real data).
Every demo student gets portal PIN "1234" (hashed).

Migrations for databases created in earlier phases:
    - teachers.role (Phase 5)
    - students.portal_pin (Phase 6) — backfilled with hash of "1234"
"""

import random
from datetime import date, time, timedelta

try:
    import fcntl  # Unix: file locking for race-safe seeding
except ImportError:  # pragma: no cover (Windows dev)
    fcntl = None
from sqlalchemy.exc import IntegrityError

from werkzeug.security import generate_password_hash

from config import DATA_DIR, ENCODINGS_PATH, STUDENT_FACES_DIR
from face_engine.encoder import FaceEncodingStore
from .models import db, Teacher, Student, Subject, Attendance

DEFAULT_PORTAL_PIN = "1234"

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


def _table_columns(conn, table):
    return [row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})")]


def _migrate(app):
    """Add columns introduced in later phases to pre-existing databases.
    PRAGMA migrations are SQLite-only; other dialects rely on create_all()."""
    if db.engine.dialect.name != "sqlite":
        _promote_and_backfill(app)
        return
    with db.engine.connect() as conn:
        cols = _table_columns(conn, "teachers")
        if "role" not in cols:
            conn.exec_driver_sql(
                "ALTER TABLE teachers ADD COLUMN role VARCHAR(10) "
                "NOT NULL DEFAULT 'teacher'"
            )
            conn.commit()
            app.logger.info("migrated teachers table: added role column")
        if "portal_pin" not in _table_columns(conn, "students"):
            conn.exec_driver_sql("ALTER TABLE students ADD COLUMN portal_pin VARCHAR(200)")
            conn.commit()
            app.logger.info("migrated students table: added portal_pin column")

    _promote_and_backfill(app)


def _promote_and_backfill(app):
    """Portable (any dialect): ensure an admin exists and students have PINs."""
    if not Teacher.query.filter_by(role="admin").first():
        first = Teacher.query.order_by(Teacher.id).first()
        if first:
            first.role = "admin"
            db.session.commit()

    stale = Student.query.filter(
        (Student.portal_pin.is_(None)) | (Student.portal_pin == "")
    ).all()
    if stale:
        hashed = generate_password_hash(DEFAULT_PORTAL_PIN)
        for s in stale:
            s.portal_pin = hashed
        db.session.commit()
        app.logger.info("backfilled portal PIN for %d student(s)", len(stale))


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


def _seed_locked(app):
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

        default_pin_hash = generate_password_hash(DEFAULT_PORTAL_PIN)
        students = []
        for sid, first, last, dept, sem in DEMO_STUDENTS:
            photo = f"{sid}.jpg" if (STUDENT_FACES_DIR / f"{sid}.jpg").exists() else None
            students.append(
                Student(
                    student_id=sid, first_name=first, last_name=last,
                    email=f"{sid.lower()}@college.edu", department=dept,
                    semester=sem, photo_path=photo,
                    portal_pin=default_pin_hash,
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


def seed_if_needed(app):
    """Race-safe wrapper around _seed_locked: when several WSGI workers boot
    at once, an exclusive file lock guarantees only one performs the seed
    (prevents UNIQUE constraint crashes on first deploy)."""
    lock_path = DATA_DIR / ".seed.lock"
    with open(lock_path, "a") as lock:
        if fcntl is not None:
            fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            return _seed_locked(app)
        except IntegrityError:
            # Lost a race despite the lock (e.g. multi-host volume) — the
            # other instance seeded; nothing for us to do.
            db.session.rollback()
            app.logger.warning("concurrent seeding detected — skipping")
            return False
        finally:
            if fcntl is not None:
                fcntl.flock(lock, fcntl.LOCK_UN)
