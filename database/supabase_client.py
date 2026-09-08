from typing import Optional
from utils.config import settings
from utils.logger import logger

supabase_client = None

try:
    if settings.SUPABASE_URL and (settings.SUPABASE_SERVICE_KEY or settings.SUPABASE_ANON_KEY):
        from supabase import create_client, Client
        key = settings.SUPABASE_SERVICE_KEY or settings.SUPABASE_ANON_KEY
        supabase_client: Optional[Client] = create_client(settings.SUPABASE_URL, key)
        logger.info("Supabase client initialized successfully.")
    else:
        logger.error("Supabase URL and key are not configured. Database requests will be unavailable.")
except Exception as e:
    logger.error(f"Could not initialize the Supabase client: {e}")

def get_supabase():
    return supabase_client
