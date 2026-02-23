"""
PostgreSQL Data Management API endpoints.

Provides CRUD operations for work sessions, clients, projects,
and a read/delete view of memory relations.
"""

import csv
import io
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ...db.models import (
    RelationCreator,
    RelationType,
    SessionCategory,
    SessionStatus,
)
from ...db.repositories import (
    ClientRepository,
    MemoryRelationRepository,
    ProjectRepository,
    WorkSessionRepository,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def get_database(request: Request):
    """Get database or raise 503 if unavailable."""
    database = getattr(request.app.state, "database", None)
    if not database:
        raise HTTPException(
            status_code=503,
            detail="PostgreSQL not available. Set MEMORIA_DATABASE_URL.",
        )
    return database


def parse_dt(value: str) -> datetime:
    """Parse ISO date or datetime string into a timezone-aware datetime.

    asyncpg requires Python datetime objects for timestamptz columns —
    it rejects raw strings even with SQL casts.
    """
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic Models
# ─────────────────────────────────────────────────────────────────────────────


class SessionResponse(BaseModel):
    id: str
    description: str
    category: str
    client_id: Optional[str] = None
    client_name: Optional[str] = None
    project_id: Optional[str] = None
    project_name: Optional[str] = None
    issue_number: Optional[int] = None
    pr_number: Optional[int] = None
    branch: Optional[str] = None
    start_time: str
    end_time: Optional[str] = None
    duration_minutes: Optional[int] = None
    total_pause_minutes: int = 0
    pauses: list[dict] = Field(default_factory=list)
    status: str
    notes: list[str] = Field(default_factory=list)
    created_at: str
    updated_at: str


class SessionListResponse(BaseModel):
    items: list[SessionResponse]
    total: int
    page: int
    pages: int


class SessionSummaryResponse(BaseModel):
    total_minutes: int
    session_count: int
    avg_minutes: int
    client_count: int


class SessionCreateRequest(BaseModel):
    description: str
    category: str = "coding"
    client_id: Optional[str] = None
    project_id: Optional[str] = None
    start_time: str
    end_time: str
    issue_number: Optional[int] = None
    pr_number: Optional[int] = None
    branch: Optional[str] = None
    notes: list[str] = Field(default_factory=list)


class SessionUpdateRequest(BaseModel):
    description: Optional[str] = None
    category: Optional[str] = None
    client_id: Optional[str] = None
    project_id: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    issue_number: Optional[int] = None
    pr_number: Optional[int] = None
    branch: Optional[str] = None
    notes: Optional[list[str]] = None


class ClientResponse(BaseModel):
    id: str
    name: str
    metadata: dict = Field(default_factory=dict)
    project_count: int = 0
    session_count: int = 0
    total_minutes: int = 0
    last_activity: Optional[str] = None
    created_at: str
    updated_at: str


class ClientCreateRequest(BaseModel):
    name: str
    metadata: dict = Field(default_factory=dict)


class ClientUpdateRequest(BaseModel):
    name: Optional[str] = None
    metadata: Optional[dict] = None


class ProjectResponse(BaseModel):
    id: str
    name: str
    client_id: Optional[str] = None
    client_name: Optional[str] = None
    repo: Optional[str] = None
    metadata: dict = Field(default_factory=dict)
    session_count: int = 0
    total_minutes: int = 0
    last_activity: Optional[str] = None
    created_at: str
    updated_at: str


class ProjectCreateRequest(BaseModel):
    name: str
    client_id: Optional[str] = None
    repo: Optional[str] = None
    metadata: dict = Field(default_factory=dict)


class ProjectUpdateRequest(BaseModel):
    name: Optional[str] = None
    client_id: Optional[str] = None
    repo: Optional[str] = None
    metadata: Optional[dict] = None


class MemoryPreviewResponse(BaseModel):
    id: str
    content_preview: str
    memory_type: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    importance: float = 0.5


class EnrichedRelationItem(BaseModel):
    id: str
    source_id: str
    target_id: str
    relation_type: str
    weight: float
    created_by: str
    metadata: dict = Field(default_factory=dict)
    created_at: str
    source: Optional[MemoryPreviewResponse] = None
    target: Optional[MemoryPreviewResponse] = None


class RelationListResponse(BaseModel):
    items: list[EnrichedRelationItem]
    total: int
    page: int
    pages: int


# ─────────────────────────────────────────────────────────────────────────────
# Sessions
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/sessions")
async def list_sessions(
    request: Request,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    client_id: Optional[str] = None,
    project_id: Optional[str] = None,
    status: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: str = "start_time",
    sort_dir: str = "desc",
) -> SessionListResponse:
    """List work sessions with filters, pagination, and joined client/project names."""
    db = get_database(request)

    # Build dynamic WHERE clause
    conditions = []
    params: list[Any] = []
    idx = 1

    if date_from:
        conditions.append(f"ws.start_time >= ${idx}::timestamptz")
        params.append(parse_dt(date_from))
        idx += 1

    if date_to:
        conditions.append(f"ws.start_time <= ${idx}::timestamptz")
        params.append(parse_dt(date_to))
        idx += 1

    if client_id:
        conditions.append(f"ws.client_id = ${idx}::uuid")
        params.append(client_id)
        idx += 1

    if project_id:
        conditions.append(f"ws.project_id = ${idx}::uuid")
        params.append(project_id)
        idx += 1

    if status:
        conditions.append(f"ws.status = ${idx}::session_status")
        params.append(status)
        idx += 1

    if category:
        conditions.append(f"ws.category = ${idx}::session_category")
        params.append(category)
        idx += 1

    if search:
        conditions.append(f"ws.description ILIKE ${idx}")
        params.append(f"%{search}%")
        idx += 1

    where_clause = " AND ".join(conditions) if conditions else "TRUE"

    # Validate sort column
    allowed_sorts = {
        "start_time": "ws.start_time",
        "duration_minutes": "ws.duration_minutes",
        "category": "ws.category",
        "status": "ws.status",
        "client_name": "c.name",
        "project_name": "p.name",
    }
    sort_col = allowed_sorts.get(sort_by, "ws.start_time")
    sort_direction = "ASC" if sort_dir.lower() == "asc" else "DESC"

    # Count total
    total = await db.fetchval(
        f"""
        SELECT COUNT(*) FROM work_sessions ws
        LEFT JOIN clients c ON ws.client_id = c.id
        LEFT JOIN projects p ON ws.project_id = p.id
        WHERE {where_clause}
        """,
        *params,
    )

    # Fetch page
    offset = (page - 1) * page_size
    params.extend([page_size, offset])

    rows = await db.fetch(
        f"""
        SELECT
            ws.id, ws.description, ws.category, ws.status,
            ws.start_time, ws.end_time, ws.duration_minutes,
            ws.total_pause_minutes, ws.pauses, ws.notes,
            ws.issue_number, ws.pr_number, ws.branch,
            ws.client_id, ws.project_id,
            ws.created_at, ws.updated_at,
            c.name as client_name,
            p.name as project_name
        FROM work_sessions ws
        LEFT JOIN clients c ON ws.client_id = c.id
        LEFT JOIN projects p ON ws.project_id = p.id
        WHERE {where_clause}
        ORDER BY {sort_col} {sort_direction} NULLS LAST
        LIMIT ${idx} OFFSET ${idx + 1}
        """,
        *params,
    )

    items = []
    for row in rows:
        r = dict(row)
        pauses_raw = r.get("pauses") or []
        if isinstance(pauses_raw, str):
            pauses_raw = json.loads(pauses_raw)

        items.append(
            SessionResponse(
                id=str(r["id"]),
                description=r["description"],
                category=r["category"],
                client_id=str(r["client_id"]) if r["client_id"] else None,
                client_name=r.get("client_name"),
                project_id=str(r["project_id"]) if r["project_id"] else None,
                project_name=r.get("project_name"),
                issue_number=r["issue_number"],
                pr_number=r["pr_number"],
                branch=r["branch"],
                start_time=r["start_time"].isoformat() if r["start_time"] else "",
                end_time=r["end_time"].isoformat() if r["end_time"] else None,
                duration_minutes=r["duration_minutes"],
                total_pause_minutes=r["total_pause_minutes"] or 0,
                pauses=pauses_raw,
                status=r["status"],
                notes=r["notes"] or [],
                created_at=r["created_at"].isoformat(),
                updated_at=r["updated_at"].isoformat(),
            )
        )

    pages = max(1, -(-total // page_size))  # ceil division

    return SessionListResponse(items=items, total=total, page=page, pages=pages)


@router.get("/sessions/summary")
async def sessions_summary(
    request: Request,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    client_id: Optional[str] = None,
) -> SessionSummaryResponse:
    """Aggregated stats for summary cards."""
    db = get_database(request)

    conditions = ["status = 'completed'"]
    params: list[Any] = []
    idx = 1

    if date_from:
        conditions.append(f"start_time >= ${idx}::timestamptz")
        params.append(parse_dt(date_from))
        idx += 1

    if date_to:
        conditions.append(f"start_time <= ${idx}::timestamptz")
        params.append(parse_dt(date_to))
        idx += 1

    if client_id:
        conditions.append(f"client_id = ${idx}::uuid")
        params.append(client_id)
        idx += 1

    where_clause = " AND ".join(conditions)

    row = await db.fetchrow(
        f"""
        SELECT
            COALESCE(SUM(duration_minutes), 0)::int as total_minutes,
            COUNT(*)::int as session_count,
            COALESCE(AVG(duration_minutes), 0)::int as avg_minutes,
            COUNT(DISTINCT client_id)::int as client_count
        FROM work_sessions
        WHERE {where_clause}
        """,
        *params,
    )

    return SessionSummaryResponse(**dict(row))


@router.get("/sessions/{session_id}")
async def get_session(request: Request, session_id: str) -> SessionResponse:
    """Get a single session with client/project names."""
    db = get_database(request)

    row = await db.fetchrow(
        """
        SELECT
            ws.*, c.name as client_name, p.name as project_name
        FROM work_sessions ws
        LEFT JOIN clients c ON ws.client_id = c.id
        LEFT JOIN projects p ON ws.project_id = p.id
        WHERE ws.id = $1::uuid
        """,
        session_id,
    )

    if not row:
        raise HTTPException(status_code=404, detail="Session not found")

    r = dict(row)
    pauses_raw = r.get("pauses") or []
    if isinstance(pauses_raw, str):
        pauses_raw = json.loads(pauses_raw)

    return SessionResponse(
        id=str(r["id"]),
        description=r["description"],
        category=r["category"],
        client_id=str(r["client_id"]) if r["client_id"] else None,
        client_name=r.get("client_name"),
        project_id=str(r["project_id"]) if r["project_id"] else None,
        project_name=r.get("project_name"),
        issue_number=r["issue_number"],
        pr_number=r["pr_number"],
        branch=r["branch"],
        start_time=r["start_time"].isoformat() if r["start_time"] else "",
        end_time=r["end_time"].isoformat() if r["end_time"] else None,
        duration_minutes=r["duration_minutes"],
        total_pause_minutes=r["total_pause_minutes"] or 0,
        pauses=pauses_raw,
        status=r["status"],
        notes=r["notes"] or [],
        created_at=r["created_at"].isoformat(),
        updated_at=r["updated_at"].isoformat(),
    )


@router.post("/sessions")
async def create_session(request: Request, body: SessionCreateRequest) -> SessionResponse:
    """Create a manual work session (already completed)."""
    db = get_database(request)

    start = datetime.fromisoformat(body.start_time)
    end = datetime.fromisoformat(body.end_time)

    row = await db.fetchrow(
        """
        INSERT INTO work_sessions (
            description, category, client_id, project_id,
            issue_number, pr_number, branch,
            start_time, end_time, status, notes
        )
        VALUES ($1, $2::session_category, $3::uuid, $4::uuid, $5, $6, $7, $8, $9, 'completed', $10)
        RETURNING *
        """,
        body.description,
        body.category,
        body.client_id,
        body.project_id,
        body.issue_number,
        body.pr_number,
        body.branch,
        start,
        end,
        body.notes or [],
    )

    r = dict(row)
    return SessionResponse(
        id=str(r["id"]),
        description=r["description"],
        category=r["category"],
        client_id=str(r["client_id"]) if r["client_id"] else None,
        project_id=str(r["project_id"]) if r["project_id"] else None,
        start_time=r["start_time"].isoformat(),
        end_time=r["end_time"].isoformat() if r["end_time"] else None,
        duration_minutes=r["duration_minutes"],
        total_pause_minutes=r["total_pause_minutes"] or 0,
        pauses=[],
        status=r["status"],
        notes=r["notes"] or [],
        issue_number=r["issue_number"],
        pr_number=r["pr_number"],
        branch=r["branch"],
        created_at=r["created_at"].isoformat(),
        updated_at=r["updated_at"].isoformat(),
    )


@router.put("/sessions/{session_id}")
async def update_session(
    request: Request, session_id: str, body: SessionUpdateRequest
) -> SessionResponse:
    """Update a work session."""
    db = get_database(request)

    # Build dynamic SET clause
    sets = []
    params: list[Any] = [session_id]
    idx = 2

    if body.description is not None:
        sets.append(f"description = ${idx}")
        params.append(body.description)
        idx += 1

    if body.category is not None:
        sets.append(f"category = ${idx}::session_category")
        params.append(body.category)
        idx += 1

    if body.client_id is not None:
        sets.append(f"client_id = ${idx}::uuid")
        params.append(body.client_id if body.client_id else None)
        idx += 1

    if body.project_id is not None:
        sets.append(f"project_id = ${idx}::uuid")
        params.append(body.project_id if body.project_id else None)
        idx += 1

    if body.start_time is not None:
        sets.append(f"start_time = ${idx}::timestamptz")
        params.append(parse_dt(body.start_time))
        idx += 1

    if body.end_time is not None:
        sets.append(f"end_time = ${idx}::timestamptz")
        params.append(parse_dt(body.end_time))
        idx += 1

    if body.issue_number is not None:
        sets.append(f"issue_number = ${idx}")
        params.append(body.issue_number)
        idx += 1

    if body.pr_number is not None:
        sets.append(f"pr_number = ${idx}")
        params.append(body.pr_number)
        idx += 1

    if body.branch is not None:
        sets.append(f"branch = ${idx}")
        params.append(body.branch)
        idx += 1

    if body.notes is not None:
        sets.append(f"notes = ${idx}")
        params.append(body.notes)
        idx += 1

    if not sets:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_clause = ", ".join(sets)

    row = await db.fetchrow(
        f"""
        UPDATE work_sessions
        SET {set_clause}
        WHERE id = $1::uuid
        RETURNING *
        """,
        *params,
    )

    if not row:
        raise HTTPException(status_code=404, detail="Session not found")

    # Re-fetch with joins for names
    return await get_session(request, session_id)


@router.delete("/sessions/{session_id}")
async def delete_session(request: Request, session_id: str) -> dict:
    """Delete a work session."""
    db = get_database(request)
    result = await db.execute(
        "DELETE FROM work_sessions WHERE id = $1::uuid", session_id
    )
    if "DELETE 0" in result:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "deleted"}


@router.get("/sessions/export")
async def export_sessions_csv(
    request: Request,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    client_id: Optional[str] = None,
) -> StreamingResponse:
    """Export filtered sessions as CSV."""
    db = get_database(request)

    conditions = []
    params: list[Any] = []
    idx = 1

    if date_from:
        conditions.append(f"ws.start_time >= ${idx}::timestamptz")
        params.append(parse_dt(date_from))
        idx += 1

    if date_to:
        conditions.append(f"ws.start_time <= ${idx}::timestamptz")
        params.append(parse_dt(date_to))
        idx += 1

    if client_id:
        conditions.append(f"ws.client_id = ${idx}::uuid")
        params.append(client_id)
        idx += 1

    where_clause = " AND ".join(conditions) if conditions else "TRUE"

    rows = await db.fetch(
        f"""
        SELECT
            ws.start_time, ws.end_time, ws.description, ws.category,
            ws.duration_minutes, ws.total_pause_minutes, ws.status,
            c.name as client_name, p.name as project_name,
            ws.issue_number, ws.pr_number, ws.branch, ws.notes
        FROM work_sessions ws
        LEFT JOIN clients c ON ws.client_id = c.id
        LEFT JOIN projects p ON ws.project_id = p.id
        WHERE {where_clause}
        ORDER BY ws.start_time DESC
        """,
        *params,
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Date", "Start", "End", "Description", "Category",
        "Duration (min)", "Pause (min)", "Status",
        "Client", "Project", "Issue", "PR", "Branch", "Notes",
    ])

    for row in rows:
        r = dict(row)

        # CSV injection protection
        def safe(val: Any) -> str:
            s = str(val) if val is not None else ""
            if s and s[0] in ("=", "+", "-", "@"):
                s = "'" + s
            return s

        start = r["start_time"]
        writer.writerow([
            safe(start.date() if start else ""),
            safe(start.strftime("%H:%M") if start else ""),
            safe(r["end_time"].strftime("%H:%M") if r["end_time"] else ""),
            safe(r["description"]),
            safe(r["category"]),
            r["duration_minutes"] or "",
            r["total_pause_minutes"] or 0,
            safe(r["status"]),
            safe(r["client_name"] or ""),
            safe(r["project_name"] or ""),
            r["issue_number"] or "",
            r["pr_number"] or "",
            safe(r["branch"] or ""),
            safe("; ".join(r["notes"]) if r["notes"] else ""),
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=sessions.csv"},
    )


# ─────────────────────────────────────────────────────────────────────────────
# Clients
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/clients")
async def list_clients(request: Request) -> list[ClientResponse]:
    """List clients with aggregated stats."""
    db = get_database(request)

    rows = await db.fetch(
        """
        SELECT
            c.id, c.name, c.metadata, c.created_at, c.updated_at,
            COUNT(DISTINCT p.id)::int as project_count,
            COUNT(ws.id)::int as session_count,
            COALESCE(SUM(CASE WHEN ws.status = 'completed' THEN ws.duration_minutes ELSE 0 END), 0)::int as total_minutes,
            MAX(ws.start_time) as last_activity
        FROM clients c
        LEFT JOIN projects p ON p.client_id = c.id
        LEFT JOIN work_sessions ws ON ws.client_id = c.id
        GROUP BY c.id
        ORDER BY last_activity DESC NULLS LAST
        """
    )

    return [
        ClientResponse(
            id=str(r["id"]),
            name=r["name"],
            metadata=json.loads(r["metadata"]) if isinstance(r["metadata"], str) else (r["metadata"] or {}),
            project_count=r["project_count"],
            session_count=r["session_count"],
            total_minutes=r["total_minutes"],
            last_activity=r["last_activity"].isoformat() if r["last_activity"] else None,
            created_at=r["created_at"].isoformat(),
            updated_at=r["updated_at"].isoformat(),
        )
        for r in rows
    ]


@router.post("/clients")
async def create_client(request: Request, body: ClientCreateRequest) -> ClientResponse:
    """Create a new client."""
    db = get_database(request)
    repo = ClientRepository(db)
    client = await repo.create(name=body.name, metadata=body.metadata)
    return ClientResponse(
        id=str(client.id),
        name=client.name,
        metadata=client.metadata,
        created_at=client.created_at.isoformat(),
        updated_at=client.updated_at.isoformat(),
    )


@router.put("/clients/{client_id}")
async def update_client(
    request: Request, client_id: str, body: ClientUpdateRequest
) -> ClientResponse:
    """Update client name/metadata."""
    db = get_database(request)
    repo = ClientRepository(db)
    try:
        client = await repo.update(
            UUID(client_id),
            name=body.name,
            metadata=body.metadata,
        )
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

    return ClientResponse(
        id=str(client.id),
        name=client.name,
        metadata=client.metadata,
        created_at=client.created_at.isoformat(),
        updated_at=client.updated_at.isoformat(),
    )


@router.delete("/clients/{client_id}")
async def delete_client(request: Request, client_id: str) -> dict:
    """Delete client. Fails if has sessions."""
    db = get_database(request)

    session_count = await db.fetchval(
        "SELECT COUNT(*) FROM work_sessions WHERE client_id = $1::uuid",
        client_id,
    )
    if session_count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Client has {session_count} sessions. Reassign or delete them first.",
        )

    repo = ClientRepository(db)
    deleted = await repo.delete(UUID(client_id))
    if not deleted:
        raise HTTPException(status_code=404, detail="Client not found")
    return {"status": "deleted"}


# ─────────────────────────────────────────────────────────────────────────────
# Projects
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/projects")
async def list_projects(
    request: Request,
    client_id: Optional[str] = None,
) -> list[ProjectResponse]:
    """List projects with stats, optionally filtered by client."""
    db = get_database(request)

    conditions = []
    params: list[Any] = []
    idx = 1

    if client_id:
        conditions.append(f"p.client_id = ${idx}::uuid")
        params.append(client_id)
        idx += 1

    where_clause = " AND ".join(conditions) if conditions else "TRUE"

    rows = await db.fetch(
        f"""
        SELECT
            p.id, p.name, p.client_id, p.repo, p.metadata,
            p.created_at, p.updated_at,
            c.name as client_name,
            COUNT(ws.id)::int as session_count,
            COALESCE(SUM(CASE WHEN ws.status = 'completed' THEN ws.duration_minutes ELSE 0 END), 0)::int as total_minutes,
            MAX(ws.start_time) as last_activity
        FROM projects p
        LEFT JOIN clients c ON p.client_id = c.id
        LEFT JOIN work_sessions ws ON ws.project_id = p.id
        WHERE {where_clause}
        GROUP BY p.id, c.name
        ORDER BY last_activity DESC NULLS LAST
        """,
        *params,
    )

    return [
        ProjectResponse(
            id=str(r["id"]),
            name=r["name"],
            client_id=str(r["client_id"]) if r["client_id"] else None,
            client_name=r.get("client_name"),
            repo=r["repo"],
            metadata=json.loads(r["metadata"]) if isinstance(r["metadata"], str) else (r["metadata"] or {}),
            session_count=r["session_count"],
            total_minutes=r["total_minutes"],
            last_activity=r["last_activity"].isoformat() if r["last_activity"] else None,
            created_at=r["created_at"].isoformat(),
            updated_at=r["updated_at"].isoformat(),
        )
        for r in rows
    ]


@router.post("/projects")
async def create_project(request: Request, body: ProjectCreateRequest) -> ProjectResponse:
    """Create a new project."""
    db = get_database(request)
    repo = ProjectRepository(db)
    project = await repo.create(
        name=body.name,
        client_id=UUID(body.client_id) if body.client_id else None,
        repo=body.repo,
        metadata=body.metadata,
    )
    return ProjectResponse(
        id=str(project.id),
        name=project.name,
        client_id=str(project.client_id) if project.client_id else None,
        repo=project.repo,
        metadata=project.metadata,
        created_at=project.created_at.isoformat(),
        updated_at=project.updated_at.isoformat(),
    )


@router.put("/projects/{project_id}")
async def update_project(
    request: Request, project_id: str, body: ProjectUpdateRequest
) -> ProjectResponse:
    """Update a project."""
    db = get_database(request)
    repo = ProjectRepository(db)
    try:
        project = await repo.update(
            UUID(project_id),
            name=body.name,
            client_id=UUID(body.client_id) if body.client_id else None,
            repo=body.repo,
            metadata=body.metadata,
        )
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

    # Cascade client_id to sessions of this project that have no client assigned
    if body.client_id and project.client_id:
        updated = await db.execute(
            """
            UPDATE work_sessions
            SET client_id = $1::uuid
            WHERE project_id = $2::uuid AND client_id IS NULL
            """,
            str(project.client_id),
            project_id,
        )
        count = int(updated.split()[-1]) if updated else 0
        if count > 0:
            logger.info(
                "Cascaded client_id %s to %d sessions of project %s",
                project.client_id, count, project_id,
            )

    return ProjectResponse(
        id=str(project.id),
        name=project.name,
        client_id=str(project.client_id) if project.client_id else None,
        repo=project.repo,
        metadata=project.metadata,
        created_at=project.created_at.isoformat(),
        updated_at=project.updated_at.isoformat(),
    )


@router.delete("/projects/{project_id}")
async def delete_project(request: Request, project_id: str) -> dict:
    """Delete project. Fails if has sessions."""
    db = get_database(request)

    session_count = await db.fetchval(
        "SELECT COUNT(*) FROM work_sessions WHERE project_id = $1::uuid",
        project_id,
    )
    if session_count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Project has {session_count} sessions. Reassign or delete them first.",
        )

    repo = ProjectRepository(db)
    deleted = await repo.delete(UUID(project_id))
    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"status": "deleted"}


