"""A NULL notes/pauses column must not make a work session unreadable."""

from datetime import datetime
from unittest.mock import MagicMock
from uuid import uuid4

from mcp_memoria.db.repositories import WorkSessionRepository


def _row(**overrides):
    row = {
        "id": uuid4(),
        "description": "Issue #1",
        "category": "coding",
        "status": "active",
        "start_time": datetime.now(),
        "end_time": None,
        "pauses": [],
        "total_pause_minutes": 0,
        "notes": [],
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
    }
    row.update(overrides)
    return row


def test_null_notes_and_pauses_read_as_empty_lists():
    repo = WorkSessionRepository(MagicMock())
    session = repo._row_to_session(_row(notes=None, pauses=None))
    assert session.notes == []
    assert session.pauses == []


def test_existing_notes_are_kept():
    repo = WorkSessionRepository(MagicMock())
    assert repo._row_to_session(_row(notes=["a"])).notes == ["a"]
