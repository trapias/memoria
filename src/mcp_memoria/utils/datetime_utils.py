"""Datetime utility functions for MCP Memoria."""

from datetime import datetime
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
