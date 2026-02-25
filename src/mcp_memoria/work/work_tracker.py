"""Work tracking business logic.

Provides high-level operations for time tracking MCP tools.
Supports multiple parallel work sessions with hybrid disambiguation.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from mcp_memoria.config.settings import Settings, get_settings
from mcp_memoria.db import (
    ClientRepository,
    Database,
    ProjectRepository,
    WorkSessionRepository,
)
from mcp_memoria.db.models import (
    SessionCategory,
    SessionStatus,
    WorkSession,
)

logger = logging.getLogger(__name__)


class WorkTracker:
    """High-level work tracking operations.

    Supports parallel work sessions with hybrid disambiguation:
    - If only 1 session is active, all tools work without session_id (transparent).
    - If >1 sessions are active, tools that mutate a session require session_id
      or return a disambiguation error listing active sessions.
    """

    def __init__(self, db: Database, settings: Settings | None = None):
        self._db = db
        self._sessions = WorkSessionRepository(db)
        self._clients = ClientRepository(db)
        self._projects = ProjectRepository(db)
        _settings = settings or get_settings()
        self._max_parallel = _settings.work_max_parallel_sessions
        self._warning_hours = _settings.work_session_warning_hours

    # ── Public methods ──────────────────────────────────────────────

    async def start(
        self,
        description: str,
        category: str = "coding",
        client: str | None = None,
        project: str | None = None,
        issue_number: int | None = None,
        pr_number: int | None = None,
        branch: str | None = None,
    ) -> dict[str, Any]:
        """Start a new work session.

        Allows parallel sessions up to the configured maximum.
        Returns warnings about long-running or duplicate-project sessions.
        """
        # Check parallel session limit
        active_count = await self._sessions.count_active()
        if self._max_parallel > 0 and active_count >= self._max_parallel:
            all_active = await self._sessions.get_all_active()
            return {
                "error": (
                    f"Maximum parallel sessions reached ({self._max_parallel}). "
                    f"Stop or complete a session before starting a new one."
                ),
                "active_sessions": self._format_session_list(all_active),
            }

        # Resolve or create client
        client_id = None
        if client:
            client_obj = await self._clients.get_by_name(client)
            if not client_obj:
                client_obj = await self._clients.create(name=client)
                logger.info(f"Created new client: {client}")
            client_id = client_obj.id

        # Resolve or create project
        project_id = None
        if project:
            project_obj = await self._projects.get_by_name(project)
            if not project_obj:
                project_obj = await self._projects.create(
                    name=project,
                    client_id=client_id,
                )
                logger.info(f"Created new project: {project}")
            project_id = project_obj.id

        # Create session
        session_category = SessionCategory(category) if category else SessionCategory.CODING
        session = await self._sessions.create(
            description=description,
            category=session_category,
            client_id=client_id,
            project_id=project_id,
            issue_number=issue_number,
            pr_number=pr_number,
            branch=branch,
        )

        # Compute warnings for all active sessions (including newly created)
        all_active = await self._sessions.get_all_active()
        warnings = self._compute_warnings(all_active)

        result: dict[str, Any] = {
            "session_id": str(session.id),
            "description": session.description,
            "category": session.category.value,
            "started_at": session.start_time.isoformat(),
            "client": client,
            "project": project,
            "issue": issue_number,
            "pr": pr_number,
            "branch": branch,
            "parallel_sessions": len(all_active),
        }
        if warnings:
            result["warnings"] = warnings
        return result

    async def stop(
        self,
        session_id: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """Stop the active (or specified) work session.

        Uses hybrid disambiguation: if only 1 session exists, session_id is optional.
        If multiple sessions exist and session_id is not provided, returns a
        disambiguation error listing available sessions.
        """
        session_or_error = await self._resolve_session(
            session_id,
            statuses=[SessionStatus.ACTIVE, SessionStatus.PAUSED],
        )
        if isinstance(session_or_error, dict):
            return session_or_error

        session = session_or_error

        # Complete the session
        notes_list = [notes] if notes else None
        completed = await self._sessions.complete(session.id, notes=notes_list)
        duration = self._calculate_duration(completed)

        return {
            "session_id": str(completed.id),
            "description": completed.description,
            "category": completed.category.value,
            "started_at": completed.start_time.isoformat(),
            "ended_at": completed.end_time.isoformat() if completed.end_time else None,
            "duration_minutes": duration,
            "duration_formatted": self._format_duration(duration),
            "total_pause_minutes": completed.total_pause_minutes,
            "notes": completed.notes,
        }

    async def status(self) -> dict[str, Any]:
        """Get status of all active and paused sessions.

        Returns a unified response with a `sessions` array and legacy
        top-level fields when exactly 1 session is active (backwards compat).
        """
        all_active = await self._sessions.get_all_active()
        warnings = self._compute_warnings(all_active)

        if not all_active:
            result: dict[str, Any] = {"active": False, "paused": False, "sessions": []}
            if warnings:
                result["warnings"] = warnings
            return result

        # Enrich each session with client/project names
        sessions_out = []
        for session in all_active:
            client_name = None
            project_name = None
            if session.client_id:
                try:
                    client_obj = await self._clients.get(session.client_id)
                    client_name = client_obj.name
                except Exception:
                    pass
            if session.project_id:
                try:
                    project_obj = await self._projects.get(session.project_id)
                    project_name = project_obj.name
                except Exception:
                    pass

            sessions_out.append({
                "session_id": str(session.id),
                "description": session.description,
                "category": session.category.value,
                "status": session.status.value,
                "started_at": session.start_time.isoformat(),
                "elapsed_minutes": self._calculate_elapsed(session),
                "elapsed_formatted": self._format_duration(self._calculate_elapsed(session)),
                "client": client_name,
                "project": project_name,
                "issue": session.issue_number,
                "pr": session.pr_number,
                "branch": session.branch,
                "notes": session.notes,
            })

        active_sessions = [s for s in all_active if s.status == SessionStatus.ACTIVE]
        paused_sessions = [s for s in all_active if s.status == SessionStatus.PAUSED]

        result = {
            "active": len(active_sessions) > 0,
            "paused": len(paused_sessions) > 0 and len(active_sessions) == 0,
            "sessions": sessions_out,
        }

        # Single-session backwards compat: populate top-level fields
        if len(all_active) == 1:
            s = sessions_out[0]
            result.update({
                "session_id": s["session_id"],
                "description": s["description"],
                "category": s["category"],
                "started_at": s["started_at"],
                "elapsed_minutes": s["elapsed_minutes"],
                "elapsed_formatted": s["elapsed_formatted"],
                "client": s["client"],
                "project": s["project"],
                "issue": s["issue"],
                "pr": s["pr"],
                "branch": s["branch"],
                "notes": s["notes"],
            })

        if warnings:
            result["warnings"] = warnings

        return result

    async def pause(
        self,
        session_id: str | None = None,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """Pause an active session.

        Uses hybrid disambiguation when multiple active sessions exist.
        """
        session_or_error = await self._resolve_session(
            session_id,
            statuses=[SessionStatus.ACTIVE],
        )
        if isinstance(session_or_error, dict):
            return session_or_error

        session = session_or_error
        paused = await self._sessions.pause(session.id, reason=reason)

        return {
            "session_id": str(paused.id),
            "description": paused.description,
            "status": "paused",
            "paused_at": datetime.now(UTC).isoformat(),
            "reason": reason,
            "elapsed_minutes": self._calculate_elapsed(paused),
        }

    async def resume(self, session_id: str | None = None) -> dict[str, Any]:
        """Resume a paused session.

        Uses hybrid disambiguation when multiple paused sessions exist.
        """
        session_or_error = await self._resolve_session(
            session_id,
            statuses=[SessionStatus.PAUSED],
        )
        if isinstance(session_or_error, dict):
            return session_or_error

        session = session_or_error
        resumed = await self._sessions.resume(session.id)

        return {
            "session_id": str(resumed.id),
            "description": resumed.description,
            "status": "active",
            "resumed_at": datetime.now(UTC).isoformat(),
            "total_pause_minutes": resumed.total_pause_minutes,
        }

    async def add_note(self, note: str, session_id: str | None = None) -> dict[str, Any]:
        """Add a note to the active or specified session.

        Uses hybrid disambiguation when multiple sessions exist.
        """
        session_or_error = await self._resolve_session(
            session_id,
            statuses=[SessionStatus.ACTIVE, SessionStatus.PAUSED],
        )
        if isinstance(session_or_error, dict):
            return session_or_error

        session = session_or_error
        updated = await self._sessions.add_note(session.id, note)

        return {
            "session_id": str(updated.id),
            "note_added": note,
            "total_notes": len(updated.notes),
        }

    async def report(
        self,
        period: str = "month",
        start_date: str | None = None,
        end_date: str | None = None,
        group_by: str | None = None,
        client: str | None = None,
        project: str | None = None,
        category: str | None = None,
    ) -> dict[str, Any]:
        """Generate a work report.

        Args:
            period: Time period (today, week, month, year, all)
            start_date: Custom start date (ISO format)
            end_date: Custom end date (ISO format)
            group_by: Group results by (client, project, category)
            client: Filter by client name
            project: Filter by project name
            category: Filter by category

        Returns:
            Report data
        """
        # Calculate date range
        now = datetime.now(UTC)
        if start_date:
            start = datetime.fromisoformat(start_date)
        else:
            if period == "today":
                start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            elif period == "week":
                start = now - timedelta(days=7)
                start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            elif period == "month":
                start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            elif period == "year":
                start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            else:  # all
                start = None

        end = datetime.fromisoformat(end_date) if end_date else now

        # Resolve client/project IDs
        client_id = None
        project_id = None
        if client:
            client_obj = await self._clients.get_by_name(client)
            if client_obj:
                client_id = client_obj.id
        if project:
            project_obj = await self._projects.get_by_name(project)
            if project_obj:
                project_id = project_obj.id

        session_category = SessionCategory(category) if category else None

        # Get sessions
        sessions = await self._sessions.list(
            client_id=client_id,
            project_id=project_id,
            status=SessionStatus.COMPLETED,
            category=session_category,
            start_after=start,
            start_before=end,
            limit=1000,
        )

        # Calculate totals
        total_minutes = sum(self._calculate_duration(s) for s in sessions)
        total_hours = round(total_minutes / 60, 2)

        # Build breakdown
        breakdown = []
        if group_by:
            groups: dict[str, list[WorkSession]] = {}
            for s in sessions:
                if group_by == "client" and s.client_id:
                    key = str(s.client_id)
                elif group_by == "project" and s.project_id:
                    key = str(s.project_id)
                elif group_by == "category":
                    key = s.category.value
                else:
                    key = "other"

                if key not in groups:
                    groups[key] = []
                groups[key].append(s)

            # Resolve names and calculate totals
            for key, group_sessions in groups.items():
                group_minutes = sum(self._calculate_duration(s) for s in group_sessions)
                group_name = key

                if group_by == "client":
                    try:
                        c = await self._clients.get(UUID(key))
                        group_name = c.name
                    except Exception:
                        group_name = "Unknown"
                elif group_by == "project":
                    try:
                        p = await self._projects.get(UUID(key))
                        group_name = p.name
                    except Exception:
                        group_name = "Unknown"

                breakdown.append({
                    "group": group_name,
                    "hours": round(group_minutes / 60, 2),
                    "sessions": len(group_sessions),
                    "percentage": round((group_minutes / total_minutes * 100) if total_minutes > 0 else 0, 1),
                })

            breakdown.sort(key=lambda x: x["hours"], reverse=True)

        # Recent sessions (all, limited in server output)
        recent = []
        for s in sessions:
            client_name = None
            project_name = None
            if s.client_id:
                try:
                    c = await self._clients.get(s.client_id)
                    client_name = c.name
                except Exception:
                    pass
            if s.project_id:
                try:
                    p = await self._projects.get(s.project_id)
                    project_name = p.name
                except Exception:
                    pass

            recent.append({
                "date": s.start_time.date().isoformat(),
                "description": s.description,
                "duration_minutes": self._calculate_duration(s),
                "category": s.category.value,
                "client": client_name,
                "project": project_name,
            })

        return {
            "period": period,
            "start_date": start.isoformat() if start else None,
            "end_date": end.isoformat(),
            "total_hours": total_hours,
            "total_minutes": total_minutes,
            "total_sessions": len(sessions),
            "breakdown": breakdown,
            "recent_sessions": recent,
        }

    # ── Private helpers ─────────────────────────────────────────────

    async def _resolve_session(
        self,
        session_id: str | None,
        statuses: list[SessionStatus],
    ) -> WorkSession | dict[str, Any]:
        """Hybrid disambiguation logic.

        If session_id is provided: fetch that specific session and validate status.
        If session_id is None:
            - 0 matching sessions → error dict
            - 1 matching session → return it (transparent single-session behavior)
            - >1 matching sessions → disambiguation error listing candidates

        Returns either a WorkSession (proceed) or a dict with "error" key (abort).
        """
        if session_id:
            try:
                session = await self._sessions.get(UUID(session_id))
            except Exception:
                return {"error": f"Session {session_id} not found"}
            if session.status not in statuses:
                status_names = "/".join(s.value for s in statuses)
                return {
                    "error": (
                        f"Session {session_id} is not {status_names} "
                        f"(current status: {session.status.value})"
                    ),
                }
            return session

        # No session_id: auto-resolve
        all_active = await self._sessions.get_all_active()
        candidates = [s for s in all_active if s.status in statuses]

        if not candidates:
            status_names = "/".join(s.value for s in statuses)
            return {"error": f"No {status_names} session found"}

        if len(candidates) == 1:
            return candidates[0]

        # Disambiguation required — show only matching candidates
        return {
            "error": "Multiple sessions found. Specify session_id.",
            "requires_session_id": True,
            "active_sessions": self._format_session_list(candidates),
        }

    def _format_session_list(self, sessions: list[WorkSession]) -> list[dict[str, Any]]:
        """Format a list of sessions for disambiguation payloads."""
        return [
            {
                "session_id": str(s.id),
                "description": s.description,
                "status": s.status.value,
                "started_at": s.start_time.isoformat(),
                "elapsed_minutes": self._calculate_elapsed(s),
            }
            for s in sessions
        ]

    def _compute_warnings(self, sessions: list[WorkSession]) -> list[str]:
        """Compute advisory warnings for active/paused sessions.

        Checks for:
        - Sessions open longer than the configured threshold
        - Multiple sessions on the same project
        - Approaching the parallel session limit
        """
        warnings: list[str] = []
        now = datetime.now(UTC)
        warning_threshold = timedelta(hours=self._warning_hours)

        for s in sessions:
            elapsed = now - s.start_time
            if elapsed > warning_threshold:
                hours = elapsed.total_seconds() / 3600
                warnings.append(
                    f"Session '{s.description[:40]}' ({str(s.id)[:8]}...) "
                    f"has been open for {hours:.1f}h — possible forgotten session"
                )

        # Same-project overlap
        project_sessions: dict[UUID, list[WorkSession]] = {}
        for s in sessions:
            if s.project_id is not None:
                project_sessions.setdefault(s.project_id, []).append(s)

        for _pid, proj_sessions in project_sessions.items():
            if len(proj_sessions) > 1:
                descriptions = ", ".join(f"'{s.description[:30]}'" for s in proj_sessions)
                warnings.append(
                    f"Multiple sessions on the same project: {descriptions}"
                )

        # Approaching max limit (only meaningful when limit >= 2)
        if (
            self._max_parallel > 1
            and len(sessions) == self._max_parallel - 1
        ):
            warnings.append(
                f"Approaching parallel session limit ({len(sessions)}/{self._max_parallel})"
            )

        return warnings

    def _calculate_elapsed(self, session: WorkSession) -> int:
        """Calculate elapsed minutes for an active/paused session."""
        if session.end_time:
            total = int((session.end_time - session.start_time).total_seconds() / 60)
        else:
            total = int((datetime.now(UTC) - session.start_time).total_seconds() / 60)
        return total - session.total_pause_minutes

    def _calculate_duration(self, session: WorkSession) -> int:
        """Calculate work duration for a completed session."""
        if session.duration_minutes is not None:
            return session.duration_minutes
        if session.end_time:
            total = int((session.end_time - session.start_time).total_seconds() / 60)
            return total - session.total_pause_minutes
        return self._calculate_elapsed(session)

    def _format_duration(self, minutes: int) -> str:
        """Format duration as human-readable string."""
        hours = minutes // 60
        mins = minutes % 60
        if hours > 0:
            return f"{hours}h {mins}m"
        return f"{mins}m"
