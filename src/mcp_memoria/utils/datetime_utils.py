"""Datetime utility functions for MCP Memoria."""

import re
from datetime import UTC, datetime, timedelta
from typing import Any


def parse_datetime(value: Any, field_name: str = "unknown") -> datetime:
    """Parse datetime from various formats safely.

    Handles string (ISO format), datetime objects, and None values.

    Args:
        value: Value to parse (string, datetime, or None)
        field_name: Field name for logging (optional)

    Returns:
        datetime object. Returns current time if value is None.
    """
    if value is None:
        return datetime.now()
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            # Try common formats
            for fmt in [
                "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
            ]:
                try:
                    return datetime.strptime(value, fmt)
                except ValueError:
                    continue
            # If all parsing fails, return now
            return datetime.now()
    # Fallback for any other type
    return datetime.now()


# Patterns for natural language date parsing (IT + EN)
_TEMPORAL_PATTERNS: list[tuple[re.Pattern, Any]] = [
    # Italian
    (re.compile(r"\boggi\b", re.IGNORECASE), lambda: timedelta(days=0)),
    (re.compile(r"\bieri\b", re.IGNORECASE), lambda: timedelta(days=1)),
    (re.compile(r"\bl['']?altro\s*ieri\b", re.IGNORECASE), lambda: timedelta(days=2)),
    (re.compile(r"\bquesta\s+settimana\b", re.IGNORECASE), lambda: timedelta(days=7)),
    (re.compile(r"\bsettimana\s+scorsa\b", re.IGNORECASE), lambda: timedelta(days=14)),
    (re.compile(r"\bquesto\s+mese\b", re.IGNORECASE), lambda: timedelta(days=30)),
    (re.compile(r"\bmese\s+scorso\b", re.IGNORECASE), lambda: timedelta(days=60)),
    (re.compile(r"\bultim[io]\s+(\d+)\s+giorn[io]\b", re.IGNORECASE), None),  # dynamic
    (re.compile(r"\bultim[ea]\s+(\d+)\s+settiman[ea]\b", re.IGNORECASE), None),  # dynamic
    (re.compile(r"\bultim[io]\s+(\d+)\s+mes[ei]\b", re.IGNORECASE), None),  # dynamic
    # English
    (re.compile(r"\btoday\b", re.IGNORECASE), lambda: timedelta(days=0)),
    (re.compile(r"\byesterday\b", re.IGNORECASE), lambda: timedelta(days=1)),
    (re.compile(r"\bthis\s+week\b", re.IGNORECASE), lambda: timedelta(days=7)),
    (re.compile(r"\blast\s+week\b", re.IGNORECASE), lambda: timedelta(days=14)),
    (re.compile(r"\bthis\s+month\b", re.IGNORECASE), lambda: timedelta(days=30)),
    (re.compile(r"\blast\s+month\b", re.IGNORECASE), lambda: timedelta(days=60)),
    (re.compile(r"\blast\s+(\d+)\s+days?\b", re.IGNORECASE), None),  # dynamic
    (re.compile(r"\blast\s+(\d+)\s+weeks?\b", re.IGNORECASE), None),  # dynamic
    (re.compile(r"\blast\s+(\d+)\s+months?\b", re.IGNORECASE), None),  # dynamic
]


def parse_temporal_query(text: str) -> tuple[str, datetime | None, datetime | None]:
    """Extract temporal references from a query and return date range.

    Parses natural language date references in Italian and English,
    returning the cleaned query and date bounds.

    Args:
        text: Query text potentially containing temporal references

    Returns:
        Tuple of (cleaned_query, date_from, date_to)
        date_from/date_to are None if no temporal reference found.
    """
    now = datetime.now(UTC)
    cleaned = text

    for pattern, delta_fn in _TEMPORAL_PATTERNS:
        match = pattern.search(cleaned)
        if match:
            if delta_fn is not None:
                # Fixed delta
                delta = delta_fn()
                date_from = now - delta
                # For "today"/"oggi", set date_from to start of day
                if delta == timedelta(days=0):
                    date_from = now.replace(hour=0, minute=0, second=0, microsecond=0)
                # Remove the matched text from query
                cleaned = pattern.sub("", cleaned).strip()
                return cleaned or text, date_from, now
            else:
                # Dynamic: extract the number from the match group
                num = int(match.group(1))
                matched_text = match.group(0).lower()

                if "giorn" in matched_text or "day" in matched_text:
                    delta = timedelta(days=num)
                elif "settiman" in matched_text or "week" in matched_text:
                    delta = timedelta(weeks=num)
                elif "mes" in matched_text or "month" in matched_text:
                    delta = timedelta(days=num * 30)
                else:
                    continue

                date_from = now - delta
                cleaned = pattern.sub("", cleaned).strip()
                return cleaned or text, date_from, now

    return text, None, None
