"""Best-effort audit trail writer.

Admin and auth actions are recorded so they can be reviewed in the console. A
missing or unreachable ``audit_log`` table must never break the request that
triggered it, so failures are logged and swallowed.
"""

from typing import Any, Dict, Optional

from database.queries import insert_audit_event
from utils.logger import logger


def record_audit(
    action: str,
    description: str,
    *,
    actor: Optional[Dict[str, Any]] = None,
    target: Optional[str] = None,
    request=None,
    severity: str = "info",
) -> None:
    event = {
        "action": action,
        "description": description,
        "actor_username": (actor or {}).get("sub"),
        "actor_role": (actor or {}).get("role"),
        "target": target,
        "severity": severity,
        "ip_address": request.client.host if request and request.client else None,
    }

    try:
        insert_audit_event(event)
    except Exception as error:
        logger.warning("Audit event '%s' was not persisted: %s", action, error)
