from typing import Optional

from database.supabase_client import get_supabase
from utils.config import settings
from utils.logger import logger


def upload_face_image(student_id: int, content: bytes, angle: str = "front") -> str:
    """Upload a cropped enrollment face to the private Supabase bucket."""
    client = get_supabase()
    if client is None:
        raise RuntimeError("Supabase is not configured; face images cannot be stored.")
    if not settings.SUPABASE_SERVICE_KEY:
        raise RuntimeError("SUPABASE_SERVICE_KEY is required to upload private face images.")

    path = f"students/{student_id}/enrollment-{angle}.jpg"
    client.storage.from_(settings.FACE_STORAGE_BUCKET).upload(
        path,
        content,
        {
            "content-type": "image/jpeg",
            "cache-control": "3600",
            "upsert": "true",
        },
    )
    return path


def delete_face_image(path: Optional[str]) -> None:
    """Best-effort cleanup for an upload whose enrollment transaction failed."""
    if not path:
        return
    client = get_supabase()
    if client is None:
        return
    try:
        client.storage.from_(settings.FACE_STORAGE_BUCKET).remove([path])
    except Exception as error:
        logger.warning("Could not clean up face image %s: %s", path, error)


def download_face_image(path: str) -> bytes:
    """Read an enrolled face image from the private storage bucket."""
    client = get_supabase()
    if client is None:
        raise RuntimeError("Supabase is not configured; face images cannot be retrieved.")
    result = client.storage.from_(settings.FACE_STORAGE_BUCKET).download(path)
    return result if isinstance(result, bytes) else result.content
