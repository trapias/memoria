"""Tests for datetime utility functions."""

from datetime import datetime

import pytest
from mcp_memoria.utils.datetime_utils import parse_datetime


class TestParseDatetime:
    """Tests for parse_datetime function."""

    def test_parse_none_returns_now(self) -> None:
        """Test that None returns current datetime."""
        before = datetime.now()
        result = parse_datetime(None)
        after = datetime.now()
        assert before <= result <= after

    def test_parse_datetime_object(self) -> None:
        """Test that datetime objects are returned as-is."""
        dt = datetime(2024, 1, 15, 10, 30, 0)
        result = parse_datetime(dt)
        assert result == dt

    def test_parse_iso_string(self) -> None:
        """Test parsing ISO format string."""
        iso_str = "2024-01-15T10:30:00"
        result = parse_datetime(iso_str)
        assert result == datetime(2024, 1, 15, 10, 30, 0)

    def test_parse_iso_string_with_microseconds(self) -> None:
        """Test parsing ISO format string with microseconds."""
        iso_str = "2024-01-15T10:30:00.123456"
        result = parse_datetime(iso_str)
        assert result == datetime(2024, 1, 15, 10, 30, 0, 123456)

    def test_parse_date_only_string(self) -> None:
        """Test parsing date-only string."""
        date_str = "2024-01-15"
        result = parse_datetime(date_str)
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_parse_datetime_with_space(self) -> None:
        """Test parsing datetime with space separator."""
        dt_str = "2024-01-15 10:30:00"
        result = parse_datetime(dt_str)
        assert result == datetime(2024, 1, 15, 10, 30, 0)

    def test_parse_invalid_string_returns_now(self) -> None:
        """Test that invalid strings return current datetime."""
        before = datetime.now()
        result = parse_datetime("not a date")
        after = datetime.now()
        assert before <= result <= after

    def test_parse_unknown_type_returns_now(self) -> None:
        """Test that unknown types return current datetime."""
        before = datetime.now()
        result = parse_datetime(12345)
        after = datetime.now()
        assert before <= result <= after

    def test_field_name_parameter(self) -> None:
        """Test that field_name parameter doesn't affect result."""
        dt = datetime(2024, 1, 15, 10, 30, 0)
        result = parse_datetime(dt, field_name="test_field")
        assert result == dt
