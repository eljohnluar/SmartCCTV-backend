from typing import Optional, Dict, Any
from utils.logger import logger

class TrespasserDetector:
    """
    Monitors un-enrolled or unrecognized faces lingering in restricted
    or unauthorized campus zones.
    """
    def check_trespasser(self, face_box, zone: str = "general") -> Optional[Dict[str, Any]]:
        # Flags unrecognized individuals detected in faculty or restricted areas
        if zone in ["restricted", "faculty_room", "server_room"]:
            return {
                "type": "trespasser",
                "description": f"Unrecognized individual detected in {zone}",
                "severity": "high"
            }
        return None

trespasser_detector = TrespasserDetector()
