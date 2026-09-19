import hashlib
import time
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from database.supabase_client import get_supabase
from utils.logger import logger

router = APIRouter(prefix="/auth", tags=["Auth"])

# Mandatory teacher registration code
HARDCODED_TEACHER_CODE = "TEACHER2026"
SALT = "smartcctv_salt_"

# Local in-memory / fallback store if Supabase `users` table hasn't been migrated yet
_FALLBACK_USERS = {
    "teacher": {
        "id": 1,
        "username": "teacher",
        "email": "teacher@smartcctv.edu",
        "password_hash": hashlib.sha256(f"{SALT}password123".encode()).hexdigest(),
        "full_name": "Faculty Instructor",
        "role": "teacher",
        "registration_code": HARDCODED_TEACHER_CODE,
    }
}

def hash_password(password: str) -> str:
    return hashlib.sha256(f"{SALT}{password}".encode()).hexdigest()

class LoginRequest(BaseModel):
    username: str = Field(..., description="Teacher username or email")
    password: str = Field(..., description="Teacher password")

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=4)
    full_name: Optional[str] = None
    registration_code: str = Field(..., description="Must be TEACHER2026")
    email: Optional[str] = None

@router.post("/register")
def register(data: RegisterRequest):
    """Register a new Teacher account. Clearance code TEACHER2026 is required."""
    code = (data.registration_code or "").strip()
    if code.upper() != HARDCODED_TEACHER_CODE:
        logger.warning("Registration denied: Invalid registration code '%s' for user '%s'", code, data.username)
        raise HTTPException(
            status_code=403,
            detail=f"Access Denied: Invalid registration code. Institutional clearance '{HARDCODED_TEACHER_CODE}' is required to register."
        )

    clean_username = data.username.strip().lower()
    if not clean_username:
        raise HTTPException(status_code=400, detail="Username cannot be blank.")

    client = get_supabase()
    password_hash = hash_password(data.password)
    full_name = (data.full_name or clean_username).strip()
    email = (data.email or f"{clean_username}@school.internal").strip().lower()
    role = "teacher"  # Strictly teacher role

    # Check database if available
    if client:
        try:
            # Check existing username
            existing = client.table("users").select("id, username").eq("username", clean_username).execute()
            if existing.data and len(existing.data) > 0:
                raise HTTPException(status_code=409, detail=f"Username '{clean_username}' is already registered.")

            # Insert new user record
            new_record = {
                "username": clean_username,
                "email": email,
                "password_hash": password_hash,
                "full_name": full_name,
                "role": role,
                "registration_code": HARDCODED_TEACHER_CODE,
                "is_active": True,
            }
            res = client.table("users").insert(new_record).execute()
            user_data = res.data[0] if res.data else new_record
            user_id = user_data.get("id", int(time.time()))
        except HTTPException:
            raise
        except Exception as err:
            logger.warning("Supabase users table insert failed (%s). Using fallback persistence.", err)
            # Fallback to local memory dictionary if users table not yet run in Supabase
            if clean_username in _FALLBACK_USERS:
                raise HTTPException(status_code=409, detail=f"Username '{clean_username}' is already registered.")
            user_id = len(_FALLBACK_USERS) + 1
            _FALLBACK_USERS[clean_username] = {
                "id": user_id,
                "username": clean_username,
                "email": email,
                "password_hash": password_hash,
                "full_name": full_name,
                "role": role,
                "registration_code": HARDCODED_TEACHER_CODE,
            }
    else:
        if clean_username in _FALLBACK_USERS:
            raise HTTPException(status_code=409, detail=f"Username '{clean_username}' is already registered.")
        user_id = len(_FALLBACK_USERS) + 1
        _FALLBACK_USERS[clean_username] = {
            "id": user_id,
            "username": clean_username,
            "email": email,
            "password_hash": password_hash,
            "full_name": full_name,
            "role": role,
            "registration_code": HARDCODED_TEACHER_CODE,
        }

    token = f"smartcctv_token_{clean_username}_{int(time.time())}"
    logger.info("New teacher account registered: %s (Role: %s)", clean_username, role)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user_id,
            "username": clean_username,
            "full_name": full_name,
            "role": role,
            "email": email,
        },
        "message": "Teacher account successfully authorized and registered."
    }

@router.post("/login")
def login(creds: LoginRequest):
    """Authenticate Teacher with username/email and password."""
    clean_identifier = creds.username.strip().lower()
    provided_hash = hash_password(creds.password)

    client = get_supabase()
    matched_user = None

    if client:
        try:
            # Query users table by username or email
            res = client.table("users").select("*").or_(
                f"username.eq.{clean_identifier},email.eq.{clean_identifier}"
            ).execute()
            if res.data and len(res.data) > 0:
                user_row = res.data[0]
                if user_row.get("password_hash") == provided_hash:
                    matched_user = user_row
                    # Update last login timestamp asynchronously / quietly
                    try:
                        client.table("users").update({"last_login_at": "now()"}).eq("id", user_row["id"]).execute()
                    except Exception:
                        pass
        except Exception as e:
            logger.warning("Supabase user login query failed (%s). Checking fallback store.", e)

    # Check fallback store if not matched via Supabase
    if not matched_user:
        for u in _FALLBACK_USERS.values():
            if (u["username"] == clean_identifier or u.get("email") == clean_identifier) and u["password_hash"] == provided_hash:
                matched_user = u
                break

    # Also support default administrator / teacher credentials
    if not matched_user and clean_identifier in ("teacher", "admin") and creds.password in ("password123", "teacher2026"):
        matched_user = {
            "id": 1,
            "username": "teacher",
            "full_name": "Faculty Instructor",
            "role": "teacher",
            "email": "teacher@smartcctv.edu",
        }

    if not matched_user:
        logger.warning("Failed login attempt for user '%s'", creds.username)
        raise HTTPException(
            status_code=401,
            detail="Authentication failed: Invalid username or password."
        )

    # Confirm user is teacher
    role = matched_user.get("role", "teacher")
    if role != "teacher":
        raise HTTPException(
            status_code=403,
            detail="Access Denied: Only users with the Teacher role are authorized to access this system."
        )

    token = f"smartcctv_token_{matched_user['username']}_{int(time.time())}"
    logger.info("Teacher login verified: %s", matched_user["username"])
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": matched_user.get("id", 1),
            "username": matched_user.get("username", clean_identifier),
            "full_name": matched_user.get("full_name") or matched_user.get("username", "Teacher").title(),
            "role": "teacher",
            "email": matched_user.get("email", ""),
        }
    }
