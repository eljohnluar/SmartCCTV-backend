from datetime import datetime, date
from typing import Any, Dict

def get_today_date_str() -> str:
    return date.today().isoformat()

def get_current_timestamp_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"

def format_percentage(value: float, total: float) -> float:
    if not total:
        return 0.0
    return round((value / total) * 100, 1)
