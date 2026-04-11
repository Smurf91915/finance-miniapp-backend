from collections.abc import Iterable
from datetime import date, datetime, time, timedelta, timezone

from fastapi import HTTPException


def current_month_bounds() -> tuple[date, date]:
    today = datetime.now(timezone.utc).date()
    start = today.replace(day=1)
    if start.month == 12:
        next_month = start.replace(year=start.year + 1, month=1, day=1)
    else:
        next_month = start.replace(month=start.month + 1, day=1)
    end = next_month - timedelta(days=1)
    return start, end


def date_range_to_datetimes(start: date | None, end: date | None) -> tuple[datetime, datetime, date, date]:
    period_start, period_end = current_month_bounds()
    start_date = start or period_start
    end_date = end or period_end
    if end_date < start_date:
        raise HTTPException(status_code=400, detail="'to' must be greater than or equal to 'from'")
    start_dt = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
    end_dt = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=timezone.utc)
    return start_dt, end_dt, start_date, end_date


def ensure_positive(amount_minor: int) -> None:
    if amount_minor <= 0:
        raise HTTPException(status_code=400, detail="amount_minor must be greater than zero")


def ensure_choice(value: str, allowed: Iterable[str], field_name: str) -> None:
    if value not in allowed:
        allowed_text = ", ".join(sorted(allowed))
        raise HTTPException(status_code=400, detail=f"{field_name} must be one of: {allowed_text}")
