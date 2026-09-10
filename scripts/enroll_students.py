#!/usr/bin/env python3
"""Enrollment CLI (Phase 2) — build the face-encoding database.

Run from the project root:

  python scripts/enroll_students.py --rebuild
      Rescan data/student_faces/ — every <STUDENT_ID>.jpg becomes an enrolled student.

  python scripts/enroll_students.py --add path/to/photo.jpg ST042
      Enroll one new student (or replace ST042's photo with a better one).

  python scripts/enroll_students.py --list
      Show everyone currently enrolled.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import ENCODINGS_PATH, STUDENT_FACES_DIR
from face_engine.encoder import FaceEncodingStore


def main():
    ap = argparse.ArgumentParser(
        description="Enroll students into the face-encoding database."
    )
    ap.add_argument(
        "--rebuild", action="store_true",
        help=f"rebuild the whole store from {STUDENT_FACES_DIR}",
    )
    ap.add_argument(
        "--add", nargs=2, metavar=("PHOTO", "STUDENT_ID"), action="append",
        help="enroll one portrait photo under a student id (repeatable)",
    )
    ap.add_argument("--list", action="store_true", help="list enrolled students")
    args = ap.parse_args()

    store = FaceEncodingStore(ENCODINGS_PATH)

    if args.rebuild:
        report = store.rebuild_from_dir(STUDENT_FACES_DIR)
        for sid, status in sorted(report.items()):
            print(f"  {sid:<10} {status}")
        ok = sum(1 for v in report.values() if v == "ok")
        print(f"\nEnrolled {ok} student(s) -> {ENCODINGS_PATH}")

    if args.add:
        for photo, sid in args.add:
            try:
                loc = store.add_student(photo, sid)
                print(f"  enrolled {sid} from {photo} (face box {loc})")
            except Exception as exc:
                sys.exit(f"  FAILED for {sid}: {exc}")
        store.save()
        print(f"  saved -> {ENCODINGS_PATH}")

    if args.list or not (args.rebuild or args.add):
        ids = sorted(store.known_ids)
        print(
            f"Enrolled students ({len(ids)}): "
            f"{', '.join(ids) if ids else '(none)'}"
        )


if __name__ == "__main__":
    main()
