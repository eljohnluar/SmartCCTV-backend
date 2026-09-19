import threading
import time
from typing import List, Dict, Any, Optional
import numpy as np
from utils.config import settings
from utils.logger import logger

# Labels emitted by a custom threat model or the standard COCO model.
# In standard COCO, pens held in hands are commonly classified as toothbrush/knife.
THREAT_LABELS = {
    # Bladed weapons
    "knife": "knife",
    "sword": "bladed weapon",
    "dagger": "bladed weapon",
    "machete": "bladed weapon",
    "blade": "bladed weapon",
    "scissors": "scissors",
    # Firearms
    "gun": "gun",
    "pistol": "gun",
    "rifle": "gun",
    "firearm": "gun",
    "handgun": "gun",
    "shotgun": "gun",
    "revolver": "gun",
    "sniper": "gun",
    "submachine gun": "gun",
    "assault rifle": "gun",
    # Blunt and improvised weapons
    "baseball bat": "blunt weapon",
    "baseball_bat": "blunt weapon",
    "bat": "blunt weapon",
    "club": "blunt weapon",
    "hammer": "blunt weapon",
    "crowbar": "blunt weapon",
    "pipe": "blunt weapon",
    "bottle": "blunt weapon",
    # Generic threat labels (custom model output)
    "weapon": "weapon",
    "threat": "weapon",
    # Incendiary / explosive
    "grenade": "explosive",
    "bomb": "explosive",
    "explosive": "explosive",
    # Common COCO-class false-positive for carried items (e.g., pens flagged as knife/toothbrush)
    "pen": "ballpoint pen",
    "ballpoint pen": "ballpoint pen",
    "ballpoint_pen": "ballpoint pen",
    "toothbrush": "ballpoint pen",
}

CLASS_CONFIDENCE = {
    # High-confidence threshold for ambiguous or common false-positive classes
    "ballpoint pen": 0.62,
    "blunt weapon": 0.50,
    "scissors": 0.48,
    # Medium confidence — these shapes are distinctive enough
    "bladed weapon": 0.40,
    "knife": 0.35,
    "weapon": 0.38,
    # Firearms are generally well-distinguished; keep threshold lower to catch partials
    "gun": 0.32,
    # Explosives — alert even at lower confidence given severity
    "explosive": 0.30,
}


