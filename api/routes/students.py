from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from typing import List, Optional
from api.models.student import StudentCreate, StudentUpdate, StudentResponse
from database.queries import (
    get_all_students,
    create_student_record,
    update_student_record,
    delete_student_record,
    replace_face_embeddings,
)
from ai_engine.face_recognition.detector import face_detector
from ai_engine.face_recognition.recognizer import face_recognizer
from database.storage import delete_face_image, upload_face_image
from utils.logger import logger

router = APIRouter(prefix="/students", tags=["Students"])

@router.get("", response_model=List[StudentResponse])
def list_students(section: Optional[str] = None):
    """Retrieve all enrolled students with optional section filter"""
    return get_all_students(section=section)

@router.post("", response_model=StudentResponse)
def add_student(student_in: StudentCreate):
    """Enroll a new student record"""
    data = student_in.dict()
    created = create_student_record(data)
    return created

@router.get("/{student_id}", response_model=StudentResponse)
def get_student(student_id: int):
    """Get student details by numerical ID"""
    all_s = get_all_students()
    match = next((s for s in all_s if s["id"] == student_id), None)
    if not match:
        raise HTTPException(status_code=404, detail="Student not found")
    return match

@router.put("/{student_id}", response_model=StudentResponse)
def update_student(student_id: int, updates: StudentUpdate):
    """Update student information"""
    data = {k: v for k, v in updates.dict().items() if v is not None}
    updated = update_student_record(student_id, data)
    if not updated:
        raise HTTPException(status_code=404, detail="Student not found")
    return updated

@router.delete("/{student_id}")
def delete_student(student_id: int):
    """Remove student record"""
    success = delete_student_record(student_id)
    if not success:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"success": True, "message": "Student deleted"}

@router.post("/face-enroll")
async def enroll_face(
    student_id: int = Form(...),
    images: List[UploadFile] = File(...),
):
    """
    Enroll four face-angle samples for facial recognition.
    Each sample produces a separate embedding so live recognition can match the
    student at different angles.
    """
    try:
        import cv2
        import numpy as np

        required_angles = ("front", "left", "right", "upward")
        if len(images) != len(required_angles):
            raise HTTPException(status_code=422, detail="Capture all four required face angles before enrolling.")

        embeddings = []
        stored_paths = []
        for angle, image in zip(required_angles, images):
            content = await image.read()
            frame = cv2.imdecode(np.frombuffer(content, dtype=np.uint8), cv2.IMREAD_COLOR)
            if frame is None:
                raise HTTPException(status_code=400, detail=f"The {angle} image could not be decoded.")

            faces = face_detector.detect_faces(frame)
            if not faces:
                raise HTTPException(status_code=422, detail=f"No face was detected in the {angle} capture. Retake it in good lighting.")

            x, y, width, height = max(faces, key=lambda box: box[2] * box[3])
            padding_x = round(width * 0.2)
            padding_y = round(height * 0.25)
            left = max(0, x - padding_x)
            top = max(0, y - padding_y)
            right = min(frame.shape[1], x + width + padding_x)
            bottom = min(frame.shape[0], y + height + padding_y)
            face_crop = frame[top:bottom, left:right]
            embedding = face_recognizer.extract_embedding(face_crop)
            if not embedding:
                raise HTTPException(
                    status_code=503,
                    detail="Face embedding is unavailable. Ensure the OpenCV SFace model is present and restart the API.",
                )
            if len(embedding) != 128:
                raise HTTPException(status_code=422, detail=f"The recognition model returned an unsupported embedding for the {angle} capture.")

            encoded_success, encoded_face = cv2.imencode(".jpg", face_crop, [cv2.IMWRITE_JPEG_QUALITY, 92])
            if not encoded_success:
                raise HTTPException(status_code=500, detail=f"The {angle} face could not be encoded for storage.")
            embeddings.append(embedding)
            stored_paths.append(upload_face_image(student_id, encoded_face.tobytes(), angle))

        try:
            replace_face_embeddings(student_id, embeddings)
            update_student_record(student_id, {"has_face": True, "face_storage_path": stored_paths[0]})
        except Exception:
            for path in stored_paths:
                delete_face_image(path)
            raise
        
        return {
            "success": True,
            "message": f"Four facial embeddings generated and registered for student {student_id}",
            "student_id": student_id,
            "has_face": True,
            "face_storage_path": stored_paths[0],
            "samples": len(embeddings),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during face enrollment: {e}")
        raise HTTPException(status_code=500, detail=str(e))
