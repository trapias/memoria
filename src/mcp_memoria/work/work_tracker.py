"""Work tracking business logic.

Provides high-level operations for time tracking MCP tools.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from mcp_memoria.db import (
    Database,
    WorkSessionRepository,
    ClientRepository,
    ProjectRepository,
)
from mcp_memoria.db.models import (
    SessionCategory,
    SessionStatus,
    WorkSession,
    Client,
    Project,
)

logger = logging.getLogger(__name__)


class WorkTracker:
    """High-level work tracking operations."""

    def __init__(self, db: Database):
        """Initialize work tracker.

        Args:
            db: Database connection
        """
        self._db = db
        self._sessions = WorkSessionRepository(db)
        self._clients = ClientRepository(db)
        self._projects = ProjectRepository(db)

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

        Args:
            description: What you're working on
            category: Work category (coding, review, meeting, support, research, documentation, devops, other)
            client: Client name (will be created if doesn't exist)
            project: Project name (will be created if doesn't exist)
            issue_number: GitHub issue number
            pr_number: GitHub PR number
            branch: Git branch name

        Returns:
            Session info dict
        """
        # Check for active session
        active = await self._sessions.get_active()
        if active:
            return {
                "error": "A session is already active",
                "active_session": {
                    "id": str(active.id),
                    "description": active.description,
                    "started_at": active.start_time.isoformat(),
                    "elapsed_minutes": self._calculate_elapsed(active),
                }
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

        return {
            "session_id": str(session.id),
            "description": session.description,
            "category": session.category.value,
            "started_at": session.start_time.isoformat(),
            "client": client,
            "project": project,
            "issue": issue_number,
            "pr": pr_number,
            "branch": branch,
        }

    async def stop(
        self,
        session_id: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """Stop the active (or specified) work session.

        Args:
            session_id: Optional session ID (defaults to active session)
            notes: Optional notes to add

        Returns:
            Completed session info
        """
        if session_id:
            session = await self._sessions.get(UUID(session_id))
        else:
            session = await self._sessions.get_active()

        if not session:
            return {"error": "No active session found"}

        if session.status == SessionStatus.COMPLETED:
            return {"error": f"Session {session.id} is already completed"}

        # Complete the session
        notes_list = [notes] if notes else None
        completed = await self._sessions.complete(session.id, notes=notes_list)

        # Calculate actual work duration
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
        """Get current work session status.

        Returns:
            Active session info or inactive status
        """
        session = await self._sessions.get_active()

        if not session:
            # Also check for paused sessions
            paused_sessions = await self._sessions.list(
                status=SessionStatus.PAUSED,
                limit=1,
            )
            if paused_sessions:
                ps = paused_sessions[0]
                return {
                    "active": False,
                    "paused": True,
                    "session_id": str(ps.id),
                    "description": ps.description,
                    "started_at": ps.start_time.isoformat(),
                    "elapsed_minutes": self._calculate_elapsed(ps),
                }
            return {"active": False, "paused": False}

        # Get client/project names
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

        return {
            "active": True,
            "paused": False,
            "session_id": str(session.id),
            "description": session.description,
            "category": session.category.value,
            "started_at": session.start_time.isoformat(),
            "elapsed_minutes": self._calculate_elapsed(session),
            "elapsed_formatted": self._format_duration(self._calculate_elapsed(session)),
            "client": client_name,
            "project": project_name,
            "issue": session.issue_number,
            "pr": session.pr_number,
            "branch": session.branch,
            "notes": session.notes,
        }

    async def pause(
        self,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """Pause the active session.

        Args:
            reason: Optional reason for pausing

        Returns:
            Paused session info
        """
        session = await self._sessions.get_active()
        if not session:
            return {"error": "No active session to pause"}

        paused = await self._sessions.pause(session.id, reason=reason)

        return {
            "session_id": str(paused.id),
            "description": paused.description,
            "status": "paused",
            "paused_at": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
            "elapsed_minutes": self._calculate_elapsed(paused),
        }

    async def resume(self) -> dict[str, Any]:
        """Resume a paused session.

        Returns:
            Resumed session info
        """
        paused_sessions = await self._sessions.list(
            status=SessionStatus.PAUSED,
            limit=1,
        )

        if not paused_sessions:
            return {"error": "No paused session to resume"}

        session = paused_sessions[0]
        resumed = await self._sessions.resume(session.id)

        return {
            "session_id": str(resumed.id),
            "description": resumed.description,
            "status": "active",
            "resumed_at": datetime.now(timezone.utc).isoformat(),
            "total_pause_minutes": resumed.total_pause_minutes,
        }

    async def add_note(self, note: str, session_id: str | None = None) -> dict[str, Any]:
        """Add a note to the active or specified session.

        Args:
            note: Note text
            session_id: Optional session ID

        Returns:
            Updated session info
        """
        if session_id:
            session = await self._sessions.get(UUID(session_id))
        else:
            session = await self._sessions.get_active()

        if not session:
            return {"error": "No active session found"}

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
        now = datetime.now(timezone.utc)
        if start_date:
            start = datetime.fromisoformat(start_date)
        else:
            if period == "today":
                start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            elif period == "week":
                start = now - timedelta(days=now.weekday())
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

        # Recent sessions
        recent = []
        for s in sessions[:10]:
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

    def _calculate_elapsed(self, session: WorkSession) -> int:
        """Calculate elapsed minutes for an active/paused session."""
        if session.end_time:
            total = int((session.end_time - session.start_time).total_seconds() / 60)
        else:
            total = int((datetime.now(timezone.utc) - session.start_time).total_seconds() / 60)
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
