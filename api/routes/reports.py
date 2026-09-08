import csv
import io
from collections import defaultdict
from datetime import date, timedelta
from typing import Optional, Tuple

from fastapi import APIRouter, HTTPException, Query, Response

from database.queries import get_all_students, get_attendance_in_range

router = APIRouter(prefix="/reports", tags=["Reports"])


def _parse_date_range(date_from: Optional[str], date_to: Optional[str]) -> Tuple[date, date]:
    try:
        end = date.fromisoformat(date_to) if date_to else date.today()
        start = date.fromisoformat(date_from) if date_from else end - timedelta(days=7)
    except ValueError as error:
        raise HTTPException(status_code=422, detail="dateFrom and dateTo must use YYYY-MM-DD.") from error
    if start > end:
        raise HTTPException(status_code=422, detail="dateFrom cannot be after dateTo.")
    return start, end


def _records_for_range(date_from: Optional[str], date_to: Optional[str], section: Optional[str]):
    start, end = _parse_date_range(date_from, date_to)
    return start, end, get_attendance_in_range(start.isoformat(), end.isoformat(), section or None)


@router.get("/summary")
def get_summary(
    date_from: Optional[str] = Query(None, alias="dateFrom"),
    date_to: Optional[str] = Query(None, alias="dateTo"),
    section: Optional[str] = None,
):
    """Get attendance metrics calculated from database records."""
    start, end, records = _records_for_range(date_from, date_to, section)
    total_students = len(get_all_students(section or None))
    present = sum(record["status"] == "present" for record in records)
    absent = sum(record["status"] == "absent" for record in records)
    late = sum(record["status"] == "late" for record in records)

    daily_rates = []
    records_by_date = defaultdict(list)
    for record in records:
        records_by_date[record["class_date"]].append(record)
    for daily_records in records_by_date.values():
        attended = sum(record["status"] in {"present", "late"} for record in daily_records)
        daily_rates.append((attended / total_students) * 100 if total_students else 0)

    return {
        "avg_rate": round(sum(daily_rates) / len(daily_rates), 1) if daily_rates else 0,
        "total_present": present,
        "total_absent": absent,
        "total_late": late,
        "total_students": total_students,
        "date_from": start.isoformat(),
        "date_to": end.isoformat(),
        "section": section or "All Sections",
    }


@router.get("/trend")
def get_trend(
    date_from: Optional[str] = Query(None, alias="dateFrom"),
    date_to: Optional[str] = Query(None, alias="dateTo"),
    section: Optional[str] = None,
):
    """Get daily attendance-rate data calculated from the database."""
    start, end, records = _records_for_range(date_from, date_to, section)
    total_students = len(get_all_students(section or None))
    records_by_date = defaultdict(list)
    for record in records:
        records_by_date[record["class_date"]].append(record)

    trend = []
    current_date = start
    while current_date <= end:
        daily_records = records_by_date[current_date.isoformat()]
        attended = sum(record["status"] in {"present", "late"} for record in daily_records)
        rate = round((attended / total_students) * 100, 1) if total_students else 0
        trend.append({"date": current_date.strftime("%a %b %d"), "rate": rate})
        current_date += timedelta(days=1)
    return trend


@router.get("/records")
def get_records(
    date_from: Optional[str] = Query(None, alias="dateFrom"),
    date_to: Optional[str] = Query(None, alias="dateTo"),
    section: Optional[str] = None,
):
    """Return detailed attendance rows for the selected report range."""
    _, _, records = _records_for_range(date_from, date_to, section)
    return records


@router.get("/export/csv")
def export_csv(
    date_from: Optional[str] = Query(None, alias="dateFrom"),
    date_to: Optional[str] = Query(None, alias="dateTo"),
    section: Optional[str] = None,
):
    """Export attendance rows from the database as CSV."""
    start, end, records = _records_for_range(date_from, date_to, section)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Student ID", "Student Name", "Section", "Status", "Check-in Time", "Confidence"])
    for record in records:
        confidence = f"{record['confidence'] * 100:.1f}%" if record["confidence"] is not None else ""
        writer.writerow([
            record["class_date"], record["student_code"], record["student_name"], record["section"],
            record["status"], record["check_in_time"] or "", confidence,
        ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=attendance_report_{start}_to_{end}.csv"},
    )
