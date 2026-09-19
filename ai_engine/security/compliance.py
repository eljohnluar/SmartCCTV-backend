import time
from typing import Optional, Dict, Any, List, Tuple

import numpy as np


FaceBox = Tuple[int, int, int, int]


class ComplianceChecker:
    """Evaluates the dominant color in an enrolled student's torso region."""

    REPORT_COOLDOWN = 300.0

    def __init__(self):
        self._last_reported: Dict[Tuple[int, str], float] = {}

    @staticmethod
    def _torso_crop(frame: np.ndarray, face_box: FaceBox) -> Optional[np.ndarray]:
        x, y, width, height = face_box
        frame_height, frame_width = frame.shape[:2]
        # The centered area below the face is deliberately used instead of an
        # object detector, so no clothing box needs to appear on the stream.
        left = max(0, x - round(width * 0.35))
        right = min(frame_width, x + width + round(width * 0.35))
        top = min(frame_height, y + height)
        bottom = min(frame_height, top + round(height * 2.6))
        if right <= left or bottom - top < max(20, height // 2):
            return None
        return frame[top:bottom, left:right]

    def detect_uniform_color(self, frame: np.ndarray, face_box: FaceBox) -> Optional[Dict[str, Any]]:
        """Detect the supported colors materially visible in the torso region."""
        torso = self._torso_crop(frame, face_box)
        if torso is None:
            return None
        try:
            import cv2

            hsv = cv2.cvtColor(torso, cv2.COLOR_BGR2HSV)
            hue, saturation, value = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
            masks = {
                # Dark blue: high hue, high saturation, low-to-medium brightness
                "dark-blue": (hue >= 100) & (hue <= 140) & (saturation >= 80) & (value >= 20) & (value < 110),
                # Light blue: similar hue range but higher brightness or lower saturation
                "light-blue": (hue >= 85) & (hue <= 140) & (saturation >= 30) & (value >= 110),
                # Dark red: low/high hue (wraps around), high saturation, low brightness
                "dark-red": (((hue <= 10) | (hue >= 170)) & (saturation >= 80) & (value >= 20) & (value < 110)),
                # Light red: similar hue wrap but brighter
                "light-red": (((hue <= 12) | (hue >= 165)) & (saturation >= 40) & (value >= 110)),
                "white": (saturation <= 45) & (value >= 155),
                # Keep dark blue/red from also being classified as black
                "black": (value <= 45) & (saturation <= 55),
            }
            ratios = {color: float(mask.mean()) for color, mask in masks.items()}
            detected = [
                {"color": color, "confidence": confidence}
                for color, confidence in ratios.items()
                if confidence >= 0.12
            ]
            if not detected:
                return {"color": "unknown", "confidence": max(ratios.values())}
            strongest = max(detected, key=lambda item: item["confidence"])
            return {**strongest, "detected_colors": detected}
        except Exception:
            return None

    def evaluate_uniform(
        self,
        student_id: int,
        frame: np.ndarray,
        face_box: FaceBox,
        allowed_colors: List[str],
    ) -> Optional[Dict[str, Any]]:
        """Return a violation only when an enrolled student's color is disallowed.

        For backward compatibility the canonical values 'blue' and 'red' implicitly
        permit their specific sub-shades ('dark-blue', 'light-blue', 'dark-red',
        'light-red') so that policies saved before the sub-shade feature was added
        continue to work without manual re-configuration.
        """
        result = self.detect_uniform_color(frame, face_box)
        if result is None:
            return None

        # Build an expanded set of allowed colors that includes sub-shades
        # when the canonical parent color is permitted.
        expanded_allowed: set = set(allowed_colors)
        if "blue" in allowed_colors:
            expanded_allowed.update(("dark-blue", "light-blue"))
        if "red" in allowed_colors:
            expanded_allowed.update(("dark-red", "light-red"))

        disallowed = [
            item for item in result.get("detected_colors", [result])
            if item["color"] not in expanded_allowed
        ]
        if not disallowed:
            return None
        return max(disallowed, key=lambda item: item["confidence"])

    def should_report(self, student_id: int, detected_color: str) -> bool:
        """Check whether a duplicate policy alert should be suppressed."""
        key = (student_id, detected_color)
        now = time.monotonic()
        previous = self._last_reported.get(key, 0.0)
        if now - previous < self.REPORT_COOLDOWN:
            return False
        return True

    def mark_reported(self, student_id: int, detected_color: str) -> None:
        self._last_reported[(student_id, detected_color)] = time.monotonic()


compliance_checker = ComplianceChecker()
