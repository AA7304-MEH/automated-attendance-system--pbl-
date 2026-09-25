#!/usr/bin/env python3
"""Bulk-enroll a dataset folder of portraits — dataset in, students + face
encodings out, ready for group-photo attendance.

Filename convention (flexible):
    <ROLLNO>_<First>_<Last>.jpg    e.g.  R101_Aarav_Sharma.jpg
    <ROLLNO>.jpg                   e.g.  R102.jpg   (name defaults to Student R102)

Usage (from the project root):
    python scripts/bulk_enroll.py path/to/dataset [--pin 1234] \
        [--department CSE] [--semester "TE-CSE"]

What it does per portrait:
  1. copies it to data/student_faces/<ROLLNO>.<ext>
  2. normalizes it (EXIF upright, RGB, 1600px) — same as the web enrollment
  3. encodes the face (robust detector: small/tilted portraits get retries)
  4. creates or updates the Student row in the database (hashed portal PIN)

Run a group photo through the web app afterwards — detected faces now match
these roll numbers and the teacher confirms them present.
"""

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import (  # noqa: E402
    Student,
    _normalize_photo,
    app as flask_app,
    db,
    generate_password_hash,
    get_recognizer,
)
from config import STUDENT_FACES_DIR  # noqa: E402

IMAGE_EXTS = {".jpg", ".jpeg", ".png"}


def parse_name(path):
    stem = path.stem.replace("-", "_").replace(" ", "_")
    parts = [p for p in stem.split("_") if p]
    roll = parts[0].upper()
    first = parts[1] if len(parts) > 1 else "Student"
    last = " ".join(parts[2:]) if len(parts) > 2 else roll
    return roll, first, last


def main():
    ap = argparse.ArgumentParser(description="Bulk-enroll portraits from a folder.")
    ap.add_argument("dataset", type=Path, help="folder of <ROLLNO>[_First_Last].jpg portraits")
    ap.add_argument("--pin", default="1234", help="portal PIN for all created students")
    ap.add_argument("--department", default=None)
    ap.add_argument("--semester", default=None)
    args = ap.parse_args()

    if not args.dataset.is_dir():
        sys.exit(f"Not a folder: {args.dataset}")
    files = sorted(p for p in args.dataset.iterdir()
                   if p.is_file() and p.suffix.lower() in IMAGE_EXTS)
    if not files:
        sys.exit(f"No .jpg/.jpeg/.png portraits found in {args.dataset}")

    ok, failed = 0, 0
    with flask_app.app_context():
        store = get_recognizer().store
        print(f"Enrolling {len(files)} portrait(s) from {args.dataset}:\n")
        for p in files:
            roll, first, last = parse_name(p)
            dest = STUDENT_FACES_DIR / f"{roll}{p.suffix.lower()}"
            shutil.copyfile(p, dest)
            _normalize_photo(dest, max_side=1600)
            try:
                store.add_student(dest, roll)
            except ValueError as exc:
                print(f"  [FACE FAIL] {roll:12} {first} {last} — {exc}")
                dest.unlink(missing_ok=True)
                failed += 1
                continue

            row = Student.query.filter_by(student_id=roll).first()
            if row:
                row.first_name, row.last_name, row.photo_path = first, last, dest.name
                action = "updated"
            else:
                row = Student(
                    student_id=roll, first_name=first, last_name=last,
                    department=args.department, semester=args.semester,
                    photo_path=dest.name,
                    portal_pin=generate_password_hash(args.pin),
                )
                action = "created"
            db.session.add(row)
            ok += 1
            print(f"  [OK {action:>7}] {roll:12} {first} {last}")

        store.save()
        db.session.commit()

    print(f"\nDone: {ok} enrolled, {failed} failed (no face found).")
    print("Encodings -> store saved. Now upload a classroom photo in the web app;")
    print("detected faces will carry these roll numbers for the teacher to confirm.")


if __name__ == "__main__":
    main()
