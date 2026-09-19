from fastapi import APIRouter, HTTPException
from typing import List, Optional
from datetime import date
from api.models.attendance import (
    AttendanceManualMark,
    AttendanceRecord,
    AttendanceStats,
    TodayAttendanceResponse
)
from database.queries import (
    get_attendance_for_date,
    mark_attendance,
    get_all_students,
    reset_attendance_for_date,
)
from ai_engine.face_recognition.live_matcher import live_face_matcher
from websocket_manager import publish_from_worker
from utils.logger import logger

router = APIRouter(prefix="/attendance", tags=["Attendance"])

def calculate_stats(records: List[dict], total_enrolled: int) -> AttendanceStats:
    total = len(records)
    present = sum(1 for r in records if r.get("status") == "present")
    late = sum(1 for r in records if r.get("status") == "late")
    effective_total = total_enrolled if total_enrolled > 0 else total
    rate = round(((present + late) / effective_total * 100), 1) if effective_total > 0 else 0.0
    return AttendanceStats(
        total=effective_total,
        present=present,
        late=late,
        rate=rate
    )

@router.get("/today", response_model=TodayAttendanceResponse)
def get_today_attendance():
    """Fetch attendance records and live summary metrics for today"""
    today_str = date.today().isoformat()
    records = get_attendance_for_date(today_str)
    all_students = get_all_students()
    stats = calculate_stats(records, len(all_students))
    return TodayAttendanceResponse(
        date=today_str,
        stats=stats,
        records=records
    )

@router.get("/date/{query_date}", response_model=TodayAttendanceResponse)
def get_attendance_by_date(query_date: str):
    """Fetch attendance records for a specific historical date (YYYY-MM-DD)"""
    records = get_attendance_for_date(query_date)
    all_students = get_all_students()
    stats = calculate_stats(records, len(all_students))
    return TodayAttendanceResponse(
        date=query_date,
        stats=stats,
        records=records
    )

@router.post("/manual")
def manual_mark(payload: AttendanceManualMark):
    """Record attendance and derive status from the check-in time."""
    record = mark_attendance(
        student_id=payload.student_id,
        confidence=payload.confidence,
        check_in_time=payload.check_in_time,
    )
    return {
        "success": True,
        "message": f"Attendance updated for student {payload.student_id}",
        "record": record
    }

@router.post("/reset")
def reset_attendance():
    """Reset all marked attendance records for today"""
    today_str = date.today().isoformat()
    try:
        count = reset_attendance_for_date(today_str)
    except Exception as e:
        logger.warning(f"Database reset attendance failed: {e}")
        count = 0

    # Clear in-memory live face matcher cache so students can be recognized again
    live_face_matcher.reset_marked()

    # Broadcast reset event over WebSocket so all connected dashboards clear marked state
    publish_from_worker({
        "type": "attendance_reset",
        "class_date": today_str,
    })

    return {
        "success": True,
        "message": f"Attendance records reset for {today_str}",
        "deleted_count": count
    }
