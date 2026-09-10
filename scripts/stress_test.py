#!/usr/bin/env python3
"""Stress test — push a good photo through heavy degradation and show that the
Human-in-the-Loop policy reacts correctly:

  * faces that stay detectable but get less similar fall into the amber
    `needs_review` band (teacher must confirm) — never auto-approved;
  * faces too degraded to detect simply vanish (Phase 3 will let the teacher
    mark those students manually from a roster).

Run after the demo (needs data/face_encodings.pkl):
    python scripts/stress_test.py
"""

import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import (
    AUTO_APPROVE_DISTANCE,
    ENCODINGS_PATH,
    FACE_MATCH_TOLERANCE,
    OUTPUTS_DIR,
    UPLOADS_DIR,
)
from face_engine.recognizer import FaceRecognizer

GROUP_PHOTO = UPLOADS_DIR / "classroom_demo.jpg"


def degrade(img_bgr):
    """Simulate a bad classroom capture: small, blurred, dim, heavily compressed."""
    out = cv2.flip(img_bgr, 1)                                   # different viewpoint (mirror)
    out = cv2.resize(out, None, fx=0.55, fy=0.55)                # far away / low res
    out = cv2.GaussianBlur(out, (0, 0), 2.2)                     # defocus / motion blur
    out = np.clip(out.astype(np.float32) * 0.7 + 10, 0, 255)     # underexposure
    return out.astype(np.uint8)


def main():
    if not ENCODINGS_PATH.exists():
        sys.exit("No encodings found — run scripts/run_phase2_demo.py first.")

    hard_path = UPLOADS_DIR / "classroom_demo_hard.jpg"
    cv2.imwrite(str(hard_path), degrade(cv2.imread(str(GROUP_PHOTO))),
                [cv2.IMWRITE_JPEG_QUALITY, 45])

    rec = FaceRecognizer(ENCODINGS_PATH, FACE_MATCH_TOLERANCE, AUTO_APPROVE_DISTANCE)
    results = rec.recognize(hard_path)

    print(f"Degraded photo: {hard_path.name}")
    for r in sorted(results, key=lambda r: (r.location[0], r.location[3])):
        print(
            f"  {r.student_id:<8} similarity={r.similarity:5.1f}%  "
            f"distance={r.distance:.3f}  -> {r.status}"
        )
    counts = {}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1
    auto = counts.get("auto_approved", 0)
    print(f"  summary: {counts}")
    print(
        "  policy check:",
        "PASS ✅ (nothing degraded was auto-approved)"
        if auto == 0 else
        f"FAIL ❌ ({auto} degraded face(s) auto-approved — tighten AUTO_APPROVE_DISTANCE)",
    )
    out = rec.annotate(hard_path, results, OUTPUTS_DIR / "annotated_hard.jpg")
    print(f"  annotated: {Path(out).relative_to(ROOT)}")


if __name__ == "__main__":
    main()