class WeaponDetector:
    """
    Object detection engine using Ultralytics YOLO to scan video frames
    for weapons and hazardous objects.
    """
    SCAN_INTERVAL = 0.33   # ~3 scans per second for faster threat detection
    ALERT_COOLDOWN = 20.0  # Seconds between repeated alerts for the same threat class

    def __init__(self):
        self.model = None
        self.enabled = settings.WEAPON_DETECTION_ENABLED
        self.confidence_threshold = getattr(settings, "WEAPON_CONFIDENCE_THRESHOLD", 0.35)
        self.display_example_threats = getattr(settings, "DISPLAY_EXAMPLE_THREATS", False)

        self._scan_lock = threading.Lock()
        self._last_scan_at = 0.0
        self._active_threats: List[Dict[str, Any]] = []
        self._threats_expire_at = 0.0

        self._alert_lock = threading.Lock()
        self._last_alert_at: Dict[str, float] = {}

        if self.enabled:
            self._load_model()

    def _load_model(self):
        try:
            from ultralytics import YOLO
            self.model = YOLO(settings.YOLO_MODEL_PATH)
            logger.info("YOLO object detection model loaded successfully from %s.", settings.YOLO_MODEL_PATH)
        except Exception as e:
            logger.warning("Could not load YOLO model: %s. Running in stub mode.", e)

    def detect_threats(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        Runs object detection on a frame and returns list of detected weapon threats.
        """
        if not self.enabled or frame is None or self.model is None:
            return []

        try:
            results = self.model(frame, verbose=False)
            threats = []
            for r in results:
                for box in r.boxes:
                    cls_id = int(box.cls[0])
                    names = self.model.names
                    class_name = (names.get(cls_id, "") if isinstance(names, dict) else names[cls_id]).lower()
                    conf = float(box.conf[0])
                    normalized_name = THREAT_LABELS.get(class_name)

                    threshold = max(self.confidence_threshold, CLASS_CONFIDENCE.get(normalized_name, 1.0))
                    if normalized_name and conf >= threshold:
                        xyxy = [int(v) for v in box.xyxy[0].tolist()]
                        width = xyxy[2] - xyxy[0]
                        height = xyxy[3] - xyxy[1]
                        if width < 12 or height < 12:
                            continue

                        threats.append({
                            "class": normalized_name,
                            "raw_class": class_name,
                            "confidence": conf,
                            "box": xyxy,
                            "display": True,
                        })
            return threats
        except Exception as e:
            logger.error("Error during YOLO threat detection: %s", e)
            return []

    def scan_threats(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        Run one shared periodic scan, no matter how many viewers stream video.
        Retains active threats briefly to prevent flickering bounding boxes.
        """
        with self._scan_lock:
            now = time.monotonic()
            if now - self._last_scan_at >= self.SCAN_INTERVAL:
                self._last_scan_at = now
                detected = self.detect_threats(frame)
                if detected:
                    self._active_threats = detected
                    self._threats_expire_at = now + 1.8  # Keep boxes visible for 1.8 s between scans
                elif now > self._threats_expire_at:
                    self._active_threats = []
            elif now > self._threats_expire_at:
                self._active_threats = []
            return list(self._active_threats)

    def draw_threat_boxes(self, frame: np.ndarray, threats: List[Dict[str, Any]]) -> np.ndarray:
        """
        Draws high-visibility red threat bounding boxes on the camera frame.
        Example threats (like ballpoint pen) are omitted from the on-screen display
        unless explicitly configured, keeping the CCTV display realistic and clean.
        """
        if frame is None or not threats:
            return frame

        try:
            import cv2
            annotated = frame.copy()
            for threat in threats:
                if not threat.get("display", True):
                    continue

                box = threat.get("box")
                if not box or len(box) != 4:
                    continue

                x1, y1, x2, y2 = box
                x1 = max(0, min(annotated.shape[1] - 1, x1))
                y1 = max(0, min(annotated.shape[0] - 1, y1))
                x2 = max(0, min(annotated.shape[1] - 1, x2))
                y2 = max(0, min(annotated.shape[0] - 1, y2))
                if x2 <= x1 or y2 <= y1:
                    continue

                threat_name = threat.get("class", "threat").upper()
                conf = threat.get("confidence", 0.0)
                label = f"THREAT: {threat_name} {conf * 100:.0f}%"

                # Red color #ef4444 (BGR format)
                box_color = (68, 68, 239)
                text_color = (255, 255, 255)

                # Outer bounding box
                cv2.rectangle(annotated, (x1, y1), (x2, y2), box_color, 2, cv2.LINE_AA)

                # Futuristic corner brackets
                corner_len = min(20, max(8, (x2 - x1) // 4))
                cv2.line(annotated, (x1, y1), (x1 + corner_len, y1), (30, 30, 255), 3)
                cv2.line(annotated, (x1, y1), (x1, y1 + corner_len), (30, 30, 255), 3)
                cv2.line(annotated, (x2, y1), (x2 - corner_len, y1), (30, 30, 255), 3)
                cv2.line(annotated, (x2, y1), (x2, y1 + corner_len), (30, 30, 255), 3)
                cv2.line(annotated, (x1, y2), (x1 + corner_len, y2), (30, 30, 255), 3)
                cv2.line(annotated, (x1, y2), (x1, y2 - corner_len), (30, 30, 255), 3)
                cv2.line(annotated, (x2, y2), (x2 - corner_len, y2), (30, 30, 255), 3)
                cv2.line(annotated, (x2, y2), (x2, y2 - corner_len), (30, 30, 255), 3)

                # Threat tag badge
                (label_w, label_h), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.48, 1)
                label_top = max(0, y1 - label_h - baseline - 8)
                cv2.rectangle(
                    annotated,
                    (x1, label_top),
                    (x1 + label_w + 12, y1),
                    box_color,
                    thickness=-1,
                )
                cv2.putText(
                    annotated,
                    label,
                    (x1 + 6, y1 - baseline - 4),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.48,
                    text_color,
                    1,
                    cv2.LINE_AA,
                )
            return annotated
        except Exception as error:
            logger.error("Error drawing threat boxes: %s", error)
            return frame

    def claim_alert(self, threat_class: str) -> bool:
        """Allow one alert per threat type during the cooldown window."""
        with self._alert_lock:
            now = time.monotonic()
            if now - self._last_alert_at.get(threat_class, 0.0) < self.ALERT_COOLDOWN:
                return False
            self._last_alert_at[threat_class] = now
            return True

    def reset_cooldowns(self) -> None:
        """Clear threat alert cooldowns and active threat state."""
        with self._alert_lock:
            self._last_alert_at.clear()
        with self._scan_lock:
            self._active_threats.clear()
            self._threats_expire_at = 0.0
        logger.info("Weapon detector alert cooldowns reset.")


weapon_detector = WeaponDetector()
