"""Central configuration for the Automated Student Attendance System.

All thresholds, paths and integration settings live here.
Environment variables override defaults (see the Email / alerts block).
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
STUDENT_FACES_DIR = DATA_DIR / "student_faces"   # enrollment portraits (<STUDENT_ID>.jpg)
UPLOADS_DIR = DATA_DIR / "uploads"               # classroom photos to process
OUTPUTS_DIR = DATA_DIR / "outputs"               # annotated images + reports
EMAILS_DIR = OUTPUTS_DIR / "emails"              # rendered email digests (console backend)

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
# Students between THRESHOLD and THRESHOLD + BORDERLINE_BAND appear on the watch list
BORDERLINE_BAND = 10.0

# Web app
RUNTIME_UPLOADS_DIR = UPLOADS_DIR / "incoming"   # per-request classroom photos
WEB_SESSIONS_DIR = OUTPUTS_DIR / "web"           # face crops + annotated images
ALLOWED_IMAGE_EXTS = {".jpg", ".jpeg", ".png"}

# ---------------------------------------------------------------------------
# Email / alerts (Phase 5)
# ---------------------------------------------------------------------------
# EMAIL_BACKEND = "console"  -> digest is rendered to data/outputs/emails/ (demo mode,
#                               no credentials needed)
# EMAIL_BACKEND = "smtp"     -> real SMTP delivery (set the variables below)
EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "console")
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM = os.environ.get("SMTP_FROM", "autoattendance@college.edu")
# Optional comma-separated override; otherwise the digest goes to every teacher.
ALERT_RECIPIENTS = [e.strip() for e in os.environ.get("ALERT_RECIPIENTS", "").split(",") if e.strip()]

# Login brute-force protection: max failed attempts per IP per window
LOGIN_MAX_ATTEMPTS = 5
LOGIN_WINDOW_SECONDS = 60

# Created at import time so scripts can always write here.
for _d in (DATA_DIR, STUDENT_FACES_DIR, UPLOADS_DIR, OUTPUTS_DIR, EMAILS_DIR,
           RUNTIME_UPLOADS_DIR, WEB_SESSIONS_DIR):
    _d.mkdir(parents=True, exist_ok=True)
