#!/usr/bin/env python3
"""Detection robustness probe — proof that the multi-scale detector finds
faces a single HOG pass misses.

Builds degraded copies of the demo classroom photo (tiny / tilted / dim /
blurred — the failure modes of real phone shots) and compares:

    OLD  = one face_recognition.face_locations() pass, upsample=1
    NEW  = face_engine.detector.detect_faces()  (bounded retry ladder)

Writes data/outputs/detect_probe.json for the report.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cv2
import face_recognition
import numpy as np

from face_engine.detector import detect_faces

GROUP = ROOT / "data" / "uploads" / "classroom_demo.jpg"
OUT_DIR = ROOT / "data" / "uploads" / "detect_probe"
OUT_JSON = ROOT / "data" / "outputs" / "detect_probe.json"


def variants(img):
    """Degraded copies simulating real failure modes of classroom phone shots."""
    h, w = img.shape[:2]
    out = {}

    # mild — single pass usually still copes
    tilted = cv2.resize(img, (int(w * 0.5), int(h * 0.5)), interpolation=cv2.INTER_AREA)
    th, tw = tilted.shape[:2]
    mat = cv2.getRotationMatrix2D((tw / 2, th / 2), 5, 1.0)
    out["tilted_5deg.jpg"] = cv2.warpAffine(tilted, mat, (tw, th),
                                            borderMode=cv2.BORDER_REPLICATE)

    # harsh — where single-pass HOG breaks down completely (0/6)
    cases = {}
    cases["ultra_tiny_18pct.jpg"] = cv2.resize(
        img, (int(w * 0.18), int(h * 0.18)), interpolation=cv2.INTER_AREA)
    small = cv2.resize(img, (int(w * 0.25), int(h * 0.25)), interpolation=cv2.INTER_AREA)
    sh, sw = small.shape[:2]
    m2 = cv2.getRotationMatrix2D((sw / 2, sh / 2), 9, 1.0)
    t2 = cv2.warpAffine(small, m2, (sw, sh), borderMode=cv2.BORDER_REPLICATE)
    cases["small_tilted_dim.jpg"] = (t2.astype(np.float64) * 0.55).astype(np.uint8)
    b = cv2.resize(img, (int(w * 0.22), int(h * 0.22)), interpolation=cv2.INTER_AREA)
    cases["small_blurred.jpg"] = cv2.GaussianBlur(b, (5, 5), 0)
    out.update(cases)
    return out


def main():
    img = cv2.imread(str(GROUP))
    if img is None:
        sys.exit(f"missing {GROUP}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    rows = []
    for name, v in variants(img).items():
        path = OUT_DIR / name
        cv2.imwrite(str(path), v, [cv2.IMWRITE_JPEG_QUALITY, 88])
        rgb = face_recognition.load_image_file(str(path))
        old = len(face_recognition.face_locations(rgb, number_of_times_to_upsample=1, model="hog"))
        new = len(detect_faces(path))
        rows.append({"variant": name, "old_single_pass": old, "new_robust": new})
        print(f"  {name:22} OLD {old}/6   NEW {new}/6")

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps({"source": "classroom_demo.jpg (6 faces)", "results": rows}, indent=2))
    gained = sum(r["new_robust"] - r["old_single_pass"] for r in rows)
    print(f"\nFaces recovered by the robust detector: +{gained} across {len(rows)} degraded shots")
    print(f"JSON -> {OUT_JSON}")


if __name__ == "__main__":
    main()
