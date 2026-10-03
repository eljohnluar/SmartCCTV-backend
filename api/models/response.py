from pydantic import BaseModel
from typing import Any, Optional, Dict, List

class APIResponse(BaseModel):
    success: bool = True
    message: str = "Operation completed successfully"
    data: Optional[Any] = None

class SystemStatusResponse(BaseModel):
    status: str
    camera_active: bool
    ai_active: bool
    camera_index: int
    fps: int
    recognition_model: str
    active_students_count: int
    unresolved_alerts_count: int
    attendance_recording: bool = False
