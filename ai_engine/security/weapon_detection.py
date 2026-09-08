from typing import List, Dict, Any, Optional
import numpy as np
from utils.config import settings
from utils.logger import logger

# COCO and weapon classes of interest
THREAT_LABELS = {"knife", "gun", "pistol", "rifle", "weapon", "scissors"}

class WeaponDetector:
    """
    Object detection engine using Ultralytics YOLO to scan video frames
    for weapons and hazardous objects.
    """
    def __init__(self):
        self.model = None
        self.enabled = settings.WEAPON_DETECTION_ENABLED
        if self.enabled:
            self._load_model()

    def _load_model(self):
        try:
            from ultralytics import YOLO
            self.model = YOLO(settings.YOLO_MODEL_PATH)
            logger.info("YOLO object detection model loaded successfully.")
        except Exception as e:
            logger.warning(f"Could not load YOLO model: {e}. Running in stub mode.")

    def detect_threats(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        Runs object detection on a frame and returns list of detected weapon threats.
        """
        if not self.enabled or frame is None:
            return []

        if self.model is None:
            return []

        try:
            results = self.model(frame, verbose=False)
            threats = []
            for r in results:
                for box in r.boxes:
                    cls_id = int(box.cls[0])
                    class_name = self.model.names.get(cls_id, "").lower()
                    conf = float(box.conf[0])

                    if class_name in THREAT_LABELS and conf >= 0.5:
                        xyxy = box.xyxy[0].tolist()
                        threats.append({
                            "class": class_name,
                            "confidence": conf,
                            "box": [int(v) for v in xyxy]
                        })
            return threats
        except Exception as e:
            logger.error(f"Error during YOLO threat detection: {e}")
            return []

weapon_detector = WeaponDetector()
