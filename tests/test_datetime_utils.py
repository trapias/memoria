"""Tests for datetime utility functions."""

from datetime import UTC, datetime, timedelta

import pytest
from mcp_memoria.utils.datetime_utils import parse_datetime, parse_temporal_query


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


class TestParseTemporalQuery:
    """Tests for parse_temporal_query function."""

    def test_no_temporal_reference(self):
        query, date_from, date_to = parse_temporal_query("memory about Python")
        assert query == "memory about Python"
        assert date_from is None
        assert date_to is None

    def test_yesterday_english(self):
        query, date_from, date_to = parse_temporal_query("what did I learn yesterday")
        assert "yesterday" not in query
        now = datetime.now(UTC)
        expected = now - timedelta(days=1)
        assert abs((date_from - expected).total_seconds()) < 2

    def test_ieri_italian(self):
        query, date_from, date_to = parse_temporal_query("cosa ho imparato ieri")
        assert "ieri" not in query
        now = datetime.now(UTC)
        expected = now - timedelta(days=1)
        assert abs((date_from - expected).total_seconds()) < 2

    def test_today_english(self):
        query, date_from, date_to = parse_temporal_query("meetings today")
        assert "today" not in query
        assert date_from is not None
        # date_from should be start of today
        assert date_from.hour == 0
        assert date_from.minute == 0

    def test_oggi_italian(self):
        query, date_from, date_to = parse_temporal_query("riunioni oggi")
        assert "oggi" not in query
        assert date_from is not None

    def test_last_week(self):
        query, date_from, date_to = parse_temporal_query("bugs fixed last week")
        assert "last week" not in query
        now = datetime.now(UTC)
        expected = now - timedelta(days=14)
        assert abs((date_from - expected).total_seconds()) < 2

    def test_settimana_scorsa(self):
        query, date_from, date_to = parse_temporal_query("bug risolti settimana scorsa")
        assert "settimana scorsa" not in query
        assert date_from is not None

    def test_last_n_days(self):
        query, date_from, date_to = parse_temporal_query("changes in last 5 days")
        assert "last 5 days" not in query
        now = datetime.now(UTC)
        expected = now - timedelta(days=5)
        assert abs((date_from - expected).total_seconds()) < 2

    def test_ultimi_n_giorni(self):
        query, date_from, date_to = parse_temporal_query("modifiche ultimi 3 giorni")
        assert "ultimi 3 giorni" not in query
        now = datetime.now(UTC)
        expected = now - timedelta(days=3)
        assert abs((date_from - expected).total_seconds()) < 2

    def test_last_n_weeks(self):
        query, date_from, date_to = parse_temporal_query("decisions last 2 weeks")
        assert date_from is not None
        now = datetime.now(UTC)
        expected = now - timedelta(weeks=2)
        assert abs((date_from - expected).total_seconds()) < 2

    def test_last_month(self):
        query, date_from, date_to = parse_temporal_query("progress last month")
        assert date_from is not None

    def test_cleaned_query_preserves_meaning(self):
        query, _, _ = parse_temporal_query("Python tips yesterday about decorators")
        assert "Python" in query
        assert "decorators" in query
        assert "yesterday" not in query

    def test_date_to_is_now(self):
        """date_to should be approximately now."""
        _, date_from, date_to = parse_temporal_query("stuff yesterday")
        assert date_to is not None
        now = datetime.now(UTC)
        assert abs((date_to - now).total_seconds()) < 2
