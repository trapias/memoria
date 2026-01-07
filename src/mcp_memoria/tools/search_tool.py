"""Search memory tool implementation."""

from datetime import datetime
from typing import Any

from mcp_memoria.core.memory_manager import MemoryManager
from mcp_memoria.core.memory_types import RecallResult


class SearchMemoryTool:
    """Tool for advanced memory search with filters."""

    name = "memoria_search"
    description = "Advanced memory search with filters"

    def __init__(self, memory_manager: MemoryManager):
        self.memory_manager = memory_manager

    async def execute(
        self,
        query: str | None = None,
        memory_type: str | None = None,
        tags: list[str] | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        importance_min: float | None = None,
        project: str | None = None,
        limit: int = 10,
        sort_by: str = "relevance",
    ) -> list[RecallResult]:
        """Search memories with filters.

        Args:
            query: Optional semantic query
            memory_type: Filter by type
            tags: Filter by tags
            date_from: Filter by date range start (ISO format)
            date_to: Filter by date range end (ISO format)
            importance_min: Minimum importance
            project: Filter by project
            limit: Maximum results
            sort_by: Sort order

        Returns:
            List of RecallResults
        """
        parsed_date_from = datetime.fromisoformat(date_from) if date_from else None
        parsed_date_to = datetime.fromisoformat(date_to) if date_to else None

        return await self.memory_manager.search(
            query=query,
            memory_type=memory_type,
            tags=tags,
            date_from=parsed_date_from,
            date_to=parsed_date_to,
            importance_min=importance_min,
            project=project,
            limit=limit,
            sort_by=sort_by,
        )
