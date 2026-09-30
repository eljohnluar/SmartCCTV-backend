import time
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from api.middleware.auth import get_current_user
from database.supabase_client import get_supabase
from utils.audit import record_audit
from utils.config import settings
from utils.demo_accounts import (
    DEMO_PASSWORDS,
    create_fallback,
    find_fallback,
    hash_password,
)
from utils.logger import logger
from utils.tokens import create_token

router = APIRouter(prefix="/auth", tags=["Auth"])

class LoginRequest(BaseModel):
    username: str = Field(..., description="Account username or email")
    password: str = Field(..., description="Account password")

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=4)
    full_name: Optional[str] = None
    registration_code: str = Field(..., description="Administrator clearance code")
    email: Optional[str] = None

def _public_user(row: dict) -> dict:
    return {
        "id": row.get("id"),
        "username": row.get("username"),
        "full_name": row.get("full_name") or str(row.get("username", "")).title(),
        "role": row.get("role", "teacher"),
        "email": row.get("email", ""),
        # Lets the teacher console limit section choices without a second request
        "year_levels": row.get("year_levels") or [],
        "sections": row.get("sections") or [],
    }


def _store_fallback(record: dict) -> int:
    try:
        return create_fallback(record)["id"]
    except ValueError as conflict:
        raise HTTPException(status_code=409, detail=str(conflict))

@router.post("/register")
def register(data: RegisterRequest, request: Request):
    """Register a new Administrator account. Teacher accounts are provisioned by an administrator."""
    code = (data.registration_code or "").strip().upper()
    if code != settings.ADMIN_REGISTRATION_CODE.upper():
        logger.warning("Registration denied: invalid clearance code for user '%s'", data.username)
        record_audit(
            "registration_denied",
            f"Registration for '{data.username}' was rejected by the clearance check.",
            target=data.username,
            request=request,
            severity="warning",
        )
        raise HTTPException(
            status_code=403,
            detail="Access Denied: an administrator clearance code is required to register.",
        )

    clean_username = data.username.strip().lower()
    if not clean_username:
        raise HTTPException(status_code=400, detail="Username cannot be blank.")

    client = get_supabase()
    password_hash = hash_password(data.password)
    full_name = (data.full_name or clean_username).strip()
    email = (data.email or f"{clean_username}@school.internal").strip().lower()
    role = "admin"

    new_record = {
        "username": clean_username,
        "email": email,
        "password_hash": password_hash,
        "full_name": full_name,
        "role": role,
        "registration_code": settings.ADMIN_REGISTRATION_CODE,
        "is_active": True,
    }

    if client:
        try:
            existing = client.table("users").select("id, username").eq("username", clean_username).execute()
            if existing.data and len(existing.data) > 0:
                raise HTTPException(status_code=409, detail=f"Username '{clean_username}' is already registered.")

            res = client.table("users").insert(new_record).execute()
            user_data = res.data[0] if res.data else new_record
            user_id = user_data.get("id", int(time.time()))
        except HTTPException:
            raise
        except Exception as err:
            failure = str(err).lower()
            if "users_role_check" in failure or ("role" in failure and "constraint" in failure):
                raise HTTPException(
                    status_code=422,
                    detail="The users table still restricts roles to 'teacher'. Run backend/database/admin_schema.sql in the Supabase SQL Editor, then try again.",
                )
            logger.warning("Supabase users table insert failed (%s). Using fallback persistence.", err)
            user_id = _store_fallback(new_record)
    else:
        user_id = _store_fallback(new_record)

    user = {"id": user_id, "username": clean_username, "full_name": full_name, "role": role, "email": email}
    record_audit(
        "admin_registered",
        f"Administrator account '{clean_username}' was created.",
        actor={"sub": clean_username, "role": role},
        target=clean_username,
        request=request,
        severity="warning",
    )
    logger.info("New administrator account registered: %s", clean_username)
    return {
        "access_token": create_token(clean_username, role, user_id),
        "token_type": "bearer",
        "user": user,
        "message": "Administrator account authorized. Teacher accounts are created from Teacher Management.",
    }

@router.post("/login")
def login(creds: LoginRequest, request: Request):
    """Authenticate an administrator or teacher with username/email and password."""
    clean_identifier = creds.username.strip().lower()
    provided_hash = hash_password(creds.password)

    client = get_supabase()
    matched_user = None

    if client:
        try:
            res = client.table("users").select("*").or_(
                f"username.eq.{clean_identifier},email.eq.{clean_identifier}"
            ).execute()
            if res.data and len(res.data) > 0:
                user_row = res.data[0]
                if user_row.get("password_hash") == provided_hash:
                    if user_row.get("is_active") is False:
                        raise HTTPException(status_code=403, detail="This account has been deactivated by an administrator.")
                    matched_user = user_row
                    try:
                        client.table("users").update({"last_login_at": "now()"}).eq("id", user_row["id"]).execute()
                    except Exception:
                        pass
        except HTTPException:
            raise
        except Exception as e:
            logger.warning("Supabase user login query failed (%s). Checking fallback store.", e)

    # Check fallback store if not matched via Supabase
    if not matched_user:
        candidate = find_fallback(clean_identifier)
        if candidate and candidate["password_hash"] == provided_hash:
            matched_user = candidate

    # Demo credentials for the offline prototype, so the console stays reviewable without a database
    if not matched_user and clean_identifier in ("teacher", "admin") and creds.password in DEMO_PASSWORDS:
        matched_user = find_fallback(clean_identifier)

    if not matched_user:
        logger.warning("Failed login attempt for user '%s'", creds.username)
        record_audit(
            "login_failed",
            f"Rejected sign-in attempt for '{creds.username}'.",
            target=clean_identifier,
            request=request,
            severity="warning",
        )
        raise HTTPException(
            status_code=401,
            detail="Authentication failed: Invalid username or password."
        )

    role = matched_user.get("role", "teacher")
    user = _public_user(matched_user)
    record_audit(
        "login",
        f"{user['username']} signed in as {role}.",
        actor={"sub": user["username"], "role": role},
        target=user["username"],
        request=request,
    )
    logger.info("Login verified: %s (role: %s)", user["username"], role)
    return {
        "access_token": create_token(user["username"], role, user["id"]),
        "token_type": "bearer",
        "user": user,
    }

@router.get("/me")
def read_current_user(claims: dict = Depends(get_current_user)):
    """Return the identity carried by the bearer token."""
    return {"username": claims.get("sub"), "role": claims.get("role"), "id": claims.get("uid")}
