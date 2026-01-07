"""Store memory tool implementation."""

from typing import Any

from mcp_memoria.core.memory_manager import MemoryManager
from mcp_memoria.core.memory_types import MemoryItem, MemoryType


class StoreMemoryTool:
    """Tool for storing new memories."""

    name = "memoria_store"
    description = "Store information in persistent memory"

    def __init__(self, memory_manager: MemoryManager):
        self.memory_manager = memory_manager

    async def execute(
        self,
        content: str,
        memory_type: str = "episodic",
        tags: list[str] | None = None,
        importance: float = 0.5,
        project: str | None = None,
        **kwargs: Any,
    ) -> MemoryItem:
        """Store a new memory.

        Args:
            content: Content to memorize
            memory_type: Type of memory (episodic, semantic, procedural)
            tags: Optional tags for categorization
            importance: Importance score (0-1)
            project: Associated project name
            **kwargs: Additional metadata

        Returns:
            Created MemoryItem
        """
        metadata = kwargs.copy()
        if project:
            metadata["project"] = project

        return await self.memory_manager.store(
            content=content,
            memory_type=MemoryType(memory_type),
            tags=tags or [],
            importance=importance,
            metadata=metadata,
        )
