"""Memory management tools (update, delete)."""

from typing import Any

from mcp_memoria.core.memory_manager import MemoryManager
from mcp_memoria.core.memory_types import MemoryItem, MemoryType


class UpdateMemoryTool:
    """Tool for updating existing memories."""

    name = "memoria_update"
    description = "Update an existing memory"

    def __init__(self, memory_manager: MemoryManager):
        self.memory_manager = memory_manager

    async def execute(
        self,
        memory_id: str,
        memory_type: str,
        content: str | None = None,
        tags: list[str] | None = None,
        importance: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryItem | None:
        """Update a memory.

        Args:
            memory_id: Memory ID to update
            memory_type: Memory type
            content: New content (re-embeds if changed)
            tags: New tags
            importance: New importance
            metadata: Additional metadata to merge

        Returns:
            Updated MemoryItem or None if not found
        """
        return await self.memory_manager.update(
            memory_id=memory_id,
            memory_type=MemoryType(memory_type),
            content=content,
            tags=tags,
            importance=importance,
            metadata=metadata,
        )


class DeleteMemoryTool:
    """Tool for deleting memories."""

    name = "memoria_delete"
    description = "Delete memories by ID or filter"

    def __init__(self, memory_manager: MemoryManager):
        self.memory_manager = memory_manager

    async def execute(
        self,
        memory_ids: list[str] | None = None,
        memory_type: str | None = None,
        filter_tags: list[str] | None = None,
    ) -> int:
        """Delete memories.

        Args:
            memory_ids: Specific IDs to delete
            memory_type: Memory type (optional, searches all if omitted)
            filter_tags: Delete by tag filter

        Returns:
            Number of memories deleted
        """
        filters = None
        if filter_tags:
            filters = {"tags": filter_tags}

        return await self.memory_manager.delete(
            memory_ids=memory_ids,
            memory_type=MemoryType(memory_type) if memory_type else None,
            filters=filters,
        )
