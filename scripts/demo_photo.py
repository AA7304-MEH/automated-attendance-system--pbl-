#!/usr/bin/env python3
"""CLI demo — recognize faces in any photo and print a results table.

Usage:
    python scripts/demo_photo.py path/to/photo.jpg
    python scripts/demo_photo.py data/uploads/classroom_demo_hard.jpg

Prints one row per detected face (name | distance | confidence | status) and
saves a color-coded annotated copy under data/outputs/.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import (
    AUTO_APPROVE_DISTANCE, ENCODINGS_PATH, FACE_MATCH_TOLERANCE, OUTPUTS_DIR,
)
from face_engine.recognizer import FaceRecognizer


def main():
    ap = argparse.ArgumentParser(description="Recognize faces in a photo (CLI)")
    ap.add_argument("image", help="path to the classroom photo")
    ap.add_argument("--out", default=str(OUTPUTS_DIR), help="output dir for annotation")
    args = ap.parse_args()

    if not ENCODINGS_PATH.exists():
        sys.exit("No encodings found — enroll students first "
                 "(scripts/enroll_students.py --rebuild).")

    rec = FaceRecognizer(ENCODINGS_PATH, FACE_MATCH_TOLERANCE, AUTO_APPROVE_DISTANCE)
    results = rec.recognize(args.image)
    if not results:
        sys.exit("No faces detected in that photo.")

    print(f"\n{'#':<3} {'name':<10} {'distance':<10} {'confidence':<12} status")
    print("-" * 52)
    for i, r in enumerate(sorted(results, key=lambda r: (r.location[0], r.location[3]))):
        dist = "n/a" if r.distance is None else f"{r.distance:.3f}"
        conf = 0.0 if r.status == "unknown" else r.similarity
        print(f"{i:<3} {r.student_id:<10} {dist:<10} {conf:<12.1f} {r.status}")

    out = Path(args.out) / f"annotated_{Path(args.image).name}"
    rec.annotate(args.image, results, out)
    print(f"\n{len(results)} face(s) · annotated copy -> {out}")


if __name__ == "__main__":
    main()
