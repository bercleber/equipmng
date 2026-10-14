from datetime import datetime, timezone


def as_utc(value: datetime) -> datetime:
    """Legacy datetimes without an offset are interpreted as UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def database_datetime(value: datetime) -> datetime:
    """MySQL DATETIME stores UTC without timezone information."""
    return as_utc(value).replace(tzinfo=None)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
