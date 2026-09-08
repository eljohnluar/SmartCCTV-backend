from fastapi import Request, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from database.supabase_client import get_supabase
from utils.logger import logger

security = HTTPBearer(auto_error=False)

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
