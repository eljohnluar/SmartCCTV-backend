from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from database.queries import get_alerts_list, update_alert_record, create_alert_record

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
    alert = create_alert_record(
        alert_type=payload.type,
        description=payload.description,
        student_id=payload.student_id,
        image_url=payload.image_url
    )
    return alert

@router.put("/{alert_id}")
def update_alert(alert_id: int, payload: AlertUpdatePayload):
    """Update alert resolution status"""
    updates = {k: v for k, v in payload.dict().items() if v is not None}
    updated = update_alert_record(alert_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="Alert not found")
    return updated
