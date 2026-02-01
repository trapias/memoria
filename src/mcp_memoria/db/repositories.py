"""Repository classes for database operations.

Provides high-level data access methods built on top of the Database class.
Each repository handles CRUD operations for a specific domain entity.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from mcp_memoria.db.database import Database
from mcp_memoria.db.exceptions import QueryError, RecordNotFoundError
from mcp_memoria.db.models import (
    Client,
    DailyTotal,
    GraphNeighbor,
    GraphPath,
    MemoryRelation,
    MonthlySummary,
    PauseEntry,
    Project,
    RelationCreator,
    RelationType,
    SessionCategory,
    SessionStatus,
    UserSetting,
    WorkSession,
)

logger = logging.getLogger(__name__)


class ClientRepository:
    """Repository for Client operations."""

    def __init__(self, db: Database):
        self._db = db

    async def create(self, name: str, metadata: dict[str, Any] | None = None) -> Client:
        """Create a new client."""
        row = await self._db.fetchrow(
            """
            INSERT INTO clients (name, metadata)
            VALUES ($1, $2)
            RETURNING *
            """,
            name,
            json.dumps(metadata or {}),
        )
        return Client(**dict(row))

    async def get(self, client_id: UUID) -> Client:
        """Get client by ID."""
        row = await self._db.fetchrow(
            "SELECT * FROM clients WHERE id = $1",
            client_id,
        )
        if not row:
            raise RecordNotFoundError("clients", str(client_id))
        return Client(**dict(row))

    async def get_by_name(self, name: str) -> Client | None:
        """Get client by name."""
        row = await self._db.fetchrow(
            "SELECT * FROM clients WHERE name = $1",
            name,
        )
        return Client(**dict(row)) if row else None

    async def list(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Client]:
        """List all clients."""
        rows = await self._db.fetch(
            """
            SELECT * FROM clients
            ORDER BY name
            LIMIT $1 OFFSET $2
            """,
            limit,
            offset,
        )
        return [Client(**dict(row)) for row in rows]

    async def update(
        self,
        client_id: UUID,
        name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Client:
        """Update a client."""
        # Verify client exists first
        await self.get(client_id)

        row = await self._db.fetchrow(
            """
            UPDATE clients
            SET name = COALESCE($2, name),
                metadata = COALESCE($3, metadata)
            WHERE id = $1
            RETURNING *
            """,
            client_id,
            name,
            json.dumps(metadata) if metadata is not None else None,
        )
        return Client(**dict(row))

    async def delete(self, client_id: UUID) -> bool:
        """Delete a client."""
        result = await self._db.execute(
            "DELETE FROM clients WHERE id = $1",
            client_id,
        )
        return "DELETE 1" in result


class ProjectRepository:
    """Repository for Project operations."""

    def __init__(self, db: Database):
        self._db = db

    async def create(
        self,
        name: str,
        client_id: UUID | None = None,
        repo: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Project:
        """Create a new project."""
        row = await self._db.fetchrow(
            """
            INSERT INTO projects (name, client_id, repo, metadata)
            VALUES ($1, $2, $3, $4)
            RETURNING *
            """,
            name,
            client_id,
            repo,
            json.dumps(metadata or {}),
        )
        return Project(**dict(row))

    async def get(self, project_id: UUID) -> Project:
        """Get project by ID."""
        row = await self._db.fetchrow(
            "SELECT * FROM projects WHERE id = $1",
            project_id,
        )
        if not row:
            raise RecordNotFoundError("projects", str(project_id))
        return Project(**dict(row))

    async def get_by_repo(self, repo: str) -> Project | None:
        """Get project by repository path."""
        row = await self._db.fetchrow(
            "SELECT * FROM projects WHERE repo = $1",
            repo,
        )
        return Project(**dict(row)) if row else None

    async def get_by_name(self, name: str) -> Project | None:
        """Get project by name."""
        row = await self._db.fetchrow(
            "SELECT * FROM projects WHERE name = $1",
            name,
        )
        return Project(**dict(row)) if row else None

    async def list_by_client(
        self,
        client_id: UUID,
        limit: int = 100,
    ) -> list[Project]:
        """List projects for a client."""
        rows = await self._db.fetch(
            """
            SELECT * FROM projects
            WHERE client_id = $1
            ORDER BY name
            LIMIT $2
            """,
            client_id,
            limit,
        )
        return [Project(**dict(row)) for row in rows]

    async def update(
        self,
        project_id: UUID,
        name: str | None = None,
        client_id: UUID | None = None,
        repo: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Project:
        """Update a project."""
        row = await self._db.fetchrow(
            """
            UPDATE projects
            SET name = COALESCE($2, name),
                client_id = COALESCE($3, client_id),
                repo = COALESCE($4, repo),
                metadata = COALESCE($5, metadata)
            WHERE id = $1
            RETURNING *
            """,
            project_id,
            name,
            client_id,
            repo,
            json.dumps(metadata) if metadata is not None else None,
        )
        if not row:
            raise RecordNotFoundError("projects", str(project_id))
        return Project(**dict(row))

    async def delete(self, project_id: UUID) -> bool:
        """Delete a project."""
        result = await self._db.execute(
            "DELETE FROM projects WHERE id = $1",
            project_id,
        )
        return "DELETE 1" in result


class WorkSessionRepository:
    """Repository for WorkSession operations."""

    def __init__(self, db: Database):
        self._db = db

    async def create(
        self,
        description: str,
        category: SessionCategory = SessionCategory.CODING,
        client_id: UUID | None = None,
        project_id: UUID | None = None,
        issue_number: int | None = None,
        pr_number: int | None = None,
        branch: str | None = None,
    ) -> WorkSession:
        """Create a new work session."""
        row = await self._db.fetchrow(
            """
            INSERT INTO work_sessions (
                description, category, client_id, project_id,
                issue_number, pr_number, branch, status
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, 'active')
            RETURNING *
            """,
            description,
            category.value,
            client_id,
            project_id,
            issue_number,
            pr_number,
            branch,
        )
        return self._row_to_session(row)

    async def get(self, session_id: UUID) -> WorkSession:
        """Get session by ID."""
        row = await self._db.fetchrow(
            "SELECT * FROM work_sessions WHERE id = $1",
            session_id,
        )
        if not row:
            raise RecordNotFoundError("work_sessions", str(session_id))
        return self._row_to_session(row)

    async def get_active(self) -> WorkSession | None:
        """Get the currently active session."""
        row = await self._db.fetchrow(
            "SELECT * FROM work_sessions WHERE status = 'active' LIMIT 1"
        )
        return self._row_to_session(row) if row else None

    async def list(
        self,
        client_id: UUID | None = None,
        project_id: UUID | None = None,
        status: SessionStatus | None = None,
        category: SessionCategory | None = None,
        start_after: datetime | None = None,
        start_before: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[WorkSession]:
        """List sessions with optional filters."""
        conditions = []
        params: list[Any] = []
        param_idx = 1

        if client_id:
            conditions.append(f"client_id = ${param_idx}")
            params.append(client_id)
            param_idx += 1

        if project_id:
            conditions.append(f"project_id = ${param_idx}")
            params.append(project_id)
            param_idx += 1

        if status:
            conditions.append(f"status = ${param_idx}")
            params.append(status.value)
            param_idx += 1

        if category:
            conditions.append(f"category = ${param_idx}")
            params.append(category.value)
            param_idx += 1

        if start_after:
            conditions.append(f"start_time >= ${param_idx}")
            params.append(start_after)
            param_idx += 1

        if start_before:
            conditions.append(f"start_time <= ${param_idx}")
            params.append(start_before)
            param_idx += 1

        where_clause = " AND ".join(conditions) if conditions else "TRUE"
        params.extend([limit, offset])

        rows = await self._db.fetch(
            f"""
            SELECT * FROM work_sessions
            WHERE {where_clause}
            ORDER BY start_time DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
            """,
            *params,
        )
        return [self._row_to_session(row) for row in rows]

    async def pause(self, session_id: UUID, reason: str | None = None) -> WorkSession:
        """Pause an active session."""
        session = await self.get(session_id)
        if session.status != SessionStatus.ACTIVE:
            raise QueryError(f"Session {session_id} is not active")

        # Add pause entry
        pauses = session.pauses + [PauseEntry(start=datetime.now(), reason=reason)]

        row = await self._db.fetchrow(
            """
            UPDATE work_sessions
            SET status = 'paused',
                pauses = $2
            WHERE id = $1
            RETURNING *
            """,
            session_id,
            json.dumps([p.model_dump(mode="json") for p in pauses]),
        )
        return self._row_to_session(row)

    async def resume(self, session_id: UUID) -> WorkSession:
        """Resume a paused session."""
        session = await self.get(session_id)
        if session.status != SessionStatus.PAUSED:
            raise QueryError(f"Session {session_id} is not paused")

        # Close the current pause
        pauses = session.pauses
        if pauses and pauses[-1].end is None:
            pauses[-1].end = datetime.now()

        # Calculate total pause minutes
        total_pause = sum(
            int((p.end - p.start).total_seconds() / 60)
            for p in pauses
            if p.end is not None
        )

        row = await self._db.fetchrow(
            """
            UPDATE work_sessions
            SET status = 'active',
                pauses = $2,
                total_pause_minutes = $3
            WHERE id = $1
            RETURNING *
            """,
            session_id,
            json.dumps([p.model_dump(mode="json") for p in pauses]),
            total_pause,
        )
        return self._row_to_session(row)

    async def complete(
        self,
        session_id: UUID,
        notes: list[str] | None = None,
    ) -> WorkSession:
        """Complete a session."""
        session = await self.get(session_id)

        # If paused, close the pause
        pauses = session.pauses
        if session.status == SessionStatus.PAUSED and pauses and pauses[-1].end is None:
            pauses[-1].end = datetime.now()

        # Calculate total pause minutes
        total_pause = sum(
            int((p.end - p.start).total_seconds() / 60)
            for p in pauses
            if p.end is not None
        )

        final_notes = (session.notes or []) + (notes or [])

        row = await self._db.fetchrow(
            """
            UPDATE work_sessions
            SET status = 'completed',
                end_time = NOW(),
                pauses = $2,
                total_pause_minutes = $3,
                notes = $4
            WHERE id = $1
            RETURNING *
            """,
            session_id,
            json.dumps([p.model_dump(mode="json") for p in pauses]),
            total_pause,
            final_notes,
        )
        return self._row_to_session(row)

    async def add_note(self, session_id: UUID, note: str) -> WorkSession:
        """Add a note to a session."""
        row = await self._db.fetchrow(
            """
            UPDATE work_sessions
            SET notes = array_append(notes, $2)
            WHERE id = $1
            RETURNING *
            """,
            session_id,
            note,
        )
        if not row:
            raise RecordNotFoundError("work_sessions", str(session_id))
        return self._row_to_session(row)

    async def link_memory(self, session_id: UUID, memory_id: UUID) -> WorkSession:
        """Link a Qdrant memory to this session."""
        row = await self._db.fetchrow(
            """
            UPDATE work_sessions
            SET memory_id = $2
            WHERE id = $1
            RETURNING *
            """,
            session_id,
            memory_id,
        )
        if not row:
            raise RecordNotFoundError("work_sessions", str(session_id))
        return self._row_to_session(row)

    def _row_to_session(self, row: Any) -> WorkSession:
        """Convert database row to WorkSession model."""
        data = dict(row)
        # Parse JSONB pauses
        if isinstance(data.get("pauses"), str):
            data["pauses"] = json.loads(data["pauses"])
        return WorkSession(**data)


class MemoryRelationRepository:
    """Repository for MemoryRelation operations and graph traversal."""

    def __init__(self, db: Database):
        self._db = db

    async def create(
        self,
        source_id: UUID,
        target_id: UUID,
        relation_type: RelationType,
        weight: float = 1.0,
        created_by: RelationCreator = RelationCreator.USER,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryRelation:
        """Create a new memory relation."""
        row = await self._db.fetchrow(
            """
            INSERT INTO memory_relations (
                source_id, target_id, relation_type, weight, created_by, metadata
            )
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING *
            """,
            source_id,
            target_id,
            relation_type.value,
            weight,
            created_by.value,
            json.dumps(metadata or {}),
        )
        return MemoryRelation(**dict(row))

    async def get(self, relation_id: UUID) -> MemoryRelation:
        """Get relation by ID."""
        row = await self._db.fetchrow(
            "SELECT * FROM memory_relations WHERE id = $1",
            relation_id,
        )
        if not row:
            raise RecordNotFoundError("memory_relations", str(relation_id))
        return MemoryRelation(**dict(row))

    async def get_for_memory(
        self,
        memory_id: UUID,
        relation_type: RelationType | None = None,
        direction: str = "both",  # "outgoing", "incoming", or "both"
    ) -> list[MemoryRelation]:
        """Get all relations for a memory."""
        conditions = []
        params: list[Any] = []
        param_idx = 1

        if direction in ("outgoing", "both"):
            conditions.append(f"source_id = ${param_idx}")
            params.append(memory_id)
            param_idx += 1

        if direction in ("incoming", "both"):
            if direction == "both":
                conditions[-1] = f"(source_id = ${param_idx - 1} OR target_id = ${param_idx})"
                params.append(memory_id)
                param_idx += 1
            else:
                conditions.append(f"target_id = ${param_idx}")
                params.append(memory_id)
                param_idx += 1

        if relation_type:
            conditions.append(f"relation_type = ${param_idx}")
            params.append(relation_type.value)

        where_clause = " AND ".join(conditions)

        rows = await self._db.fetch(
            f"""
            SELECT * FROM memory_relations
            WHERE {where_clause}
            ORDER BY created_at DESC
            """,
            *params,
        )
        return [MemoryRelation(**dict(row)) for row in rows]

    async def update_weight(
        self,
        relation_id: UUID,
        weight: float,
    ) -> MemoryRelation:
        """Update relation weight."""
        row = await self._db.fetchrow(
            """
            UPDATE memory_relations
            SET weight = $2
            WHERE id = $1
            RETURNING *
            """,
            relation_id,
            weight,
        )
        if not row:
            raise RecordNotFoundError("memory_relations", str(relation_id))
        return MemoryRelation(**dict(row))

    async def delete(self, relation_id: UUID) -> bool:
        """Delete a relation."""
        result = await self._db.execute(
            "DELETE FROM memory_relations WHERE id = $1",
            relation_id,
        )
        return "DELETE 1" in result

    async def delete_for_memory(self, memory_id: UUID) -> int:
        """Delete all relations involving a memory."""
        result = await self._db.execute(
            """
            DELETE FROM memory_relations
            WHERE source_id = $1 OR target_id = $1
            """,
            memory_id,
        )
        # Parse "DELETE N" to get count
        try:
            return int(result.split()[1])
        except (IndexError, ValueError):
            return 0

    async def get_neighbors(
        self,
        memory_id: UUID,
        depth: int = 1,
        relation_types: list[RelationType] | None = None,
    ) -> list[GraphNeighbor]:
        """Get neighboring memories up to N hops."""
        type_array = (
            [rt.value for rt in relation_types] if relation_types else None
        )

        rows = await self._db.fetch(
            "SELECT * FROM get_neighbors($1, $2, $3::relation_type[])",
            memory_id,
            depth,
            type_array,
        )

        return [
            GraphNeighbor(
                memory_id=row["memory_id"],
                depth=row["depth"],
                path=row["path"],
                relation=RelationType(row["relation"]),
            )
            for row in rows
        ]

    async def find_path(
        self,
        from_id: UUID,
        to_id: UUID,
        max_depth: int = 5,
    ) -> list[GraphPath]:
        """Find shortest path between two memories."""
        rows = await self._db.fetch(
            "SELECT * FROM find_path($1, $2, $3)",
            from_id,
            to_id,
            max_depth,
        )

        return [
            GraphPath(
                step=row["step"],
                memory_id=row["memory_id"],
                relation=RelationType(row["relation"]) if row["relation"] else None,
                direction=row["direction"],
            )
            for row in rows
        ]

    async def count_relations(
        self,
        memory_id: UUID,
    ) -> dict[str, dict[str, int]]:
        """Count relations by type for a memory."""
        rows = await self._db.fetch(
            "SELECT * FROM count_relations($1)",
            memory_id,
        )

        return {
            row["relation_type"]: {
                "outgoing": row["outgoing_count"],
                "incoming": row["incoming_count"],
            }
            for row in rows
        }


class UserSettingRepository:
    """Repository for UserSetting operations."""

    def __init__(self, db: Database):
        self._db = db

    async def get(self, key: str) -> Any:
        """Get a setting value."""
        row = await self._db.fetchrow(
            "SELECT value FROM user_settings WHERE key = $1",
            key,
        )
        if not row:
            return None
        return row["value"]

    async def set(self, key: str, value: Any) -> UserSetting:
        """Set a setting value."""
        row = await self._db.fetchrow(
            """
            INSERT INTO user_settings (key, value)
            VALUES ($1, $2)
            ON CONFLICT (key) DO UPDATE SET value = $2
            RETURNING *
            """,
            key,
            json.dumps(value),
        )
        return UserSetting(**dict(row))

    async def delete(self, key: str) -> bool:
        """Delete a setting."""
        result = await self._db.execute(
            "DELETE FROM user_settings WHERE key = $1",
            key,
        )
        return "DELETE 1" in result

    async def list(self) -> dict[str, Any]:
        """Get all settings as a dictionary."""
        rows = await self._db.fetch("SELECT key, value FROM user_settings")
        return {row["key"]: row["value"] for row in rows}


class ReportRepository:
    """Repository for report and statistics queries."""

    def __init__(self, db: Database):
        self._db = db

    async def get_monthly_summary(
        self,
        year: int | None = None,
        month: int | None = None,
        client_id: UUID | None = None,
    ) -> list[MonthlySummary]:
        """Get monthly work summary from materialized view."""
        conditions = []
        params: list[Any] = []
        param_idx = 1

        if year and month:
            conditions.append("month = date_trunc('month', make_date($1, $2, 1)::timestamp)")
            params.extend([year, month])
            param_idx += 2
        elif year:
            conditions.append(f"EXTRACT(YEAR FROM month) = ${param_idx}")
            params.append(year)
            param_idx += 1

        if client_id:
            conditions.append(f"client_id = ${param_idx}")
            params.append(client_id)

        where_clause = " AND ".join(conditions) if conditions else "TRUE"

        rows = await self._db.fetch(
            f"""
            SELECT * FROM monthly_work_summary
            WHERE {where_clause}
            ORDER BY month DESC, client_name, project_name
            """,
            *params,
        )

        return [MonthlySummary(**dict(row)) for row in rows]

    async def get_daily_totals(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        client_id: UUID | None = None,
    ) -> list[DailyTotal]:
        """Get daily work totals from materialized view."""
        conditions = []
        params: list[Any] = []
        param_idx = 1

        if start_date:
            conditions.append(f"date >= ${param_idx}")
            params.append(start_date.date())
            param_idx += 1

        if end_date:
            conditions.append(f"date <= ${param_idx}")
            params.append(end_date.date())
            param_idx += 1

        if client_id:
            conditions.append(f"client_id = ${param_idx}")
            params.append(client_id)

        where_clause = " AND ".join(conditions) if conditions else "TRUE"

        rows = await self._db.fetch(
            f"""
            SELECT * FROM daily_work_totals
            WHERE {where_clause}
            ORDER BY date DESC
            """,
            *params,
        )

        return [DailyTotal(**dict(row)) for row in rows]

    async def refresh_views(self) -> None:
        """Refresh all materialized views."""
        await self._db.execute("SELECT refresh_all_statistics()")
        logger.info("Materialized views refreshed")

    async def get_client_statistics(
        self,
        client_id: UUID | None = None,
    ) -> list[dict[str, Any]]:
        """Get client statistics from materialized view."""
        if client_id:
            rows = await self._db.fetch(
                "SELECT * FROM client_statistics WHERE client_id = $1",
                client_id,
            )
        else:
            rows = await self._db.fetch(
                "SELECT * FROM client_statistics ORDER BY total_minutes DESC"
            )

        return [dict(row) for row in rows]


class RejectedSuggestionRepository:
    """Repository for storing rejected relation suggestions."""

    def __init__(self, db: Database):
        self._db = db

    async def create(
        self,
        source_id: str,
        target_id: str,
        relation_type: str,
    ) -> dict[str, Any]:
        """Record a rejected suggestion."""
        row = await self._db.fetchrow(
            """
            INSERT INTO rejected_suggestions (source_id, target_id, relation_type)
            VALUES ($1::uuid, $2::uuid, $3)
            ON CONFLICT (source_id, target_id, relation_type) DO NOTHING
            RETURNING *
            """,
            source_id,
            target_id,
            relation_type,
        )
        return dict(row) if row else {"source_id": source_id, "target_id": target_id, "relation_type": relation_type}

    async def get_all(self) -> list[dict[str, Any]]:
        """Get all rejected suggestions."""
        rows = await self._db.fetch(
            "SELECT source_id, target_id, relation_type FROM rejected_suggestions"
        )
        return [dict(row) for row in rows]

    async def delete(
        self,
        source_id: str,
        target_id: str,
        relation_type: str,
    ) -> bool:
        """Remove a rejected suggestion (allow it to be suggested again)."""
        result = await self._db.execute(
            """
            DELETE FROM rejected_suggestions
            WHERE source_id = $1::uuid AND target_id = $2::uuid AND relation_type = $3
            """,
            source_id,
            target_id,
            relation_type,
        )
        return "DELETE 1" in result

    async def clear_all(self) -> int:
        """Clear all rejected suggestions."""
        result = await self._db.execute("DELETE FROM rejected_suggestions")
        try:
            return int(result.split()[1])
        except (IndexError, ValueError):
            return 0
