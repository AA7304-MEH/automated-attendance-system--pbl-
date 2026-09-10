#!/usr/bin/env python3
"""Functional tests for the Phase 2 face engine (no pytest needed).

Run the Phase 2 demo first (it creates the demo data), then:
    python tests/test_face_engine.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import (
    AUTO_APPROVE_DISTANCE,
    ENCODINGS_PATH,
    FACE_MATCH_TOLERANCE,
    STUDENT_FACES_DIR,
    UPLOADS_DIR,
)
from face_engine.encoder import FaceEncodingStore
from face_engine.recognizer import FaceRecognizer

failures = []


def check(name, cond, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        failures.append(name)


def main():
    portraits = sorted(p for p in STUDENT_FACES_DIR.glob("*.jpg"))
    if not portraits:
        sys.exit("No enrolled portraits found — run scripts/run_phase2_demo.py first.")

    print("Test 1 — every portrait yields a 128-d encoding")
    store = FaceEncodingStore(ENCODINGS_PATH)
    for p in portraits:
        enrolled = p.stem in store.known_ids
        dim_ok = False
        if enrolled:
            e = store.known_encodings[store.known_ids.index(p.stem)]
            dim_ok = len(e) == 128
        check(f"portrait {p.name}", enrolled and dim_ok)

    print("Test 2 — recognizer re-identifies every enrolled student in the original photo")
    rec = FaceRecognizer(ENCODINGS_PATH, FACE_MATCH_TOLERANCE, AUTO_APPROVE_DISTANCE)
    group = UPLOADS_DIR / "classroom_demo.jpg"
    results = rec.recognize(group)
    found = {r.student_id for r in results if r.status != "unknown"}
    check(
        "all enrolled students matched",
        set(store.known_ids) <= found,
        f"matched={sorted(found)}",
    )

    print("Test 3 — augmented (flipped/dimmed/recompressed) photo still recognized")
    aug = UPLOADS_DIR / "classroom_demo_augmented.jpg"
    if aug.exists():
        res2 = rec.recognize(aug)
        found2 = {r.student_id for r in res2 if r.status != "unknown"}
        check(
            ">= 80% matched on augmented photo",
            len(found2) >= 0.8 * len(store.known_ids),
            f"matched={len(found2)}/{len(store.known_ids)}",
        )

    print("Test 4 — a stranger is never auto-approved")
    stranger = UPLOADS_DIR / "stranger_test.jpg"
    if stranger.exists():
        res3 = rec.recognize(stranger)
        check(
            "stranger not auto-approved",
            all(r.status != "auto_approved" for r in res3),
            ", ".join(f"{r.student_id}:{r.status}" for r in res3) or "no faces found",
        )

    print()
    if failures:
        sys.exit(f"{len(failures)} test(s) FAILED: {failures}")
    print("All tests passed ✅")


if __name__ == "__main__":
    main()
