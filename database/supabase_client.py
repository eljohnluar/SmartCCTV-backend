"""Shared Supabase client, created lazily so a boot-time failure is not permanent.

A one-shot module import meant a single unreachable network at startup left every
database route answering 503 until someone restarted the API. ``get_supabase()``
now retries, rate-limited so a genuinely missing configuration does not add a
connection attempt to every request.
"""

import time
from typing import Optional

from utils.config import settings
from utils.logger import logger

_RETRY_SECONDS = 30.0

_client_instance = None
_last_attempt = 0.0


def _has_configuration() -> bool:
    return bool(settings.SUPABASE_URL and (settings.SUPABASE_SERVICE_KEY or settings.SUPABASE_ANON_KEY))


def _attempt_connection() -> Optional[object]:
    global _client_instance, _last_attempt
    _last_attempt = time.monotonic()

    if not _has_configuration():
        logger.error("Supabase URL and key are not configured. Database requests will be unavailable.")
        return None

    try:
        from supabase import create_client
        key = settings.SUPABASE_SERVICE_KEY or settings.SUPABASE_ANON_KEY
        _client_instance = create_client(settings.SUPABASE_URL, key)
        logger.info("Supabase client initialized successfully.")
    except Exception as error:
        logger.error("Could not initialize the Supabase client: %s", error)
        _client_instance = None
    return _client_instance


def get_supabase():
    global _last_attempt
    if _client_instance is None and time.monotonic() - _last_attempt >= _RETRY_SECONDS:
        _attempt_connection()
    return _client_instance


# Establish the client at import so the first request is not charged for it.
_attempt_connection()
