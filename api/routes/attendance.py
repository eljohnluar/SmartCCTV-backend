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
    get_all_students
)

router = APIRouter(prefix="/attendance", tags=["Attendance"])

def calculate_stats(records: List[dict], total_enrolled: int) -> AttendanceStats:
    total = len(records)
    present = sum(1 for r in records if r.get("status") == "present")
    absent = sum(1 for r in records if r.get("status") == "absent")
    late = sum(1 for r in records if r.get("status") == "late")
    effective_total = total_enrolled if total_enrolled > 0 else total
    rate = round(((present + late) / effective_total * 100), 1) if effective_total > 0 else 0.0
    return AttendanceStats(
        total=effective_total,
        present=present,
        absent=absent,
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
    """Manually override or record student attendance status"""
    record = mark_attendance(
        student_id=payload.student_id,
        status=payload.status,
        confidence=payload.confidence
    )
    return {
        "success": True,
        "message": f"Attendance updated for student {payload.student_id}",
        "record": record
    }
