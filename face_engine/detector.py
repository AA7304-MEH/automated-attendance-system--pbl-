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


def detect_faces(image_path, model="hog", upsample_times=1, num_jitters=1):
    """Detect all faces in an image and encode them.

    model: "hog" (fast, CPU) or "cnn" (GPU / more accurate).
    Returns a list of DetectedFace, ordered as face_recognition returns them.
    """
    image = face_recognition.load_image_file(str(image_path))
    locations = face_recognition.face_locations(
        image, number_of_times_to_upsample=upsample_times, model=model
    )
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
