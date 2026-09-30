"""Signed, dependency-free session tokens.

Tokens are ``<payload>.<signature>`` where the payload is base64url JSON and the
signature is HMAC-SHA256 over it, so the server can trust the role claim without
a JWT library.
"""

import base64
import hashlib
import hmac
import json
import time
from typing import Optional

from utils.config import settings


def _encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(body: str) -> str:
    key = settings.AUTH_SECRET.encode()
    return _encode(hmac.new(key, body.encode(), hashlib.sha256).digest())


def create_token(username: str, role: str, user_id, ttl_hours: Optional[int] = None) -> str:
    issued_at = int(time.time())
    payload = {
        "sub": username,
        "role": role,
        "uid": user_id,
        "iat": issued_at,
        "exp": issued_at + 3600 * (ttl_hours or settings.AUTH_TOKEN_TTL_HOURS),
    }
    body = _encode(json.dumps(payload, separators=(",", ":")).encode())
    return f"{body}.{_sign(body)}"


def decode_token(token: str) -> Optional[dict]:
    if not token or "." not in token:
        return None

    body, signature = token.rsplit(".", 1)
    if not hmac.compare_digest(signature, _sign(body)):
        return None

    try:
        payload = json.loads(_decode(body))
    except (ValueError, TypeError):
        return None

    if not isinstance(payload, dict) or payload.get("exp", 0) < time.time():
        return None
    return payload
