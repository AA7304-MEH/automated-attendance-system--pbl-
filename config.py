"""Central configuration for the Automated Student Attendance System.

Phase 1-2 (face engine) settings live here; Phase 3 will add Flask/DB config.
"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
STUDENT_FACES_DIR = DATA_DIR / "student_faces"   # enrollment portraits (<STUDENT_ID>.jpg)
UPLOADS_DIR = DATA_DIR / "uploads"               # classroom photos to process
OUTPUTS_DIR = DATA_DIR / "outputs"               # annotated images + reports

ENCODINGS_PATH = DATA_DIR / "face_encodings.pkl"  # the "face database"

# ---------------------------------------------------------------------------
# Face-recognition tuning (Human-in-the-Loop policy)
# ---------------------------------------------------------------------------
# face_recognition compares faces by Euclidean DISTANCE between 128-d encodings:
#   distance 0.0  = identical face,  larger = less similar.
#   similarity %  = (1 - distance) * 100
FACE_MATCH_TOLERANCE = 0.60   # distance <= this  -> declared the same person (dlib standard)
AUTO_APPROVE_DISTANCE = 0.45  # distance <= this  -> high confidence, auto-mark present
                              # between the two   -> AI suggests, teacher must confirm

DEFAULT_FACE_MODEL = "hog"    # "hog" = fast CPU detection | "cnn" = GPU, more accurate
NUM_JITTERS = 1               # encoding resampling; higher = slower but stabler

# Attendance below this % flags a student as at-risk (analytics + alerts)
ATTENDANCE_THRESHOLD = 75.0

# Web app
RUNTIME_UPLOADS_DIR = UPLOADS_DIR / "incoming"   # per-request classroom photos
WEB_SESSIONS_DIR = OUTPUTS_DIR / "web"           # face crops + annotated images
ALLOWED_IMAGE_EXTS = {".jpg", ".jpeg", ".png"}

# Created at import time so scripts can always write here.
for _d in (DATA_DIR, STUDENT_FACES_DIR, UPLOADS_DIR, OUTPUTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)
