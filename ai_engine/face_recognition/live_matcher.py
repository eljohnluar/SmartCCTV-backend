import time
from collections import defaultdict
from datetime import date
from typing import Dict, List, Optional, Tuple

import numpy as np

from database.queries import get_face_embeddings, mark_attendance
from websocket_manager import publish_from_worker
from utils.logger import logger
from .recognizer import face_recognizer


FaceBox = Tuple[int, int, int, int]


class LiveFaceMatcher:
    """Matches detected face crops and confirms attendance across consecutive scans."""

    def __init__(self):
        self._embeddings: List[Dict] = []
        self._embeddings_loaded_at = 0.0
        self._confirmations: Dict[int, int] = defaultdict(int)
        self._marked_today = set()
        self._marked_date = date.today()

    def _load_embeddings(self) -> List[Dict]:
        now = time.monotonic()
        if now - self._embeddings_loaded_at < 15:
            return self._embeddings
        try:
            self._embeddings = get_face_embeddings()
            self._embeddings_loaded_at = now
            logger.info("Loaded %d enrolled face embedding(s) for live matching.", len(self._embeddings))
        except Exception as error:
            logger.warning("Could not load enrolled face embeddings: %s", error)
            self._embeddings = []
            self._embeddings_loaded_at = now
        return self._embeddings

    @staticmethod
    def _crop(frame: np.ndarray, box: FaceBox) -> Optional[np.ndarray]:
        x, y, width, height = box
        frame_height, frame_width = frame.shape[:2]
        padding_x = round(width * 0.18)
        padding_y = round(height * 0.22)
        left = max(0, x - padding_x)
        top = max(0, y - padding_y)
        right = min(frame_width, x + width + padding_x)
        bottom = min(frame_height, y + height + padding_y)
        crop = frame[top:bottom, left:right]
        return crop if crop.size else None

    def match_frame(self, frame: np.ndarray, boxes: List[FaceBox], record_attendance: bool = True) -> List[str]:
        """Return labels aligned with boxes and mark confirmed identities present today."""
        if frame is None or not boxes:
            return []

        today = date.today()
        if today != self._marked_date:
            self._marked_date = today
            self._marked_today.clear()
            self._confirmations.clear()

        enrolled = self._load_embeddings()
        if not enrolled:
            return ["FACE" for _ in boxes]

        labels: List[str] = []
        seen_students = set()
        matched_confidences: Dict[int, float] = {}
        for box in boxes:
            crop = self._crop(frame, box)
            embedding = face_recognizer.extract_embedding(crop) if crop is not None else None
            match = face_recognizer.match_face(embedding, enrolled) if embedding else None
            if not match:
                labels.append("UNKNOWN")
                continue

            student_id = int(match["student_id"])
            student = next((item for item in enrolled if item.get("student_id") == student_id), {})
            name = student.get("student_name") or "MATCH"
            confidence = float(match.get("confidence", 0.0))
            labels.append(f"{name} {confidence * 100:.0f}%")
            seen_students.add(student_id)
            matched_confidences[student_id] = max(matched_confidences.get(student_id, 0.0), confidence)

        if not record_attendance:
            self._confirmations.clear()
            return labels

        for student_id in list(self._confirmations):
            if student_id not in seen_students:
                self._confirmations[student_id] = 0

        for student_id in seen_students:
            self._confirmations[student_id] += 1
            if self._confirmations[student_id] < 2 or student_id in self._marked_today:
                continue
            try:
                record = mark_attendance(
                    student_id=student_id,
                    status="present",
                    confidence=matched_confidences.get(student_id),
                )
                self._marked_today.add(student_id)
                logger.info("Attendance marked for matched student %s.", student_id)
                publish_from_worker({
                    "type": "attendance",
                    "student_id": student_id,
                    "student_name": next(
                        (item.get("student_name") for item in enrolled if item.get("student_id") == student_id),
                        "Unknown student",
                    ),
                    "student_code": next(
                        (item.get("student_code") for item in enrolled if item.get("student_id") == student_id),
                        "",
                    ),
                    "status": "present",
                    "confidence": matched_confidences.get(student_id),
                    "check_in_time": record.get("check_in_time"),
                    "class_date": record.get("class_date"),
                    "record": record,
                })
            except Exception as error:
                logger.warning("Could not mark attendance for student %s: %s", student_id, error)

        return labels


live_face_matcher = LiveFaceMatcher()
