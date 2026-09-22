"""UTC lookback / watermark helpers for incremental HAL pulls."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def format_hal_date(dt: datetime) -> str:
    """ISO-8601 UTC timestamp accepted by HAL Solr date ranges."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_hal_date(value: str) -> datetime | None:
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def lookback_since(days: float, *, now: datetime | None = None) -> str:
    base = now or utc_now()
    return format_hal_date(base - timedelta(days=days))


def read_watermark(meta_path: Path) -> str | None:
    """Read watermark_modified from a harvest/census *.meta.json sidecar."""
    if not meta_path.exists():
        return None
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    value = data.get("watermark_modified")
    return value if isinstance(value, str) and value.strip() else None


def effective_since(
    *,
    since: str | None = None,
    lookback_days: float | None = None,
    watermark: str | None = None,
    safety_hours: float = 1.0,
    now: datetime | None = None,
) -> str | None:
    """
    Resolve the Solr modifiedDate lower bound.

    Priority:
    1. Explicit ``since`` if provided.
    2. Otherwise the earlier (more inclusive) of:
       - watermark minus ``safety_hours``
       - now minus ``lookback_days`` (when lookback_days is set)
    """
    if since:
        return since

    base = now or utc_now()
    candidates: list[datetime] = []

    if lookback_days is not None:
        candidates.append(base - timedelta(days=lookback_days))

    if watermark:
        wm = parse_hal_date(watermark)
        if wm is not None:
            candidates.append(wm - timedelta(hours=safety_hours))

    if not candidates:
        return None
    return format_hal_date(min(candidates))