# ─────────────────────────────────────────────────────────────────────────────
# Memory preview helper
# ─────────────────────────────────────────────────────────────────────────────


async def _batch_get_memory_previews(
    request: Request,
    memory_ids: list[str],
    preview_length: int = 120,
) -> dict[str, MemoryPreviewResponse]:
    """Batch-fetch memory previews from Qdrant across all collections.

    Handles chunked memories by falling back to chunk_0 IDs when direct
    lookups fail (chunked memories use uuid5-derived point IDs).
    """
    from ...core.memory_types import MemoryType
    from ...core.memory_manager import _chunk_id

    qdrant_store = getattr(request.app.state, "qdrant_store", None)
    if not qdrant_store or not memory_ids:
        return {}

    previews: dict[str, MemoryPreviewResponse] = {}
    remaining = set(memory_ids)

    def _process_results(results, mem_type_value):
        for sr in results:
            payload = sr.payload
            parent_id = payload.get("parent_id", sr.id)
            if parent_id in previews and sr.id in previews:
                continue
            content = payload.get("full_content") or payload.get("content", "")
            preview = content[:preview_length]
            if len(content) > preview_length:
                preview += "..."
            item = MemoryPreviewResponse(
                id=parent_id,
                content_preview=preview,
                memory_type=mem_type_value,
                tags=payload.get("tags", []),
                importance=payload.get("importance", 0.5),
            )
            # Index under both parent_id and point id (chunk_id)
            # because relations may reference either
            previews[parent_id] = item
            if sr.id != parent_id:
                previews[sr.id] = item
            remaining.discard(parent_id)
            remaining.discard(sr.id)

    for memory_type in MemoryType:
        if not remaining:
            break

        # First pass: try direct IDs
        try:
            results = await qdrant_store.get(
                collection=memory_type.value,
                ids=list(remaining),
                with_vectors=False,
            )
            _process_results(results, memory_type.value)
        except Exception:
            pass

        if not remaining:
            break

        # Second pass: try chunk_0 IDs for memories not found directly
        chunk_map = {_chunk_id(mid, 0): mid for mid in remaining}
        try:
            results = await qdrant_store.get(
                collection=memory_type.value,
                ids=list(chunk_map.keys()),
                with_vectors=False,
            )
            _process_results(results, memory_type.value)
        except Exception:
            pass

    return previews


