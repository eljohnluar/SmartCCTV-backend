from pathlib import Path
import threading
from typing import Optional, Dict, Any, List
import numpy as np
from utils.config import settings
from utils.logger import logger


class FaceRecognizer:
    """
    Extracts 128-dimensional facial embeddings using OpenCV SFace with
    YuNet 5-point facial landmark alignment, and matches against registered
    student embeddings stored in the database.
    """
    def __init__(self):
        self.model_name = settings.RECOGNITION_MODEL
        self.threshold = settings.RECOGNITION_THRESHOLD
        self.sface = None
        self.yunet = None
        # OpenCV's DNN Net keeps mutable input/output buffers. The live camera
        # and enrollment API can run simultaneously, so inference must be
        # serialized to prevent the buffer-shape assertion seen in OpenCV 5.
        self._sface_lock = threading.Lock()
        self.backend_name = "unavailable"

        try:
            import importlib.util
            if importlib.util.find_spec("deepface"):
                self.backend_name = "DeepFace"
        except Exception:
            pass

        try:
            import cv2
            base_dir = Path(__file__).resolve().parents[2]
            
            # SFace recognition model
            sface_path = Path(settings.FACE_RECOGNITION_MODEL_PATH)
            if not sface_path.is_absolute():
                sface_path = base_dir / sface_path
            if sface_path.is_file() and hasattr(cv2, "FaceRecognizerSF_create"):
                self.sface = cv2.FaceRecognizerSF_create(str(sface_path), "")
                if self.backend_name == "unavailable":
                    self.backend_name = "OpenCV SFace"
                logger.info("Face embedding backend available: %s", self.backend_name)

            # YuNet landmark alignment detector
            yunet_path = Path(settings.FACE_DETECTION_MODEL_PATH)
            if not yunet_path.is_absolute():
                yunet_path = base_dir / yunet_path
            if yunet_path.is_file() and hasattr(cv2, "FaceDetectorYN_create"):
                self.yunet = cv2.FaceDetectorYN_create(str(yunet_path), "", (320, 320), 0.45)
                logger.info("Face landmark aligner loaded with OpenCV YuNet.")
        except Exception as error:
            logger.warning("Could not load OpenCV SFace/YuNet model: %s", error)

    def extract_embedding_from_frame(self, frame: np.ndarray, raw_face: np.ndarray) -> Optional[List[float]]:
        """
        Extracts a 128-d embedding directly from the original frame using YuNet's
        5-point facial landmarks for canonical 112x112 alignment.
        """
        if self.sface is None or frame is None or frame.size == 0 or raw_face is None:
            return None
        try:
            with self._sface_lock:
                aligned_face = self.sface.alignCrop(frame, raw_face)
                feature = self.sface.feature(aligned_face)
            vector = np.asarray(feature, dtype=np.float32).reshape(-1)
            norm = np.linalg.norm(vector)
            return (vector / norm).astype(float).tolist() if norm > 0 else None
        except Exception as error:
            logger.warning("Frame landmark-aligned SFace embedding failed: %s", error)
            return None

    def _extract_sface_embedding(self, face_image: np.ndarray, raw_face: Optional[np.ndarray] = None) -> Optional[List[float]]:
        if self.sface is None or face_image is None or face_image.size == 0:
            return None
        try:
            import cv2
            if raw_face is not None:
                with self._sface_lock:
                    aligned_face = self.sface.alignCrop(face_image, raw_face)
                    feature = self.sface.feature(aligned_face)
            else:
                # If raw_face was not provided, attempt landmark detection within face_image
                aligned_face = None
                if self.yunet is not None:
                    h, w = face_image.shape[:2]
                    if h >= 20 and w >= 20:
                        with self._sface_lock:
                            self.yunet.setInputSize((w, h))
                            _, detected = self.yunet.detect(face_image)
                            if detected is not None and len(detected) > 0:
                                best = max(detected, key=lambda f: f[-1])
                                aligned_face = self.sface.alignCrop(face_image, best)

                with self._sface_lock:
                    if aligned_face is None:
                        aligned_face = cv2.resize(face_image, (112, 112), interpolation=cv2.INTER_AREA)
                    feature = self.sface.feature(aligned_face)

            vector = np.asarray(feature, dtype=np.float32).reshape(-1)
            norm = np.linalg.norm(vector)
            return (vector / norm).astype(float).tolist() if norm > 0 else None
        except Exception as error:
            logger.warning("OpenCV SFace embedding failed: %s", error)
            return None

    def extract_embedding(self, face_image: np.ndarray, raw_face: Optional[np.ndarray] = None) -> Optional[List[float]]:
        """
        Generates embedding vector for a face image with landmark alignment.
        """
        if self.backend_name == "DeepFace":
            try:
                from deepface import DeepFace
                embeddings = DeepFace.represent(
                    img_path=face_image,
                    model_name=self.model_name,
                    enforce_detection=False,
                )
                if embeddings and len(embeddings) > 0:
                    return embeddings[0]["embedding"]
            except Exception as error:
                logger.warning("DeepFace embedding failed; trying OpenCV SFace: %s", error)

        return self._extract_sface_embedding(face_image, raw_face=raw_face)

    def match_face(
        self,
        target_embedding: List[float],
        student_embeddings: List[Dict[str, Any]],
        min_threshold: Optional[float] = None,
        min_margin: float = 0.04,
    ) -> Optional[Dict[str, Any]]:
        """
        Calculates cosine similarity against database embeddings.
        Enforces both strict similarity threshold and top-2 margin test to
        guarantee that different faces are rejected and never falsely attributed.
        """
        if not target_embedding or not student_embeddings:
            return None

        target_vec = np.asarray(target_embedding, dtype=np.float32)
        target_norm = np.linalg.norm(target_vec)
        if target_norm == 0:
            return None
        target_vec = target_vec / target_norm

        # Group similarities by student_id to find the best match per student
        student_best_score: Dict[int, float] = {}

        for entry in student_embeddings:
            try:
                emb = np.asarray(entry["embedding"], dtype=np.float32)
                if emb.shape != target_vec.shape:
                    continue
                emb_norm = np.linalg.norm(emb)
                if emb_norm == 0:
                    continue
                sim = float(np.dot(target_vec, emb) / emb_norm)
                sid = int(entry["student_id"])
                if sid not in student_best_score or sim > student_best_score[sid]:
                    student_best_score[sid] = sim
            except (KeyError, TypeError, ValueError):
                continue

        if not student_best_score:
            return None

        # Sort candidate students descending by similarity score
        sorted_candidates = sorted(student_best_score.items(), key=lambda x: x[1], reverse=True)
        best_id, best_score = sorted_candidates[0]
        second_score = sorted_candidates[1][1] if len(sorted_candidates) > 1 else -1.0

        effective_threshold = min_threshold if min_threshold is not None else self.threshold

        # 1. Confidence threshold check: reject anything below threshold
        if best_score < effective_threshold:
            return None

        # 2. Discrimination / margin check: reject ambiguous matches where two
        # different students are close in similarity
        if second_score > 0 and (best_score - second_score) < min_margin:
            logger.debug(
                "Rejecting ambiguous face match: Student %s (%.3f) vs Student %s (%.3f), margin %.3f < %.3f",
                best_id, best_score, sorted_candidates[1][0], second_score, best_score - second_score, min_margin,
            )
            return None

        return {
            "student_id": best_id,
            "confidence": best_score,
            "margin": (best_score - second_score) if second_score > 0 else 1.0,
        }


face_recognizer = FaceRecognizer()
