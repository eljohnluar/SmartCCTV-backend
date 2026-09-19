import asyncio
import time
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ai_engine.camera.rtsp_client import camera_stream
from ai_engine.gesture_detection import gesture_detector
from ai_engine.face_recognition.detector import face_detector
from ai_engine.face_recognition.live_matcher import live_face_matcher
from ai_engine.security.weapon_detection import weapon_detector
from ai_engine.voice.announcer import voice_announcer
from database.queries import create_alert_record
from utils.config import settings
from utils.logger import logger
from utils.uniform_policy import get_runtime_controls
from websocket_manager import publish_from_worker

router = APIRouter(prefix="/camera", tags=["camera"])


class AttendanceRecordingRequest(BaseModel):
    enabled: bool


class VoiceTestRequest(BaseModel):
    message: str = "Voice announcer is ready."


async def _process_threats(frame, alert_mode_enabled: bool) -> list:
    """Scan for threat objects and announce security policy violations."""
    if not settings.WEAPON_DETECTION_ENABLED or not alert_mode_enabled or frame is None:
        return []

    threats = await asyncio.to_thread(weapon_detector.scan_threats, frame)
    for threat in threats:
        threat_class = threat["class"]
        if not weapon_detector.claim_alert(threat_class):
            continue
        description = f"Security policy violation: {threat_class.title()} detected."
        try:
            alert = await asyncio.to_thread(
                create_alert_record,
                "weapon_detected",
                description,
                None,
                None,
                "high",
            )
            voice_announcer.announce(f"Security violation. {threat_class} detected.")
            publish_from_worker({"type": "alert", **alert})
            logger.warning("%s", description)
        except Exception as error:
            logger.warning("Could not record detected %s: %s", threat_class, error)
    return threats


async def _mjpeg_frames() -> AsyncIterator[bytes]:
    import cv2

    detected_faces = []
    face_labels = []
    last_detection_time = 0.0
    last_match_time = 0.0
    last_gesture_check_time = 0.0
    last_controls_check_time = 0.0
    runtime_controls = get_runtime_controls()
    hand_detection = {"detected": False, "open_palm": False, "bbox": None}
    hand_gesture_detected = False
    detection_interval = 1.0 / max(0.5, settings.FACE_DETECTION_FPS)
    match_interval = 1.0

    while True:
        frame = camera_stream.get_latest_frame()
        if frame is None:
            await asyncio.sleep(0.1)
            continue

        now = time.monotonic()
        if now - last_controls_check_time >= 1.0:
            runtime_controls = get_runtime_controls()
            last_controls_check_time = now
        if runtime_controls["camera_flip_horizontal"]:
            frame = cv2.flip(frame, 1)
        threats = await _process_threats(frame, runtime_controls["alert_mode_enabled"])
        if now - last_gesture_check_time >= match_interval:
            hand_detection = gesture_detector.detect_hand(frame)
            hand_gesture_detected = hand_detection["open_palm"]
            last_gesture_check_time = now
        if settings.FACE_DETECTION_ENABLED and now - last_detection_time >= detection_interval:
            detected_faces = face_detector.detect_faces(frame)
            last_detection_time = now
            if detected_faces and (now - last_match_time >= match_interval or len(detected_faces) != len(face_labels)):
                face_labels = await asyncio.to_thread(
                    live_face_matcher.match_frame,
                    frame,
                    detected_faces,
                    camera_stream.attendance_recording,
                    hand_gesture_detected,
                )
                last_match_time = now
            elif not detected_faces:
                face_labels = []

        display_frame = frame
        if settings.WEAPON_DETECTION_ENABLED and threats:
            display_frame = weapon_detector.draw_threat_boxes(display_frame, threats)

        if settings.FACE_DETECTION_ENABLED and detected_faces:
            display_frame = face_detector.draw_face_boxes(display_frame, detected_faces, face_labels)
        if hand_detection["detected"] and hand_detection["bbox"]:
            x, y, width, height = hand_detection["bbox"]
            label = "OPEN PALM" if hand_gesture_detected else "HAND"
            color = (80, 210, 120) if hand_gesture_detected else (60, 190, 240)
            cv2.rectangle(display_frame, (x, y), (x + width, y + height), color, 2)
            cv2.putText(display_frame, label, (x, max(20, y - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
        success, encoded = cv2.imencode(".jpg", display_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if success:
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + encoded.tobytes() + b"\r\n"
        await asyncio.sleep(0.03)


@router.get("/stream")
async def stream_camera():
    """Stream the latest camera frame as MJPEG for the web dashboard."""
    try:
        import cv2  # noqa: F401
    except ImportError as error:
        raise HTTPException(status_code=503, detail="OpenCV is not installed; the camera stream is unavailable.") from error

    if not camera_stream.is_running:
        camera_stream.start()

    return StreamingResponse(
        _mjpeg_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@router.get("/attendance-recording")
async def get_attendance_recording():
    return {
        "ready": camera_stream.is_connected,
        "attendance_recording": camera_stream.attendance_recording,
    }


@router.post("/attendance-recording")
async def set_attendance_recording(payload: AttendanceRecordingRequest):
    if payload.enabled and not camera_stream.is_connected:
        raise HTTPException(status_code=409, detail="The camera is not ready. Please ensure the camera source is active.")
    camera_stream.attendance_recording = payload.enabled
    return {
        "ready": camera_stream.is_connected,
        "attendance_recording": camera_stream.attendance_recording,
    }


@router.post("/test-voice")
async def test_voice(payload: VoiceTestRequest = VoiceTestRequest()):
    """Play a short test through the server speaker and connected dashboards."""
    voice_announcer.announce(payload.message)
    return {"success": True, "message": "Voice announcement queued."}
