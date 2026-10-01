from fastapi import Header, Request, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from database.supabase_client import get_supabase
from utils.demo_accounts import FALLBACK_USERS, hash_password
from utils.logger import logger
from utils.tokens import decode_token

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
) -> dict:
    """Return the signed token claims, or reject the request with 401."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required.")

    claims = decode_token(credentials.credentials)
    if not claims:
        raise HTTPException(status_code=401, detail="Session token is invalid or has expired. Sign in again.")
    return claims


async def require_admin(claims: dict = Security(get_current_user)) -> dict:
    if claims.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Access Denied: Administrator role required.")
    return claims


async def get_optional_account(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
) -> Optional[dict]:
    """Claims for read endpoints that stay public but scope results per teacher.

    An absent or unusable token means "no scope", not "denied" — these endpoints
    were reachable without credentials before section scoping existed.
    """
    if not credentials:
        return None
    return decode_token(credentials.credentials)


def verify_account_password(username: str, password: str) -> bool:
    expected = hash_password(password)
    client = get_supabase()
    if client:
        try:
            result = client.table("users").select("password_hash").eq("username", username).execute()
        except Exception as error:
            logger.warning("Password confirmation lookup failed for '%s': %s", username, error)
            return False
        if result.data:
            return result.data[0].get("password_hash") == expected

    account = FALLBACK_USERS.get(username)
    return bool(account) and account["password_hash"] == expected


async def require_password_confirmation(
    claims: dict = Security(get_current_user),
    confirm_password: Optional[str] = Header(default=None, alias="X-Confirm-Password"),
) -> dict:
    """
    Re-authentication gate for destructive actions.

    The caller must send their own account password in X-Confirm-Password; it is
    checked against the stored hash, so stealing a session token is not enough.
    """
    if not confirm_password:
        raise HTTPException(status_code=401, detail="Enter your password to confirm this action.")
    if not verify_account_password(claims.get("sub", ""), confirm_password):
        logger.warning("Password confirmation rejected for account '%s'", claims.get("sub"))
        raise HTTPException(status_code=401, detail="Password does not match your account.")
    return claims


async def verify_token(credentials: Optional[HTTPAuthorizationCredentials] = Security(security)):
    """
    Validates bearer token against Supabase auth.
    """
    if not credentials:
        return None

    token = credentials.credentials
    client = get_supabase()
    if not client:
        raise HTTPException(status_code=503, detail="Database authentication is not configured.")
    try:
        user = client.auth.get_user(token)
        return user
    except Exception as e:
        logger.warning(f"Token verification failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
