"""Recall memory tool implementation."""

from typing import Any

from mcp_memoria.core.memory_manager import MemoryManager
from mcp_memoria.core.memory_types import MemoryType, RecallResult


class RecallMemoryTool:
    """Tool for recalling memories by semantic similarity."""

    name = "memoria_recall"
    description = "Recall memories similar to a query"

    def __init__(self, memory_manager: MemoryManager):
        self.memory_manager = memory_manager

    async def execute(
        self,
        query: str,
        memory_types: list[str] | None = None,
        limit: int = 5,
        min_score: float = 0.5,
        filters: dict[str, Any] | None = None,
    ) -> list[RecallResult]:
        """Recall relevant memories.

        Args:
            query: Search query
            memory_types: Types to search (all if None)
            limit: Maximum results
            min_score: Minimum similarity score
            filters: Additional filters

        Returns:
            List of RecallResults
        """
        types = None
        if memory_types:
            types = [MemoryType(t) for t in memory_types]

        return await self.memory_manager.recall(
            query=query,
            memory_types=types,
            limit=limit,
            min_score=min_score,
            filters=filters,
        )
