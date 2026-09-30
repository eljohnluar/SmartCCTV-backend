"""In-memory account store used when Supabase is not configured.

The prototype has to stay reviewable without a database, so the demo teacher and
administrator accounts live here and admin routes fall back to this store. It is
never consulted when Supabase is configured.
"""

import hashlib
from typing import Any, Dict, List, Optional

from utils.config import settings

SALT = "smartcctv_salt_"

DEMO_PASSWORDS = ("password123", "admin123", "teacher2026")


def hash_password(password: str) -> str:
    return hashlib.sha256(f"{SALT}{password}".encode()).hexdigest()


FALLBACK_USERS: Dict[str, Dict[str, Any]] = {
    "teacher": {
        "id": 1,
        "username": "teacher",
        "email": "teacher@smartcctv.edu",
        "password_hash": hash_password("password123"),
        "full_name": "Faculty Instructor",
        "role": "teacher",
        "registration_code": settings.TEACHER_PROVISIONING_CODE,
        "is_active": True,
        "year_levels": [],
        "sections": [],
        "last_login_at": None,
        "created_at": None,
    },
    "admin": {
        "id": 2,
        "username": "admin",
        "email": "admin@smartcctv.edu",
        "password_hash": hash_password("password123"),
        "full_name": "System Administrator",
        "role": "admin",
        "registration_code": settings.ADMIN_REGISTRATION_CODE,
        "is_active": True,
        "year_levels": [],
        "sections": [],
        "last_login_at": None,
        "created_at": None,
    },
}


def public_account(row: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in row.items() if key != "password_hash"}


def find_fallback(identifier: str) -> Optional[Dict[str, Any]]:
    for account in FALLBACK_USERS.values():
        if account["username"] == identifier or account.get("email") == identifier:
            return account
    return None


def list_fallback(role: Optional[str] = None) -> List[Dict[str, Any]]:
    accounts = [public_account(account) for account in FALLBACK_USERS.values()]
    if role:
        accounts = [account for account in accounts if account.get("role") == role]
    return sorted(accounts, key=lambda account: (account.get("full_name") or "").lower())


def create_fallback(record: Dict[str, Any]) -> Dict[str, Any]:
    username = record["username"]
    if username in FALLBACK_USERS:
        raise ValueError(f"Username '{username}' is already registered.")
    account = {**record, "id": max((user["id"] for user in FALLBACK_USERS.values()), default=0) + 1}
    FALLBACK_USERS[username] = account
    return public_account(account)


def update_fallback(user_id: int, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    for account in FALLBACK_USERS.values():
        if account["id"] == user_id:
            account.update(updates)
            return public_account(account)
    return None


def delete_fallback(user_id: int) -> bool:
    for username, account in list(FALLBACK_USERS.items()):
        if account["id"] == user_id:
            del FALLBACK_USERS[username]
            return True
    return False
