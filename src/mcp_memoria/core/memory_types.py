"""Memory type definitions and models."""

import logging
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from mcp_memoria.utils.datetime_utils import parse_datetime

logger = logging.getLogger(__name__)


class MemoryType(str, Enum):
    """Types of memory supported by the system."""

    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"


class MemoryItem(BaseModel):
    """Base memory item model."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    content: str
    memory_type: MemoryType
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    accessed_at: datetime = Field(default_factory=datetime.now)
    access_count: int = 0
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        """Convert to Qdrant payload format.

        Returns:
            Dictionary suitable for Qdrant storage
        """
        return {
            "content": self.content,
            "memory_type": self.memory_type.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "accessed_at": self.accessed_at.isoformat(),
            "access_count": self.access_count,
            "importance": self.importance,
            "tags": self.tags,
            **self.metadata,
        }

    @classmethod
    def from_payload(cls, id: str, payload: dict[str, Any]) -> "MemoryItem":
        """Create from Qdrant payload.

        Args:
            id: Memory ID
            payload: Qdrant payload dict

        Returns:
            MemoryItem instance
        """
        import logging
        logger = logging.getLogger(__name__)

        # Extract known fields
        known_fields = {
            "content",
            "full_content",
            "memory_type",
            "created_at",
            "updated_at",
            "accessed_at",
            "access_count",
            "importance",
            "tags",
            "is_chunk",
            "parent_id",
            "chunk_index",
            "chunk_count",
        }
        metadata = {k: v for k, v in payload.items() if k not in known_fields}

        # Use full_content if available (chunked memories), else content
        content = payload.get("full_content", payload.get("content", ""))

        try:
            return cls(
                id=id,
                content=content,
                memory_type=MemoryType(payload.get("memory_type", "episodic")),
                created_at=parse_datetime(payload.get("created_at"), "created_at"),
                updated_at=parse_datetime(payload.get("updated_at"), "updated_at"),
                accessed_at=parse_datetime(payload.get("accessed_at"), "accessed_at"),
                access_count=payload.get("access_count", 0),
                importance=payload.get("importance", 0.5),
                tags=payload.get("tags", []),
                metadata=metadata,
            )
        except Exception as e:
            logger.error(f"Error creating MemoryItem from payload: {e}")
            logger.error(f"Payload field types: {[(k, type(v).__name__) for k, v in payload.items()]}")
            raise

    def touch(self) -> None:
        """Update access timestamp and count."""
        self.accessed_at = datetime.now()
        self.access_count += 1

    def update_importance(self, decay_factor: float = 0.95) -> None:
        """Apply importance decay based on time since last access.

        Args:
            decay_factor: Decay multiplier (0-1)
        """
        days_since_access = (datetime.now() - self.accessed_at).days
        if days_since_access > 0:
            self.importance *= decay_factor**days_since_access


class EpisodicMemory(MemoryItem):
    """Memory of specific events and experiences.

    Episodic memories are time-bound and include contextual information
    about when and where an event occurred.
    """

    memory_type: MemoryType = MemoryType.EPISODIC
    session_id: str | None = None
    project: str | None = None
    user_action: str | None = None

    def to_payload(self) -> dict[str, Any]:
        payload = super().to_payload()
        if self.session_id:
            payload["session_id"] = self.session_id
        if self.project:
            payload["project"] = self.project
        if self.user_action:
            payload["user_action"] = self.user_action
        return payload


class SemanticMemory(MemoryItem):
    """Memory of facts and general knowledge.

    Semantic memories represent factual knowledge that is not tied
    to specific events or experiences.
    """

    memory_type: MemoryType = MemoryType.SEMANTIC
    domain: str | None = None
    source: str | None = None
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    last_verified: datetime | None = None

    def to_payload(self) -> dict[str, Any]:
        payload = super().to_payload()
        if self.domain:
            payload["domain"] = self.domain
        if self.source:
            payload["source"] = self.source
        payload["confidence"] = self.confidence
        if self.last_verified:
            payload["last_verified"] = self.last_verified.isoformat()
        return payload


class ProceduralMemory(MemoryItem):
    """Memory of skills and procedures.

    Procedural memories represent learned skills and know-how,
    including step-by-step procedures and workflows.
    """

    memory_type: MemoryType = MemoryType.PROCEDURAL
    category: str | None = None
    steps: list[str] = Field(default_factory=list)
    success_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    execution_count: int = 0
    last_executed: datetime | None = None

    def to_payload(self) -> dict[str, Any]:
        payload = super().to_payload()
        if self.category:
            payload["category"] = self.category
        if self.steps:
            payload["steps"] = self.steps
        payload["success_rate"] = self.success_rate
        payload["execution_count"] = self.execution_count
        payload["frequency"] = self.execution_count  # For Qdrant index
        if self.last_executed:
            payload["last_executed"] = self.last_executed.isoformat()
        return payload

    def record_execution(self, success: bool = True) -> None:
        """Record a procedure execution.

        Args:
            success: Whether the execution was successful
        """
        self.execution_count += 1
        self.last_executed = datetime.now()
        self.touch()

        # Update success rate (rolling average)
        alpha = 0.1  # Learning rate
        self.success_rate = (1 - alpha) * self.success_rate + alpha * (1.0 if success else 0.0)


class RecallResult(BaseModel):
    """Result from a memory recall operation."""

    memory: MemoryItem
    score: float
    distance: float | None = None

    @property
    def relevance(self) -> str:
        """Human-readable relevance description."""
        if self.score >= 0.9:
            return "highly relevant"
        elif self.score >= 0.7:
            return "relevant"
        elif self.score >= 0.5:
            return "somewhat relevant"
        else:
            return "marginally relevant"


def create_memory(
    content: str,
    memory_type: MemoryType | str,
    **kwargs,
) -> MemoryItem:
    """Factory function to create the appropriate memory type.

    Args:
        content: Memory content
        memory_type: Type of memory to create
        **kwargs: Additional memory attributes

    Returns:
        Appropriate MemoryItem subclass instance
    """
    if isinstance(memory_type, str):
        memory_type = MemoryType(memory_type)

    memory_classes = {
        MemoryType.EPISODIC: EpisodicMemory,
        MemoryType.SEMANTIC: SemanticMemory,
        MemoryType.PROCEDURAL: ProceduralMemory,
    }

    memory_class = memory_classes[memory_type]
    return memory_class(content=content, **kwargs)
