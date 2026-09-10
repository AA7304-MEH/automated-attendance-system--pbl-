#!/usr/bin/env python3
"""Phase 2 end-to-end demo — proves the face engine works before any web code.

Pipeline:
  1. Detect faces in data/uploads/classroom_demo.jpg (group photo).
  2. Save each face crop as an enrollment portrait data/student_faces/ST00x.jpg.
  3. Build the encoding database data/face_encodings.pkl.
  4. Recognize faces on an AUGMENTED copy of the photo (flipped + dimmed +
     shrunk + recompressed) so matching is non-trivial. Annotate results.
  5. Leave-one-out check: remove one student from the store and verify their
     face is NOT matched (proves discrimination, not just "everything passes").
  6. Unknown-face check with data/uploads/stranger_test.jpg.

Outputs -> data/outputs/: annotated_full.jpg, annotated_leave_one_out.jpg,
annotated_stranger.jpg, phase2_report.json
"""

import json
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
    STUDENT_FACES_DIR,
    UPLOADS_DIR,
)
from face_engine.detector import crop_face, detect_faces
from face_engine.encoder import FaceEncodingStore
from face_engine.recognizer import FaceRecognizer

GROUP_PHOTO = UPLOADS_DIR / "classroom_demo.jpg"
STRANGER_PHOTO = UPLOADS_DIR / "stranger_test.jpg"


def augment(img_bgr):
    """Make the test photo harder than the enrollment crops (simulates a
    different capture: mirrored, smaller, dimmer, heavy JPEG recompression)."""
    out = cv2.flip(img_bgr, 1)
    out = cv2.resize(out, None, fx=0.85, fy=0.85)
    out = np.clip(out.astype(np.float32) * 0.82, 0, 255).astype(np.uint8)
    return out


def print_results(title, results):
    print(f"\n  {title}")
    print(f"  {'-' * len(title)}")
    for r in sorted(results, key=lambda r: (r.location[0], r.location[3])):
        name = r.student_id if r.status != "unknown" else "Unknown"
        print(
            f"    box(top={r.location[0]:>3}, left={r.location[3]:>3})  "
            f"{name:<8} similarity={r.similarity:5.1f}%  distance="
            f"{'  — ' if r.distance is None else f'{r.distance:.3f}'}  {r.status}"
        )


