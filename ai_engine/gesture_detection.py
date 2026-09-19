"""Lightweight, on-device open-palm detection for gesture confirmation."""

from __future__ import annotations

from typing import Any, Dict, Tuple


class HandGestureDetector:
    """Detect a raised open palm without requiring a separate ML runtime.

    This intentionally gates attendance rather than identifying a person: face
    recognition remains the identity check, while the open palm is an explicit
    action from the person standing at the camera.
    """

    def detect_hand(self, frame: Any) -> Dict[str, Any]:
        """Return a visible hand box and whether it is an open-palm gesture."""
        try:
            import cv2
            import numpy as np

            if frame is None or frame.size == 0:
                return {"detected": False, "open_palm": False, "bbox": None}

            height, width = frame.shape[:2]
            scale = min(1.0, 480 / max(height, width))
            if scale < 1:
                frame = cv2.resize(frame, (round(width * scale), round(height * scale)))

            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            # Broad skin-tone ranges in HSV, including the hue range that wraps
            # around zero. Morphology removes small background fragments.
            mask = cv2.inRange(hsv, np.array((0, 20, 55)), np.array((25, 255, 255)))
            mask |= cv2.inRange(hsv, np.array((160, 20, 55)), np.array((180, 255, 255)))
            kernel = np.ones((5, 5), np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                return {"detected": False, "open_palm": False, "bbox": None}

            contour = max(contours, key=cv2.contourArea)
            area = cv2.contourArea(contour)
            frame_area = frame.shape[0] * frame.shape[1]
            if area < max(900, frame_area * 0.012):
                return {"detected": False, "open_palm": False, "bbox": None}

            x, y, box_width, box_height = cv2.boundingRect(contour)
            bbox: Tuple[int, int, int, int] = tuple(
                round(value / scale) for value in (x, y, box_width, box_height)
            )

            hull = cv2.convexHull(contour, returnPoints=False)
            if hull is None or len(hull) < 4:
                return {"detected": True, "open_palm": False, "bbox": bbox}
            defects = cv2.convexityDefects(contour, hull)
            if defects is None:
                return {"detected": True, "open_palm": False, "bbox": bbox}

            finger_gaps = 0
            for defect in defects[:, 0]:
                start, end, far, depth = defect
                a = np.linalg.norm(contour[end][0] - contour[start][0])
                b = np.linalg.norm(contour[far][0] - contour[start][0])
                c = np.linalg.norm(contour[end][0] - contour[far][0])
                if not a or not b or not c:
                    continue
                cosine = np.clip((b * b + c * c - a * a) / (2 * b * c), -1, 1)
                angle = np.degrees(np.arccos(cosine))
                if angle < 90 and depth > 12 * 256:
                    finger_gaps += 1

            hull_area = cv2.contourArea(cv2.convexHull(contour))
            solidity = area / hull_area if hull_area else 1.0
            return {
                "detected": True,
                "open_palm": finger_gaps >= 2 and 0.42 <= solidity <= 0.93,
                "bbox": bbox,
            }
        except Exception:
            # Gesture confirmation is optional. Never let a camera-frame error
            # interrupt recognition or the live video stream.
            return {"detected": False, "open_palm": False, "bbox": None}

    def is_open_palm(self, frame: Any) -> bool:
        """Compatibility helper for enrollment validation."""
        return bool(self.detect_hand(frame)["open_palm"])


gesture_detector = HandGestureDetector()
