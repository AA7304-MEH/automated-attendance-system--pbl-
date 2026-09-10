"""Phase 2 — Enrollment: build & manage the face-encoding database.

A student is "enrolled" when we store a 128-dimension face encoding computed
from their registration photo. Recognition later compares detected faces
against these encodings.

Storage format (pickle, blueprint-compatible keys):
    {"encodings": [np.ndarray(128), ...], "names": ["ST001", ...]}
"""

import pickle
from pathlib import Path

import face_recognition
import numpy as np

from .detector import detect_faces

IMAGE_EXTS = {".jpg", ".jpeg", ".png"}


class FaceEncodingStore:
    def __init__(self, encodings_path):
        self.encodings_path = Path(encodings_path)
        self.known_encodings = []  # list[np.ndarray(128)]
        self.known_ids = []        # list[str] student ids, parallel to encodings
        if self.encodings_path.exists():
            self.load()

    # -- persistence ----------------------------------------------------
    def load(self):
        with open(self.encodings_path, "rb") as f:
            data = pickle.load(f)
        self.known_encodings = [np.asarray(e, dtype=np.float64) for e in data.get("encodings", [])]
        self.known_ids = [str(n) for n in data.get("names", [])]

    def save(self):
        self.encodings_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.encodings_path, "wb") as f:
            pickle.dump(
                {"encodings": self.known_encodings, "names": self.known_ids}, f
            )

    # -- enrollment -------------------------------------------------------
    def add_student(self, photo_path, student_id):
        """Encode the dominant face in `photo_path` and register it under `student_id`.

        Re-enrolling an existing id replaces its old encoding in place.
        Raises ValueError if no face is found in the photo.
        """
        faces = detect_faces(photo_path)
        if not faces:
            raise ValueError(
                f"No face detected in {photo_path} — use a clear, front-facing portrait."
            )
        # If several faces are in the frame, keep the largest (the subject).
        best = max(
            faces,
            key=lambda f: (f.location[2] - f.location[0]) * (f.location[1] - f.location[3]),
        )
        self.remove_student(student_id)
        self.known_encodings.append(np.asarray(best.encoding, dtype=np.float64))
        self.known_ids.append(str(student_id))
        return best.location

    def remove_student(self, student_id):
        pairs = [
            (e, i) for e, i in zip(self.known_encodings, self.known_ids)
            if i != str(student_id)
        ]
        self.known_encodings = [e for e, _ in pairs]
        self.known_ids = [i for _, i in pairs]

    def rebuild_from_dir(self, faces_dir):
        """Rebuild the whole store from portraits named <STUDENT_ID>.<ext>.

        Returns {student_id: "ok" | "FAILED: reason"}.
        """
        faces_dir = Path(faces_dir)
        report = {}
        self.known_encodings, self.known_ids = [], []
        for path in sorted(faces_dir.iterdir()):
            if path.suffix.lower() not in IMAGE_EXTS:
                continue
            try:
                self.add_student(path, path.stem)
                report[path.stem] = "ok"
            except Exception as exc:  # keep going; report failures at the end
                report[path.stem] = f"FAILED: {exc}"
        self.save()
        return report

    def __len__(self):
        return len(self.known_ids)
