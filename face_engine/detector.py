"""Face detection + cropping utilities (Phase 2).

Coordinate convention: face_recognition uses RGB images and (top, right,
bottom, left) boxes; OpenCV loads BGR. crop_face() expects the BGR image
you would get from cv2.imread().
"""

from dataclasses import dataclass
from pathlib import Path

import cv2
import face_recognition
import numpy as np


@dataclass
class DetectedFace:
    location: tuple        # (top, right, bottom, left)
    encoding: np.ndarray   # 128-d face encoding


def _rotate_image(img, angle):
    """Rotate an RGB numpy image about its center, edges replicated."""
    h, w = img.shape[:2]
    mat = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), angle, 1.0)
    return cv2.warpAffine(img, mat, (w, h), flags=cv2.INTER_CUBIC,
                          borderMode=cv2.BORDER_REPLICATE)


def _map_location(loc, scale, angle, orig_shape):
    """Map a (top, right, bottom, left) box from a transformed detection pass
    back to original-image coordinates. Returns None for degenerate boxes."""
    top, right, bottom, left = loc
    l, t, r, b = left / scale, top / scale, right / scale, bottom / scale
    if angle:
        h, w = orig_shape[:2]
        mat = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), angle, 1.0)
        inv = cv2.invertAffineTransform(mat)
        pts = inv @ np.array([[l, t, 1.0], [r, b, 1.0]], dtype=np.float64).T
        l, t, r, b = pts[0].min(), pts[1].min(), pts[0].max(), pts[1].max()
    H, W = orig_shape[:2]
    l, t = max(0, int(l)), max(0, int(t))
    r, b = min(W, int(r)), min(H, int(b))
    if r - l < 20 or b - t < 20:
        return None
    return (t, r, b, l)


def detect_faces(image_path, model="hog", upsample_times=1, num_jitters=1):
    """Detect all faces in an image and encode them (robust, bounded).

    Real classroom photos often contain small, dim or slightly tilted faces
    that a single HOG pass misses. We try a short ladder of detection passes
    and stop at the FIRST one that finds faces:

      1. native resolution, caller's upsample  (fast path - the usual case)
      2. native resolution, upsample=2         (small faces)
      3. 2x cubic upscale, upsample=1          (very small faces)
      4. 2x upscale +/- 6-degree tilt sweep    (casually tilted camera shots)

    Boxes found on transformed attempts are mapped back to original-image
    coordinates; encodings are ALWAYS computed from the original pixels, so
    they stay comparable with normally-enrolled portraits.

    model: "hog" (fast, CPU) or "cnn" (GPU / more accurate).
    Returns a list of DetectedFace, ordered as face_recognition returns them.
    """
    image = face_recognition.load_image_file(str(image_path))
    if image.ndim != 3 or max(image.shape[:2]) < 80:
        return []

    h, w = image.shape[:2]
    big = cv2.resize(image, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)
    attempts = [(image, 1.0, 0.0, upsample_times)]
    if upsample_times != 2:
        attempts.append((image, 1.0, 0.0, 2))
    attempts += [
        (big, 2.0, 0.0, 1),
        (_rotate_image(big, 6), 2.0, 6.0, 1),
        (_rotate_image(big, -6), 2.0, -6.0, 1),
    ]

    locations = []
    for img, scale, angle, ups in attempts:
        raw = face_recognition.face_locations(
            img, number_of_times_to_upsample=ups, model=model
        )
        mapped = [m for m in
                  (_map_location(loc, scale, angle, image.shape) for loc in raw)
                  if m]
        if len(mapped) > len(locations):
            locations = mapped
        if locations:
            break  # first successful pass wins — bounded CPU time

    encodings = face_recognition.face_encodings(image, locations, num_jitters=num_jitters)
    return [DetectedFace(loc, enc) for loc, enc in zip(locations, encodings)]


def crop_face(image_bgr, location, margin=0.25, target_size=(256, 256)):
    """Crop one face (with a margin) from a BGR image, resized to target_size."""
    top, right, bottom, left = location
    h, w = bottom - top, right - left
    mh, mw = int(h * margin), int(w * margin)
    t = max(0, top - mh)
    b = min(image_bgr.shape[0], bottom + mh)
    l = max(0, left - mw)
    r = min(image_bgr.shape[1], right + mw)
    crop = image_bgr[t:b, l:r].copy()
    if crop.size == 0:
        return crop
    return cv2.resize(crop, target_size)
