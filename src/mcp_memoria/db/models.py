"""Pydantic models for PostgreSQL database entities.

These models represent the relational data stored in PostgreSQL,
complementing the vector data stored in Qdrant.
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SessionCategory(str, Enum):
    """Work session categories for time tracking."""

    CODING = "coding"
    REVIEW = "review"
    MEETING = "meeting"
    SUPPORT = "support"
    RESEARCH = "research"
    DOCUMENTATION = "documentation"
    DEVOPS = "devops"
    OTHER = "other"


class SessionStatus(str, Enum):
    """Work session status values."""

    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class RelationType(str, Enum):
    """Types of relationships between memories in the knowledge graph."""

    CAUSES = "causes"  # A leads to B
    FIXES = "fixes"  # A resolves B
    SUPPORTS = "supports"  # A confirms B
    OPPOSES = "opposes"  # A contradicts B
    FOLLOWS = "follows"  # A comes after B
    SUPERSEDES = "supersedes"  # A replaces B
    DERIVES = "derives"  # A is derived from B
    PART_OF = "part_of"  # A is component of B
    RELATED = "related"  # Generic connection


class RelationCreator(str, Enum):
    """How a memory relation was created."""

    USER = "user"  # Manually created
    AUTO = "auto"  # AI suggested and accepted
    SYSTEM = "system"  # Created by consolidation/system


class Client(BaseModel):
    """Client entity for work tracking."""

    id: UUID = Field(default_factory=uuid4)
    name: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    model_config = ConfigDict(from_attributes=True)


class Project(BaseModel):
    """Project entity linked to a client."""

    id: UUID = Field(default_factory=uuid4)
    client_id: UUID | None = None
    name: str
    repo: str | None = None  # "owner/repo" for GitHub integration
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    model_config = ConfigDict(from_attributes=True)


class PauseEntry(BaseModel):
    """A pause period within a work session."""

    start: datetime
    end: datetime | None = None
    reason: str | None = None


class WorkSession(BaseModel):
    """Work session for time tracking."""

    id: UUID = Field(default_factory=uuid4)
    description: str
    category: SessionCategory = SessionCategory.CODING

    # Relations (nullable for flexibility)
    client_id: UUID | None = None
    project_id: UUID | None = None

    # GitHub context
    issue_number: int | None = None
    pr_number: int | None = None
    branch: str | None = None

    # Timing
    start_time: datetime = Field(default_factory=datetime.now)
    end_time: datetime | None = None
    duration_minutes: int | None = None  # Calculated, excludes pauses

    # Pauses
    pauses: list[PauseEntry] = Field(default_factory=list)
    total_pause_minutes: int = 0

    # Status
    status: SessionStatus = SessionStatus.ACTIVE

    # Notes as array
    notes: list[str] = Field(default_factory=list)

    # Link to episodic memory in Qdrant (optional)
    memory_id: UUID | None = None

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    model_config = ConfigDict(from_attributes=True)

    @field_validator("pauses", mode="before")
    @classmethod
    def parse_pauses(cls, v: Any) -> list[PauseEntry]:
        """Parse pauses from JSON or list of dicts."""
        if v is None:
            return []
        if isinstance(v, list):
            return [
                PauseEntry(**p) if isinstance(p, dict) else p
                for p in v
            ]
        return v


class MemoryRelation(BaseModel):
    """Relationship between two memories in the knowledge graph."""

    id: UUID = Field(default_factory=uuid4)
    source_id: UUID
    target_id: UUID
    relation_type: RelationType
    weight: float = Field(default=1.0, ge=0.0, le=1.0)
    created_by: RelationCreator = RelationCreator.USER
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)

    model_config = ConfigDict(from_attributes=True)

    @field_validator("source_id", "target_id", mode="before")
    @classmethod
    def validate_uuid(cls, v: Any) -> UUID:
        """Convert string UUIDs to UUID objects."""
        if isinstance(v, str):
            return UUID(v)
        return v


class UserSetting(BaseModel):
    """Key-value user setting."""

    key: str
    value: Any  # Stored as JSONB
    updated_at: datetime = Field(default_factory=datetime.now)

    model_config = ConfigDict(from_attributes=True)


class GraphNeighbor(BaseModel):
    """Result from graph traversal - a neighboring memory."""

    memory_id: UUID
    depth: int
    path: list[UUID]
    relation: RelationType


class GraphPath(BaseModel):
    """Result from path finding between two memories."""

    step: int
    memory_id: UUID
    relation: RelationType | None
    direction: str | None  # "in" or "out"


class MonthlySummary(BaseModel):
    """Monthly work summary from materialized view."""

    month: datetime
    client_id: UUID | None
    client_name: str | None
    project_id: UUID | None
    project_name: str | None
    category: SessionCategory
    session_count: int
    total_minutes: int
    avg_minutes: int
    days_worked: int


class DailyTotal(BaseModel):
    """Daily work totals from materialized view."""

    date: datetime
    client_id: UUID | None
    total_minutes: int
    session_count: int
