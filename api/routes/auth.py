from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from database.supabase_client import get_supabase
from utils.logger import logger

router = APIRouter(prefix="/auth", tags=["Auth"])

class LoginRequest(BaseModel):
    email: str
    password: str

@router.post("/login")
def login(creds: LoginRequest):
    """Authenticate administrator using Supabase Auth"""
    client = get_supabase()
    if not client:
        raise HTTPException(status_code=503, detail="Database authentication is not configured.")
    try:
        res = client.auth.sign_in_with_password({
            "email": creds.email,
            "password": creds.password
        })
        return {
            "access_token": res.session.access_token,
            "token_type": "bearer",
            "user": res.user
        }
    except Exception as e:
        logger.warning(f"Supabase login failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
