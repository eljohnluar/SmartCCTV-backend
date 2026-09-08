from typing import Tuple, Optional
import numpy as np
from utils.logger import logger

class FrameProcessor:
    """
    Standard preprocessing for video frames:
    resizing, color conversions, and ROI cropping.
    """
    @staticmethod
    def resize_frame(frame: np.ndarray, width: int = 640, height: int = 480) -> np.ndarray:
        try:
            import cv2
            return cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)
        except Exception:
            return frame

    @staticmethod
    def to_grayscale(frame: np.ndarray) -> np.ndarray:
        try:
            import cv2
            return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        except Exception:
            return frame

    @staticmethod
    def crop_roi(frame: np.ndarray, box: Tuple[int, int, int, int]) -> Optional[np.ndarray]:
        """Crops region of interest given (x, y, w, h) bounding box"""
        x, y, w, h = box
        if x < 0 or y < 0 or w <= 0 or h <= 0:
            return None
        return frame[y:y+h, x:x+w]
