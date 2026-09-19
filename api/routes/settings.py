from typing import List, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from utils.uniform_policy import (
    get_gesture_attendance_settings,
    get_runtime_controls,
    get_schedule_settings,
    get_uniform_policy,
    get_voice_settings,
    save_gesture_attendance_settings,
    save_runtime_controls,
    save_schedule_settings,
    save_uniform_policy,
    save_voice_settings,
)
from websocket_manager import publish_from_worker


router = APIRouter(prefix="/settings", tags=["settings"])


class UniformPolicyPayload(BaseModel):
    uniform_colors: List[str]


class VoiceSettingsPayload(BaseModel):
    voice_gender: Literal["female", "male"]


class ScheduleSettingsPayload(BaseModel):
    checkin_time: str
    late_grace_minutes: int = 30


class GestureAttendanceSettingsPayload(BaseModel):
    gesture_attendance_enabled: bool


class RuntimeControlsPayload(BaseModel):
    camera_flip_horizontal: bool = False
    announcer_enabled: bool = True
    announcer_volume: int = 100
    alert_mode_enabled: bool = True


@router.get("/uniform-policy")
def get_uniform_color_policy():
    """Read the colors accepted as compliant student uniforms."""
    return get_uniform_policy()


@router.put("/uniform-policy")
def update_uniform_color_policy(payload: UniformPolicyPayload):
    """Set the colors accepted as compliant student uniforms."""
    try:
        return save_uniform_policy(payload.uniform_colors)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/voice")
def get_voice_configuration():
    return get_voice_settings()


@router.put("/voice")
def update_voice_configuration(payload: VoiceSettingsPayload):
    return save_voice_settings(payload.voice_gender)


@router.get("/gesture-attendance")
def get_gesture_attendance_configuration():
    """Read whether an open palm must confirm enrollment and attendance."""
    return get_gesture_attendance_settings()


@router.put("/gesture-attendance")
def update_gesture_attendance_configuration(payload: GestureAttendanceSettingsPayload):
    result = save_gesture_attendance_settings(payload.gesture_attendance_enabled)
    publish_from_worker({"type": "gesture_attendance_updated", **result})
    return result


@router.get("/runtime-controls")
def get_runtime_control_configuration():
    return get_runtime_controls()


@router.put("/runtime-controls")
def update_runtime_control_configuration(payload: RuntimeControlsPayload):
    try:
        result = save_runtime_controls(**payload.model_dump())
        publish_from_worker({"type": "runtime_controls_updated", **result})
        return result
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/schedule")
def get_schedule_configuration():
    """Get the target check-in time and late grace minutes."""
    return get_schedule_settings()


@router.put("/schedule")
def update_schedule_configuration(payload: ScheduleSettingsPayload):
    """Set the target check-in time and late grace window."""
    try:
        result = save_schedule_settings(payload.checkin_time, payload.late_grace_minutes)
        publish_from_worker({"type": "schedule_updated", **result})
        return result
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
