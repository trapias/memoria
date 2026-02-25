"""Tests for parallel work session support.

Tests the hybrid disambiguation logic, warnings system,
and parallel session limit enforcement in WorkTracker.
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from mcp_memoria.db.models import SessionCategory, SessionStatus, WorkSession
from mcp_memoria.work.work_tracker import WorkTracker


# ── Helpers ──────────────────────────────────────────────────────


def make_session(
    description: str = "Test task",
    status: SessionStatus = SessionStatus.ACTIVE,
    hours_ago: float = 1.0,
    project_id=None,
    client_id=None,
) -> WorkSession:
    """Create a WorkSession for testing."""
    return WorkSession(
        id=uuid4(),
        description=description,
        category=SessionCategory.CODING,
        status=status,
        start_time=datetime.now(timezone.utc) - timedelta(hours=hours_ago),
        project_id=project_id,
        client_id=client_id,
    )


def make_tracker(max_parallel: int = 3, warning_hours: float = 8.0) -> WorkTracker:
    """Create a WorkTracker with mocked dependencies."""
    db = MagicMock()
    settings = MagicMock()
    settings.work_max_parallel_sessions = max_parallel
    settings.work_session_warning_hours = warning_hours
    tracker = WorkTracker(db, settings=settings)
    # Replace repositories with async mocks
    tracker._sessions = AsyncMock()
    tracker._clients = AsyncMock()
    tracker._projects = AsyncMock()
    return tracker


# ── Disambiguation Tests ─────────────────────────────────────────


class TestResolveSession:
    """Tests for _resolve_session hybrid disambiguation logic."""

    @pytest.mark.asyncio
    async def test_no_sessions_returns_error(self):
        tracker = make_tracker()
        tracker._sessions.get_all_active.return_value = []
        result = await tracker._resolve_session(None, [SessionStatus.ACTIVE])
        assert isinstance(result, dict)
        assert "error" in result
        assert "active" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_single_session_returns_transparently(self):
        tracker = make_tracker()
        s = make_session()
        tracker._sessions.get_all_active.return_value = [s]
        result = await tracker._resolve_session(None, [SessionStatus.ACTIVE])
        assert isinstance(result, WorkSession)
        assert result.id == s.id

    @pytest.mark.asyncio
    async def test_multiple_sessions_returns_disambiguation(self):
        tracker = make_tracker()
        sessions = [make_session(f"Task {i}") for i in range(2)]
        tracker._sessions.get_all_active.return_value = sessions
        result = await tracker._resolve_session(None, [SessionStatus.ACTIVE])
        assert isinstance(result, dict)
        assert "error" in result
        assert result.get("requires_session_id") is True
        assert len(result["active_sessions"]) == 2

    @pytest.mark.asyncio
    async def test_explicit_session_id_bypasses_disambiguation(self):
        tracker = make_tracker()
        s = make_session()
        tracker._sessions.get.return_value = s
        result = await tracker._resolve_session(str(s.id), [SessionStatus.ACTIVE])
        assert isinstance(result, WorkSession)
        assert result.id == s.id

    @pytest.mark.asyncio
    async def test_explicit_session_id_wrong_status_returns_error(self):
        tracker = make_tracker()
        s = make_session(status=SessionStatus.PAUSED)
        tracker._sessions.get.return_value = s
        result = await tracker._resolve_session(str(s.id), [SessionStatus.ACTIVE])
        assert isinstance(result, dict)
        assert "error" in result
        assert "paused" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_explicit_session_id_not_found_returns_error(self):
        tracker = make_tracker()
        tracker._sessions.get.side_effect = Exception("not found")
        result = await tracker._resolve_session(str(uuid4()), [SessionStatus.ACTIVE])
        assert isinstance(result, dict)
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_filters_by_requested_status(self):
        """With 1 active + 1 paused, resolving for ACTIVE only returns the active one."""
        tracker = make_tracker()
        active = make_session("Active", status=SessionStatus.ACTIVE)
        paused = make_session("Paused", status=SessionStatus.PAUSED)
        tracker._sessions.get_all_active.return_value = [active, paused]
        result = await tracker._resolve_session(None, [SessionStatus.ACTIVE])
        assert isinstance(result, WorkSession)
        assert result.id == active.id

    @pytest.mark.asyncio
    async def test_filters_paused_only(self):
        """With 1 active + 1 paused, resolving for PAUSED only returns the paused one."""
        tracker = make_tracker()
        active = make_session("Active", status=SessionStatus.ACTIVE)
        paused = make_session("Paused", status=SessionStatus.PAUSED)
        tracker._sessions.get_all_active.return_value = [active, paused]
        result = await tracker._resolve_session(None, [SessionStatus.PAUSED])
        assert isinstance(result, WorkSession)
        assert result.id == paused.id

    @pytest.mark.asyncio
    async def test_disambiguation_lists_only_matching_candidates(self):
        """With 2 active + 1 paused, pause disambiguation should list only the 2 active ones."""
        tracker = make_tracker()
        active1 = make_session("Active 1", status=SessionStatus.ACTIVE)
        active2 = make_session("Active 2", status=SessionStatus.ACTIVE)
        paused = make_session("Paused", status=SessionStatus.PAUSED)
        tracker._sessions.get_all_active.return_value = [active1, active2, paused]
        result = await tracker._resolve_session(None, [SessionStatus.ACTIVE])
        assert isinstance(result, dict)
        assert result.get("requires_session_id") is True
        # Should list only the 2 active sessions, not the paused one
        listed_ids = {s["session_id"] for s in result["active_sessions"]}
        assert str(active1.id) in listed_ids
        assert str(active2.id) in listed_ids
        assert str(paused.id) not in listed_ids


# ── Start Tests ──────────────────────────────────────────────────


class TestStart:
    """Tests for start() with parallel session support."""

    @pytest.mark.asyncio
    async def test_start_first_session(self):
        tracker = make_tracker()
        new_session = make_session("New task")
        tracker._sessions.count_active.return_value = 0
        tracker._sessions.create.return_value = new_session
        tracker._sessions.get_all_active.return_value = [new_session]
        tracker._clients.get_by_name.return_value = None
        tracker._projects.get_by_name.return_value = None

        result = await tracker.start("New task")
        assert "error" not in result
        assert result["session_id"] == str(new_session.id)
        assert result["parallel_sessions"] == 1

    @pytest.mark.asyncio
    async def test_start_second_session_parallel(self):
        tracker = make_tracker(max_parallel=3)
        existing = make_session("Existing task")
        new_session = make_session("Second task")
        tracker._sessions.count_active.return_value = 1
        tracker._sessions.create.return_value = new_session
        tracker._sessions.get_all_active.return_value = [existing, new_session]
        tracker._clients.get_by_name.return_value = None
        tracker._projects.get_by_name.return_value = None

        result = await tracker.start("Second task")
        assert "error" not in result
        assert result["parallel_sessions"] == 2

    @pytest.mark.asyncio
    async def test_start_blocked_at_max_limit(self):
        tracker = make_tracker(max_parallel=2)
        existing = [make_session(f"Task {i}") for i in range(2)]
        tracker._sessions.count_active.return_value = 2
        tracker._sessions.get_all_active.return_value = existing

        result = await tracker.start("Blocked task")
        assert "error" in result
        assert "Maximum" in result["error"]
        assert len(result["active_sessions"]) == 2

    @pytest.mark.asyncio
    async def test_start_unlimited_when_max_zero(self):
        tracker = make_tracker(max_parallel=0)
        tracker._sessions.count_active.return_value = 100
        new_session = make_session("Task 101")
        tracker._sessions.create.return_value = new_session
        tracker._sessions.get_all_active.return_value = [new_session]
        tracker._clients.get_by_name.return_value = None
        tracker._projects.get_by_name.return_value = None

        result = await tracker.start("Task 101")
        assert "error" not in result

    @pytest.mark.asyncio
    async def test_start_includes_warnings(self):
        tracker = make_tracker(max_parallel=5, warning_hours=2.0)
        old_session = make_session("Old task", hours_ago=5.0)
        new_session = make_session("New task", hours_ago=0.0)
        tracker._sessions.count_active.return_value = 1
        tracker._sessions.create.return_value = new_session
        tracker._sessions.get_all_active.return_value = [old_session, new_session]
        tracker._clients.get_by_name.return_value = None
        tracker._projects.get_by_name.return_value = None

        result = await tracker.start("New task")
        assert "warnings" in result
        assert any("forgotten" in w for w in result["warnings"])


# ── Stop Tests ───────────────────────────────────────────────────


class TestStop:
    """Tests for stop() with hybrid disambiguation."""

    @pytest.mark.asyncio
    async def test_stop_single_session_no_id_needed(self):
        tracker = make_tracker()
        session = make_session()
        completed = make_session(status=SessionStatus.COMPLETED)
        completed.end_time = datetime.now(timezone.utc)
        completed.duration_minutes = 60

        tracker._sessions.get_all_active.return_value = [session]
        tracker._sessions.complete.return_value = completed

        result = await tracker.stop()
        assert "error" not in result
        assert result["session_id"] == str(completed.id)

    @pytest.mark.asyncio
    async def test_stop_multiple_sessions_requires_id(self):
        tracker = make_tracker()
        sessions = [make_session(f"Task {i}") for i in range(2)]
        tracker._sessions.get_all_active.return_value = sessions

        result = await tracker.stop()
        assert "error" in result
        assert result.get("requires_session_id") is True

    @pytest.mark.asyncio
    async def test_stop_with_explicit_id(self):
        tracker = make_tracker()
        session = make_session()
        completed = make_session(status=SessionStatus.COMPLETED)
        completed.end_time = datetime.now(timezone.utc)
        completed.duration_minutes = 30

        tracker._sessions.get.return_value = session
        tracker._sessions.complete.return_value = completed

        result = await tracker.stop(session_id=str(session.id))
        assert "error" not in result


# ── Pause/Resume Tests ───────────────────────────────────────────


class TestPauseResume:
    """Tests for pause() and resume() with disambiguation."""

    @pytest.mark.asyncio
    async def test_pause_single_session(self):
        tracker = make_tracker()
        session = make_session()
        paused = make_session(status=SessionStatus.PAUSED)
        tracker._sessions.get_all_active.return_value = [session]
        tracker._sessions.pause.return_value = paused

        result = await tracker.pause()
        assert "error" not in result
        assert result["status"] == "paused"

    @pytest.mark.asyncio
    async def test_pause_multiple_active_requires_id(self):
        tracker = make_tracker()
        sessions = [make_session(f"Task {i}") for i in range(2)]
        tracker._sessions.get_all_active.return_value = sessions

        result = await tracker.pause()
        assert "error" in result
        assert result.get("requires_session_id") is True

    @pytest.mark.asyncio
    async def test_pause_with_explicit_id(self):
        tracker = make_tracker()
        session = make_session()
        paused = make_session(status=SessionStatus.PAUSED)
        tracker._sessions.get.return_value = session
        tracker._sessions.pause.return_value = paused

        result = await tracker.pause(session_id=str(session.id))
        assert "error" not in result

    @pytest.mark.asyncio
    async def test_resume_single_paused(self):
        tracker = make_tracker()
        paused = make_session(status=SessionStatus.PAUSED)
        resumed = make_session(status=SessionStatus.ACTIVE)
        tracker._sessions.get_all_active.return_value = [paused]
        tracker._sessions.resume.return_value = resumed

        result = await tracker.resume()
        assert "error" not in result
        assert result["status"] == "active"

    @pytest.mark.asyncio
    async def test_resume_multiple_paused_requires_id(self):
        tracker = make_tracker()
        paused = [make_session(f"Task {i}", status=SessionStatus.PAUSED) for i in range(2)]
        tracker._sessions.get_all_active.return_value = paused

        result = await tracker.resume()
        assert "error" in result
        assert result.get("requires_session_id") is True

    @pytest.mark.asyncio
    async def test_resume_with_mixed_sessions_resolves_paused(self):
        """With 1 active + 1 paused, resume resolves to the paused one."""
        tracker = make_tracker()
        active = make_session("Active", status=SessionStatus.ACTIVE)
        paused = make_session("Paused", status=SessionStatus.PAUSED)
        resumed = make_session(status=SessionStatus.ACTIVE)
        tracker._sessions.get_all_active.return_value = [active, paused]
        tracker._sessions.resume.return_value = resumed

        result = await tracker.resume()
        assert "error" not in result
        tracker._sessions.resume.assert_called_once_with(paused.id)


# ── Status Tests ─────────────────────────────────────────────────


class TestStatus:
    """Tests for status() with multiple sessions."""

    @pytest.mark.asyncio
    async def test_status_no_sessions(self):
        tracker = make_tracker()
        tracker._sessions.get_all_active.return_value = []

        result = await tracker.status()
        assert result["active"] is False
        assert result["sessions"] == []

    @pytest.mark.asyncio
    async def test_status_single_session_has_legacy_fields(self):
        """Single session populates both sessions array and top-level fields."""
        tracker = make_tracker()
        session = make_session("Solo task")
        tracker._sessions.get_all_active.return_value = [session]

        result = await tracker.status()
        assert result["active"] is True
        assert "session_id" in result  # legacy top-level
        assert len(result["sessions"]) == 1
        assert result["sessions"][0]["session_id"] == str(session.id)

    @pytest.mark.asyncio
    async def test_status_multiple_sessions_no_ambiguous_top_level(self):
        """Multiple sessions should NOT have session_id at top level."""
        tracker = make_tracker()
        sessions = [make_session(f"Task {i}") for i in range(2)]
        tracker._sessions.get_all_active.return_value = sessions

        result = await tracker.status()
        assert result["active"] is True
        assert "session_id" not in result
        assert len(result["sessions"]) == 2

    @pytest.mark.asyncio
    async def test_status_includes_warnings(self):
        tracker = make_tracker(warning_hours=2.0)
        old = make_session("Old task", hours_ago=5.0)
        tracker._sessions.get_all_active.return_value = [old]

        result = await tracker.status()
        assert "warnings" in result
        assert len(result["warnings"]) >= 1

    @pytest.mark.asyncio
    async def test_status_mixed_active_and_paused(self):
        tracker = make_tracker()
        active = make_session("Active", status=SessionStatus.ACTIVE)
        paused = make_session("Paused", status=SessionStatus.PAUSED)
        tracker._sessions.get_all_active.return_value = [active, paused]

        result = await tracker.status()
        assert result["active"] is True
        assert result["paused"] is False  # has active sessions, so not "only paused"
        assert len(result["sessions"]) == 2
        statuses = {s["status"] for s in result["sessions"]}
        assert statuses == {"active", "paused"}


# ── Warning Tests ────────────────────────────────────────────────


class TestWarnings:
    """Tests for _compute_warnings."""

    def test_no_warnings_for_fresh_sessions(self):
        tracker = make_tracker(warning_hours=8.0)
        sessions = [make_session(hours_ago=1.0)]
        assert tracker._compute_warnings(sessions) == []

    def test_stale_session_warning(self):
        tracker = make_tracker(warning_hours=4.0)
        sessions = [make_session("Old task", hours_ago=5.0)]
        warnings = tracker._compute_warnings(sessions)
        assert len(warnings) == 1
        assert "forgotten" in warnings[0].lower()

    def test_same_project_overlap_warning(self):
        tracker = make_tracker()
        pid = uuid4()
        sessions = [
            make_session("Task A", project_id=pid),
            make_session("Task B", project_id=pid),
        ]
        warnings = tracker._compute_warnings(sessions)
        assert any("same project" in w.lower() for w in warnings)

    def test_no_project_overlap_for_different_projects(self):
        tracker = make_tracker()
        sessions = [
            make_session("Task A", project_id=uuid4()),
            make_session("Task B", project_id=uuid4()),
        ]
        warnings = tracker._compute_warnings(sessions)
        assert not any("same project" in w.lower() for w in warnings)

    def test_no_project_overlap_when_no_project(self):
        tracker = make_tracker()
        sessions = [
            make_session("Task A"),
            make_session("Task B"),
        ]
        warnings = tracker._compute_warnings(sessions)
        assert not any("same project" in w.lower() for w in warnings)

    def test_approaching_limit_warning(self):
        tracker = make_tracker(max_parallel=3)
        sessions = [make_session(f"Task {i}") for i in range(2)]  # 2 of 3
        warnings = tracker._compute_warnings(sessions)
        assert any("approaching" in w.lower() for w in warnings)

    def test_no_limit_warning_when_not_close(self):
        tracker = make_tracker(max_parallel=5)
        sessions = [make_session()]  # 1 of 5
        warnings = tracker._compute_warnings(sessions)
        assert not any("approaching" in w.lower() for w in warnings)

    def test_no_limit_warning_when_unlimited(self):
        tracker = make_tracker(max_parallel=0)
        sessions = [make_session(f"Task {i}") for i in range(10)]
        warnings = tracker._compute_warnings(sessions)
        assert not any("approaching" in w.lower() for w in warnings)

    def test_no_spurious_warning_when_max_parallel_is_one(self):
        """max_parallel=1 should not produce 'approaching limit (0/1)' on empty list."""
        tracker = make_tracker(max_parallel=1)
        warnings = tracker._compute_warnings([])
        assert not any("approaching" in w.lower() for w in warnings)
        # Also no warning with 1 session (already at limit, not approaching)
        warnings = tracker._compute_warnings([make_session()])
        assert not any("approaching" in w.lower() for w in warnings)

    def test_multiple_warnings_combined(self):
        tracker = make_tracker(max_parallel=3, warning_hours=2.0)
        pid = uuid4()
        sessions = [
            make_session("Old task A", hours_ago=5.0, project_id=pid),
            make_session("Old task B", hours_ago=3.0, project_id=pid),
        ]
        warnings = tracker._compute_warnings(sessions)
        # Should have: 2 stale warnings + 1 project overlap + 1 approaching limit
        assert len(warnings) >= 3


# ── AddNote Tests ────────────────────────────────────────────────


class TestAddNote:
    """Tests for add_note() with disambiguation."""

    @pytest.mark.asyncio
    async def test_add_note_single_session(self):
        tracker = make_tracker()
        session = make_session()
        updated = make_session()
        updated.notes = ["test note"]
        tracker._sessions.get_all_active.return_value = [session]
        tracker._sessions.add_note.return_value = updated

        result = await tracker.add_note("test note")
        assert "error" not in result
        assert result["note_added"] == "test note"

    @pytest.mark.asyncio
    async def test_add_note_multiple_sessions_requires_id(self):
        tracker = make_tracker()
        sessions = [make_session(f"Task {i}") for i in range(2)]
        tracker._sessions.get_all_active.return_value = sessions

        result = await tracker.add_note("test note")
        assert "error" in result
        assert result.get("requires_session_id") is True
