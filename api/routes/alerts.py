from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from database.queries import get_alerts_list, update_alert_record, create_alert_record, reset_all_alerts
from ai_engine.security.weapon_detection import weapon_detector
from ai_engine.voice.announcer import voice_announcer
from websocket_manager import publish_from_worker
from utils.logger import logger
from utils.uniform_policy import get_runtime_controls

router = APIRouter(prefix="/alerts", tags=["Alerts"])

class AlertUpdatePayload(BaseModel):
    is_resolved: Optional[bool] = None
    description: Optional[str] = None

class AlertCreatePayload(BaseModel):
    type: str
    description: str
    student_id: Optional[int] = None
    image_url: Optional[str] = None

@router.get("")
def list_alerts(
    is_resolved: Optional[bool] = Query(None),
    limit: int = Query(20, ge=1, le=100)
):
    """List recent security and threat alerts"""
    return get_alerts_list(is_resolved=is_resolved, limit=limit)

@router.post("")
def trigger_alert(payload: AlertCreatePayload):
    """Trigger a new security alert event"""
    if not get_runtime_controls()["alert_mode_enabled"]:
        raise HTTPException(status_code=409, detail="Alert mode is disabled.")
    alert = create_alert_record(
        alert_type=payload.type,
        description=payload.description,
        student_id=payload.student_id,
        image_url=payload.image_url
    )
    voice_announcer.announce_security_alert(payload.description)
    return alert

@router.put("/{alert_id}")
def update_alert(alert_id: int, payload: AlertUpdatePayload):
    """Update alert resolution status"""
    updates = {k: v for k, v in payload.dict().items() if v is not None}
    updated = update_alert_record(alert_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="Alert not found")
    return updated

@router.post("/reset")
def reset_alerts():
    """Reset / clear all security alerts and reset detection cooldowns"""
    try:
        count = reset_all_alerts()
    except Exception as e:
        logger.warning("Database reset alerts failed: %s", e)
        count = 0

    try:
        weapon_detector.reset_cooldowns()
    except Exception as e:
        logger.warning("Weapon detector cooldown reset failed: %s", e)

    publish_from_worker({
        "type": "alerts_reset",
    })

    return {
        "success": True,
        "message": "All security alerts have been reset",
        "deleted_count": count
    }
