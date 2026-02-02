from __future__ import annotations
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo
import calendar

def _last_day_of_month(y: int, m: int) -> int:
    return calendar.monthrange(y, m)[1]

def calc_next_charge_date_monthly(now_local: datetime, day: int) -> date:
    y, m = now_local.year, now_local.month
    ld = _last_day_of_month(y, m)
    d = min(day, ld)
    candidate = date(y, m, d)
    if candidate >= now_local.date():
        return candidate

    # next month
    if m == 12:
        y2, m2 = y + 1, 1
    else:
        y2, m2 = y, m + 1

    ld2 = _last_day_of_month(y2, m2)
    d2 = min(day, ld2)
    return date(y2, m2, d2)

def calc_next_charge_date_yearly(now_local: datetime, month: int, dom: int) -> date:
    y = now_local.year

    def safe_date(yy: int) -> date:
        # правило: 29 Feb в невисокосный год -> 28 Feb
        if month == 2 and dom == 29 and not calendar.isleap(yy):
            return date(yy, 2, 28)
        ld = _last_day_of_month(yy, month)
        d = min(dom, ld)
        return date(yy, month, d)

    candidate = safe_date(y)
    if candidate >= now_local.date():
        return candidate
    return safe_date(y + 1)

def local_remind_at_days(charge_date: date, days_before: int, reminder_hour: int, tz: str) -> datetime:
    z = ZoneInfo(tz)
    local_dt = datetime.combine(charge_date - timedelta(days=days_before), time(reminder_hour, 0), tzinfo=z)
    return local_dt

def to_utc(dt_local: datetime) -> datetime:
    # dt_local must be aware
    return dt_local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)  # store naive UTC

def utc_now() -> datetime:
    return datetime.utcnow()