def main():
    if not GROUP_PHOTO.exists():
        sys.exit(f"Missing {GROUP_PHOTO} — add a classroom group photo first.")
    if not STRANGER_PHOTO.exists():
        print(f"NOTE: {STRANGER_PHOTO.name} not found — skipping unknown-face test.")

    print("=" * 64)
    print("PHASE 2 DEMO — face recognition engine, end to end")
    print("=" * 64)

    # 1 ── detect faces in the group photo, save crops as portraits --------
    print("\n[1/5] Detecting faces in the group photo ...")
    faces = detect_faces(GROUP_PHOTO)
    print(f"      -> {len(faces)} face(s) detected")
    if len(faces) < 2:
        sys.exit("Need at least 2 faces in the group photo for a meaningful demo.")

    img_bgr = cv2.imread(str(GROUP_PHOTO))
    student_ids = []
    for i, f in enumerate(sorted(faces, key=lambda f: (f.location[0], f.location[3])), start=1):
        sid = f"ST{i:03d}"
        cv2.imwrite(str(STUDENT_FACES_DIR / f"{sid}.jpg"), crop_face(img_bgr, f.location))
        student_ids.append(sid)
    print(f"      -> enrollment portraits saved: {', '.join(student_ids)}")

    # 2 ── enroll (compute 128-d encodings) --------------------------------
    print("\n[2/5] Enrolling students (computing 128-d encodings) ...")
    store = FaceEncodingStore(ENCODINGS_PATH)
    for sid in student_ids:
        store.add_student(STUDENT_FACES_DIR / f"{sid}.jpg", sid)
    store.save()
    print(f"      -> {len(store)} students in {ENCODINGS_PATH.name}")

    # 3 ── recognize on augmented copy --------------------------------------
    print("\n[3/5] Recognizing faces on an AUGMENTED copy of the photo ...")
    aug_path = UPLOADS_DIR / "classroom_demo_augmented.jpg"
    cv2.imwrite(str(aug_path), augment(img_bgr), [cv2.IMWRITE_JPEG_QUALITY, 70])
    recognizer = FaceRecognizer(ENCODINGS_PATH, FACE_MATCH_TOLERANCE, AUTO_APPROVE_DISTANCE)
    results = recognizer.recognize(aug_path)
    print_results("Results (augmented group photo)", results)
    recognizer.annotate(aug_path, results, OUTPUTS_DIR / "annotated_full.jpg")
    print("      -> annotated image: data/outputs/annotated_full.jpg")

    # 4 ── leave-one-out honesty check --------------------------------------
    print("\n[4/5] Leave-one-out check (is matching real, or trivially easy?) ...")
    loo_id = student_ids[-1]
    tmp_store = OUTPUTS_DIR / "_loo_store.pkl"
    partial = FaceEncodingStore(tmp_store)
    for e, i in zip(store.known_encodings, store.known_ids):
        if i != loo_id:
            partial.known_encodings.append(e)
            partial.known_ids.append(i)
    partial.save()
    loo_rec = FaceRecognizer(tmp_store, FACE_MATCH_TOLERANCE, AUTO_APPROVE_DISTANCE)
    loo_results = loo_rec.recognize(aug_path)
    print_results(f"Results (store WITHOUT {loo_id})", loo_results)
    loo_not_matched = all(r.student_id != loo_id for r in loo_results)
    print(
        f"      -> {loo_id} not matched by the 5-student store: "
        f"{'PASS ✅' if loo_not_matched else 'FAIL ❌'}"
    )
    loo_rec.annotate(aug_path, loo_results, OUTPUTS_DIR / "annotated_leave_one_out.jpg")
    tmp_store.unlink(missing_ok=True)

    # 5 ── stranger must not be auto-approved --------------------------------
    print("\n[5/5] Unknown-face check ...")
    stranger_results = None
    if STRANGER_PHOTO.exists():
        stranger_results = recognizer.recognize(STRANGER_PHOTO)
        print_results("Results (stranger portrait)", stranger_results)
        recognizer.annotate(STRANGER_PHOTO, stranger_results, OUTPUTS_DIR / "annotated_stranger.jpg")

    # summary + report --------------------------------------------------------
    n_auto = sum(1 for r in results if r.status == "auto_approved")
    n_review = sum(1 for r in results if r.status == "needs_review")
    n_unknown = sum(1 for r in results if r.status == "unknown")
    print("\n" + "=" * 64)
    print(
        f"AUGMENTED PHOTO: {len(results)} faces | auto-approved: {n_auto} | "
        f"needs review: {n_review} | unknown: {n_unknown}"
    )
    print(f"LEAVE-ONE-OUT ({loo_id}): {'PASS' if loo_not_matched else 'FAIL'}")
    if stranger_results:
        print(
            "STRANGER: "
            + ", ".join(f"{r.student_id} ({r.status})" for r in stranger_results)
        )
    print("=" * 64)

    report = {
        "thresholds": {
            "match_tolerance": FACE_MATCH_TOLERANCE,
            "auto_approve_distance": AUTO_APPROVE_DISTANCE,
        },
        "enrolled_students": student_ids,
        "faces_detected_in_group_photo": len(faces),
        "augmented_photo_results": [r.to_dict() for r in results],
        "leave_one_out": {
            "removed": loo_id,
            "not_matched": bool(loo_not_matched),
            "results": [r.to_dict() for r in loo_results],
        },
        "stranger": None if stranger_results is None else [r.to_dict() for r in stranger_results],
    }
    out_json = OUTPUTS_DIR / "phase2_report.json"
    out_json.write_text(json.dumps(report, indent=2))
    print(f"JSON report: {out_json}")


if __name__ == "__main__":
    main()
