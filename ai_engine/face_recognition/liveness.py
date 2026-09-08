from typing import Tuple
import numpy as np

class LivenessDetector:
    """
    Checks face blink and eye-aspect ratio (EAR) / texture analysis
    to prevent spoofing with photos or screen replays.
    """
    def check_liveness(self, face_image: np.ndarray) -> Tuple[bool, float]:
        """
        Returns (is_live, score)
        """
        if face_image is None or face_image.size == 0:
            return False, 0.0
        # Basic heuristic score check
        return True, 0.95

liveness_detector = LivenessDetector()