# ─────────────────────────────────────────────────────────────────────────────
# Relations (read + delete only)
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/relations")
async def list_relations(
    request: Request,
    relation_type: Optional[str] = None,
    created_by: Optional[str] = None,
    memory_id: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> RelationListResponse:
    """List memory relations as table."""
    db = get_database(request)

    conditions = []
    params: list[Any] = []
    idx = 1

    if relation_type:
        conditions.append(f"mr.relation_type = ${idx}::relation_type")
        params.append(relation_type)
        idx += 1

    if created_by:
        conditions.append(f"mr.created_by = ${idx}::relation_creator")
        params.append(created_by)
        idx += 1

    if memory_id:
        conditions.append(f"(mr.source_id = ${idx}::uuid OR mr.target_id = ${idx}::uuid)")
        params.append(memory_id)
        idx += 1

    where_clause = " AND ".join(conditions) if conditions else "TRUE"

    total = await db.fetchval(
        f"SELECT COUNT(*) FROM memory_relations mr WHERE {where_clause}",
        *params,
    )

    offset = (page - 1) * page_size
    params.extend([page_size, offset])

    rows = await db.fetch(
        f"""
        SELECT
            mr.id, mr.source_id, mr.target_id, mr.relation_type,
            mr.weight, mr.created_by, mr.metadata, mr.created_at
        FROM memory_relations mr
        WHERE {where_clause}
        ORDER BY mr.created_at DESC
        LIMIT ${idx} OFFSET ${idx + 1}
        """,
        *params,
    )

    # Collect unique memory IDs for enrichment
    memory_ids = set()
    for r in rows:
        memory_ids.add(str(r["source_id"]))
        memory_ids.add(str(r["target_id"]))

    previews = await _batch_get_memory_previews(request, list(memory_ids))

    items = [
        EnrichedRelationItem(
            id=str(r["id"]),
            source_id=str(r["source_id"]),
            target_id=str(r["target_id"]),
            relation_type=r["relation_type"],
            weight=r["weight"],
            created_by=r["created_by"],
            metadata=json.loads(r["metadata"]) if isinstance(r["metadata"], str) else (r["metadata"] or {}),
            created_at=r["created_at"].isoformat(),
            source=previews.get(str(r["source_id"])),
            target=previews.get(str(r["target_id"])),
        )
        for r in rows
    ]

    pages = max(1, -(-total // page_size))

    return RelationListResponse(items=items, total=total, page=page, pages=pages)


@router.delete("/relations/orphaned")
async def delete_orphaned_relations(request: Request) -> dict:
    """Delete all relations where source or target memory no longer exists in Qdrant."""
    from ...core.memory_types import MemoryType
    from ...core.memory_manager import _chunk_id

    db = get_database(request)
    qdrant_store = getattr(request.app.state, "qdrant_store", None)
    if not qdrant_store:
        raise HTTPException(status_code=503, detail="Qdrant not available")

    # Fetch all relations
    rows = await db.fetch(
        "SELECT id, source_id, target_id FROM memory_relations"
    )
    if not rows:
        return {"status": "ok", "deleted": 0}

    # Collect all unique memory IDs
    all_ids = set()
    for r in rows:
        all_ids.add(str(r["source_id"]))
        all_ids.add(str(r["target_id"]))

    # Batch-check which IDs exist in Qdrant (direct + chunk_0 fallback)
    existing_ids: set[str] = set()
    for memory_type in MemoryType:
        not_found = all_ids - existing_ids
        if not not_found:
            break

        # Pass 1: try direct IDs
        try:
            results = await qdrant_store.get(
                collection=memory_type.value,
                ids=list(not_found),
                with_vectors=False,
            )
            for sr in results:
                parent_id = sr.payload.get("parent_id", sr.id)
                existing_ids.add(parent_id)
                existing_ids.add(sr.id)
        except Exception:
            pass

        # Pass 2: try chunk_0 IDs for still-missing memories
        still_missing = all_ids - existing_ids
        if not still_missing:
            continue
        chunk_map = {_chunk_id(mid, 0): mid for mid in still_missing}
        try:
            results = await qdrant_store.get(
                collection=memory_type.value,
                ids=list(chunk_map.keys()),
                with_vectors=False,
            )
            for sr in results:
                parent_id = sr.payload.get("parent_id", sr.id)
                existing_ids.add(parent_id)
                existing_ids.add(sr.id)
        except Exception:
            pass

    # Find orphaned relation IDs (source OR target missing)
    orphaned_ids = []
    for r in rows:
        src = str(r["source_id"])
        tgt = str(r["target_id"])
        if src not in existing_ids or tgt not in existing_ids:
            orphaned_ids.append(r["id"])

    if not orphaned_ids:
        return {"status": "ok", "deleted": 0}

    # Delete in batches
    result = await db.execute(
        "DELETE FROM memory_relations WHERE id = ANY($1::uuid[])",
        orphaned_ids,
    )
    count = int(result.split()[-1]) if result else 0
    logger.info("Deleted %d orphaned relations out of %d total", count, len(rows))

    return {"status": "ok", "deleted": count}


@router.delete("/relations/{relation_id}")
async def delete_relation(request: Request, relation_id: str) -> dict:
    """Delete a memory relation."""
    db = get_database(request)
    repo = MemoryRelationRepository(db)
    deleted = await repo.delete(UUID(relation_id))
    if not deleted:
        raise HTTPException(status_code=404, detail="Relation not found")
    return {"status": "deleted"}
