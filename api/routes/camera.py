import asyncio
import time
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ai_engine.camera.rtsp_client import camera_stream
from ai_engine.face_recognition.detector import face_detector
from ai_engine.face_recognition.live_matcher import live_face_matcher
from utils.config import settings

router = APIRouter(prefix="/camera", tags=["camera"])


class AttendanceRecordingRequest(BaseModel):
    enabled: bool


async def _mjpeg_frames() -> AsyncIterator[bytes]:
    import cv2

    detected_faces = []
    face_labels = []
    last_detection_time = 0.0
    last_match_time = 0.0
    detection_interval = 1.0 / max(0.5, settings.FACE_DETECTION_FPS)
    match_interval = 1.0

    while True:
        frame = camera_stream.get_latest_frame()
        if frame is None:
            await asyncio.sleep(0.1)
            continue

        now = time.monotonic()
        if settings.FACE_DETECTION_ENABLED and now - last_detection_time >= detection_interval:
            detected_faces = face_detector.detect_faces(frame)
            last_detection_time = now
            if detected_faces and now - last_match_time >= match_interval:
                face_labels = await asyncio.to_thread(
                    live_face_matcher.match_frame,
                    frame,
                    detected_faces,
                    camera_stream.attendance_recording,
                )
                last_match_time = now
            elif not detected_faces:
                face_labels = []

        display_frame = (
            face_detector.draw_face_boxes(frame, detected_faces, face_labels)
            if settings.FACE_DETECTION_ENABLED
            else frame
        )
        success, encoded = cv2.imencode(".jpg", display_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if success:
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + encoded.tobytes() + b"\r\n"
        await asyncio.sleep(0.03)


@router.get("/stream")
async def stream_camera():
    """Stream the latest OBS Virtual Camera frame as MJPEG for the web dashboard."""
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
        raise HTTPException(status_code=409, detail="The camera is not ready. Start OBS Virtual Camera first.")
    camera_stream.attendance_recording = payload.enabled
    return {
        "ready": camera_stream.is_connected,
        "attendance_recording": camera_stream.attendance_recording,
    }
