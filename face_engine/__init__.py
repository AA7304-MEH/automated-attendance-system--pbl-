"""face_engine — Phase 2 of the Automated Student Attendance System.

Public API:
    detect_faces(image_path)            -> [DetectedFace]
    crop_face(image_bgr, location)      -> cropped portrait (BGR)
    FaceEncodingStore(encodings_path)   -> enrollment / encoding database
    FaceRecognizer(encodings_path)      -> recognition with confidence + HITL statuses
"""

from .detector import DetectedFace, crop_face, detect_faces
from .encoder import FaceEncodingStore
from .recognizer import (
    AUTO_APPROVED,
    NEEDS_REVIEW,
    UNKNOWN,
    FaceRecognizer,
    Recognition,
)

__all__ = [
    "DetectedFace",
    "crop_face",
    "detect_faces",
    "FaceEncodingStore",
    "FaceRecognizer",
    "Recognition",
    "AUTO_APPROVED",
    "NEEDS_REVIEW",
    "UNKNOWN",
]
