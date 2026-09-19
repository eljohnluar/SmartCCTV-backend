from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional

class Settings(BaseSettings):
    # Supabase
    SUPABASE_URL: str = Field(default="", env="SUPABASE_URL")
    SUPABASE_SERVICE_KEY: str = Field(default="", env="SUPABASE_SERVICE_KEY")
    SUPABASE_ANON_KEY: str = Field(default="", env="SUPABASE_ANON_KEY")

    # Camera (OBS Virtual Camera)
    CAMERA_INDEX: int = Field(default=1, env="CAMERA_INDEX")
    CAMERA_FPS: int = Field(default=15, env="CAMERA_FPS")
    CAMERA_FRAME_WIDTH: int = Field(default=1280, env="CAMERA_FRAME_WIDTH")
    CAMERA_FRAME_HEIGHT: int = Field(default=720, env="CAMERA_FRAME_HEIGHT")

    # AI & Face Recognition
    RECOGNITION_THRESHOLD: float = Field(default=0.45, env="RECOGNITION_THRESHOLD")
    RECOGNITION_MODEL: str = Field(default="Facenet", env="RECOGNITION_MODEL")
    FACE_RECOGNITION_MODEL_PATH: str = Field(
        default="ai_engine/models/face_recognition_sface_2021dec.onnx",
        env="FACE_RECOGNITION_MODEL_PATH",
    )
    FACE_STORAGE_BUCKET: str = Field(default="face-enrollments", env="FACE_STORAGE_BUCKET")
    DETECTION_BACKEND: str = Field(default="opencv", env="DETECTION_BACKEND")
    FACE_DETECTION_ENABLED: bool = Field(default=True, env="FACE_DETECTION_ENABLED")
    FACE_DETECTION_FPS: float = Field(default=6.0, env="FACE_DETECTION_FPS")
    FACE_DETECTION_WIDTH: int = Field(default=720, env="FACE_DETECTION_WIDTH")
    FACE_DETECTION_MIN_SIZE: int = Field(default=28, env="FACE_DETECTION_MIN_SIZE")
    FACE_DETECTION_MIN_NEIGHBORS: int = Field(default=5, env="FACE_DETECTION_MIN_NEIGHBORS")
    FACE_DETECTION_CONFIDENCE: float = Field(default=0.75, env="FACE_DETECTION_CONFIDENCE")
    FACE_DETECTION_MODEL_PATH: str = Field(
        default="ai_engine/models/face_detection_yunet_2023mar.onnx",
        env="FACE_DETECTION_MODEL_PATH",
    )

    # Voice / gTTS
    VOICE_LANGUAGE: str = Field(default="en", env="VOICE_LANGUAGE")
    VOICE_ENABLED: bool = Field(default=True, env="VOICE_ENABLED")

    # Security / YOLO
    WEAPON_DETECTION_ENABLED: bool = Field(default=True, env="WEAPON_DETECTION_ENABLED")
    YOLO_MODEL_PATH: str = Field(default="yolov8n.pt", env="YOLO_MODEL_PATH")
    WEAPON_CONFIDENCE_THRESHOLD: float = Field(default=0.35, env="WEAPON_CONFIDENCE_THRESHOLD")
    DISPLAY_EXAMPLE_THREATS: bool = Field(default=False, env="DISPLAY_EXAMPLE_THREATS")

    # General
    ENVIRONMENT: str = Field(default="development", env="ENVIRONMENT")
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    HOST: str = Field(default="0.0.0.0", env="HOST")
    PORT: int = Field(default=8000, env="PORT")

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
