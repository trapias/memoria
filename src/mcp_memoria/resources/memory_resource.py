"""Memory resources for MCP."""

from typing import Any

from mcp_memoria.core.memory_manager import MemoryManager
from mcp_memoria.core.memory_types import MemoryType


class MemoryResource:
    """Resource for accessing memories."""

    def __init__(self, memory_manager: MemoryManager):
        self.memory_manager = memory_manager

    async def list_memories(
        self,
        memory_type: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """List memories.

        Args:
            memory_type: Optional type filter
            limit: Maximum results

        Returns:
            List of memory dicts
        """
        results = await self.memory_manager.search(
            memory_type=memory_type,
            limit=limit,
            sort_by="date",
        )

        return [
            {
                "id": r.memory.id,
                "content": r.memory.content[:200],
                "memory_type": r.memory.memory_type.value,
                "tags": r.memory.tags,
                "importance": r.memory.importance,
                "created_at": r.memory.created_at.isoformat(),
            }
            for r in results
        ]

    async def get_memory(self, memory_id: str, memory_type: str) -> dict[str, Any] | None:
        """Get a specific memory.

        Args:
            memory_id: Memory ID
            memory_type: Memory type

        Returns:
            Memory dict or None
        """
        memory = await self.memory_manager.get(memory_id, MemoryType(memory_type))

        if memory:
            return {
                "id": memory.id,
                "content": memory.content,
                "memory_type": memory.memory_type.value,
                "tags": memory.tags,
                "importance": memory.importance,
                "created_at": memory.created_at.isoformat(),
                "updated_at": memory.updated_at.isoformat(),
                "access_count": memory.access_count,
                "metadata": memory.metadata,
            }

        return None
