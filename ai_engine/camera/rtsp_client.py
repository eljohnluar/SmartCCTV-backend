import threading
import time
from typing import Optional, Callable
import numpy as np
from utils.config import settings
from utils.logger import logger

class CameraCapture:
    """
    Captures live frames from OBS Virtual Camera using OpenCV.
    The Yi IoT desktop app streams the wireless CCTV feed,
    OBS Studio captures the window and outputs as OBS Virtual Camera,
    and OpenCV ingests from the virtual camera index.
    """
    def __init__(
        self,
        camera_index: Optional[int] = None,
        target_fps: Optional[int] = None,
        on_frame_callback: Optional[Callable[[np.ndarray], None]] = None
    ):
        self.camera_index = camera_index if camera_index is not None else settings.CAMERA_INDEX
        self.target_fps = target_fps or settings.CAMERA_FPS
        self.on_frame_callback = on_frame_callback
        
        self.cap = None
        self.is_running = False
        self.is_connected = False
        self.thread: Optional[threading.Thread] = None
        self.latest_frame: Optional[np.ndarray] = None
        self.frame_seq = 0
        # Face recognition marks enrolled students by default as soon as the
        # camera is available. The dashboard can still pause it explicitly.
        self.attendance_recording = True
        self.lock = threading.Lock()

    def start(self):
        """Starts background thread to continuously ingest frames from OBS Virtual Camera"""
        if self.is_running:
            logger.info("Camera capture is already running.")
            return

        self.is_running = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()
        logger.info(f"Camera capture thread started on device index {self.camera_index}")

    def stop(self):
        """Stops capture loop and releases OpenCV VideoCapture resource"""
        self.is_running = False
        self.is_connected = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
        if self.cap:
            try:
                self.cap.release()
            except Exception as e:
                logger.error(f"Error releasing camera: {e}")
        logger.info("Camera capture stopped.")

    def _capture_loop(self):
        try:
            import cv2
            self.cap = cv2.VideoCapture(self.camera_index)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, settings.CAMERA_FRAME_WIDTH)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, settings.CAMERA_FRAME_HEIGHT)
            self.cap.set(cv2.CAP_PROP_FPS, max(self.target_fps, settings.STREAM_MAX_FPS))
            # Keep the driver queue at one frame so we always publish the newest
            # picture instead of draining a backlog of stale ones.
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            if not self.cap.isOpened():
                self.is_connected = False
                logger.warning(
                    f"Could not open camera device at index {self.camera_index}. "
                    "Ensure OBS Virtual Camera is started (Controls -> Start Virtual Camera)."
                )

            # read() blocks until the device produces a frame, so no artificial
            # throttle is needed; pacing only applies when reads fail.
            while self.is_running:
                ret, frame = self.cap.read()
                if ret and frame is not None:
                    self.is_connected = True
                    with self.lock:
                        self.latest_frame = frame
                        self.frame_seq += 1

                    if self.on_frame_callback:
                        try:
                            self.on_frame_callback(frame)
                        except Exception as cb_err:
                            logger.error(f"Error in on_frame callback: {cb_err}")
                    continue

                self.is_connected = False
                time.sleep(0.05)

        except ImportError:
            logger.warning("OpenCV (cv2) not installed. Camera loop running in simulation mode.")
            while self.is_running:
                time.sleep(1.0)
        except Exception as e:
            logger.error(f"Unexpected error in camera capture loop: {e}")
        finally:
            self.is_connected = False
            if self.cap:
                try:
                    self.cap.release()
                except Exception:
                    pass

    def get_latest_frame(self) -> Optional[np.ndarray]:
        with self.lock:
            frame = self.latest_frame
        return frame.copy() if frame is not None else None

    def read_if_new(self, last_seq: int):
        """Return (frame, seq) only when the device produced a frame since last_seq."""
        with self.lock:
            if self.frame_seq == last_seq or self.latest_frame is None:
                return None, last_seq
            # The capture thread swaps in a brand new array each read, so holding
            # a reference is stable and the copy can happen outside the lock.
            frame_ref = self.latest_frame
            seq = self.frame_seq
        return frame_ref.copy(), seq

camera_stream = CameraCapture()
