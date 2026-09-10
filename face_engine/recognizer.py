"""Phase 2 — Recognition & confidence scoring (the "AI suggests" half of
Human-in-the-Loop).

Status policy per detected face:

    distance <= AUTO_APPROVE_DISTANCE      -> auto_approved (AI is confident;
                                              teacher just sees it pre-checked)
    AUTO_APPROVE_DISTANCE < d <= tolerance -> needs_review (AI has a guess;
                                              teacher confirms or corrects)
    no enrolled face within tolerance      -> unknown (teacher assigns from list)

NOTE — fix vs the original blueprint: it computed confidence = 1 - distance
and auto-approved at "confidence >= 85%", i.e. distance <= 0.15. Real dlib
matches typically land at distance 0.20-0.45, so that threshold would push
practically every face into manual review. We auto-approve at distance
<= 0.45 (similarity >= 55%) and review up to the standard 0.60 tolerance.
Both values live in config.py.
"""

from dataclasses import dataclass
from pathlib import Path

import cv2
import face_recognition
import numpy as np

from .encoder import FaceEncodingStore

AUTO_APPROVED = "auto_approved"
NEEDS_REVIEW = "needs_review"
UNKNOWN = "unknown"

# BGR colors for annotation boxes: green / amber / red
_STATUS_COLOR = {
    AUTO_APPROVED: (80, 200, 120),
    NEEDS_REVIEW: (60, 165, 255),
    UNKNOWN: (60, 60, 230),
}


@dataclass
class Recognition:
    location: tuple          # (top, right, bottom, left)
    student_id: str          # matched id or "Unknown"
    similarity: float        # 0-100, = (1 - face_distance) * 100
    distance: float | None   # raw face distance (None if nobody enrolled)
    status: str              # AUTO_APPROVED | NEEDS_REVIEW | UNKNOWN

    def to_dict(self):
        return {
            "location": [int(v) for v in self.location],
            "student_id": self.student_id,
            "similarity": float(self.similarity),
            "distance": None if self.distance is None else float(self.distance),
            "status": self.status,
        }


class FaceRecognizer:
    def __init__(self, encodings_path, tolerance=0.60, auto_approve_distance=0.45):
        self.tolerance = float(tolerance)
        self.auto_approve_distance = float(auto_approve_distance)
        self.store = FaceEncodingStore(encodings_path)

    @property
    def enrolled_students(self):
        return list(self.store.known_ids)

    def recognize(self, image_path, model="hog", upsample_times=1):
        """Detect + identify every face in an image.

        Returns a list of Recognition (JSON-safe via .to_dict()).
        """
        image = face_recognition.load_image_file(str(image_path))
        locations = face_recognition.face_locations(
            image, number_of_times_to_upsample=upsample_times, model=model
        )
        encodings = face_recognition.face_encodings(image, locations)

        known = (
            np.vstack(self.store.known_encodings)
            if len(self.store)
            else None
        )

        results = []
        for loc, enc in zip(locations, encodings):
            dist = None
            student_id = "Unknown"
            status = UNKNOWN
            if known is not None:
                distances = np.linalg.norm(known - enc, axis=1)
                j = int(np.argmin(distances))
                dist = float(distances[j])
                if dist <= self.tolerance:
                    student_id = self.store.known_ids[j]
                    status = (
                        AUTO_APPROVED
                        if dist <= self.auto_approve_distance
                        else NEEDS_REVIEW
                    )
            similarity = round(max(0.0, 1.0 - dist) * 100, 1) if dist is not None else 0.0
            results.append(
                Recognition(
                    location=loc,
                    student_id=student_id,
                    similarity=similarity,
                    distance=None if dist is None else round(dist, 4),
                    status=status,
                )
            )
        return results

    def annotate(self, image_path, results, out_path):
        """Draw color-coded boxes + labels on the image and save it."""
        img = cv2.imread(str(image_path))
        for r in results:
            top, right, bottom, left = r.location
            color = _STATUS_COLOR[r.status]
            cv2.rectangle(img, (left, top), (right, bottom), color, 2)
            label = (
                f"{r.student_id} {r.similarity:.0f}%"
                if r.status != UNKNOWN
                else "Unknown"
            )
            scale = max(0.45, min(0.8, (right - left) / 220))
            (tw, th), _ = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, scale, 2
            )
            cv2.rectangle(img, (left, top - th - 10), (left + tw + 6, top), color, -1)
            cv2.putText(
                img, label, (left + 3, top - 5),
                cv2.FONT_HERSHEY_SIMPLEX, scale, (255, 255, 255), 2,
            )
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(out_path), img)
        return out_path
