from fastapi import Request, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from database.supabase_client import get_supabase
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
