"""Search memory tool implementation."""

from datetime import datetime
from typing import Any

from mcp_memoria.core.memory_manager import MemoryManager
from mcp_memoria.core.memory_types import RecallResult


def _parse_date(value: str | datetime | None) -> datetime | None:
    """Safely parse date from string or datetime.

    Args:
        value: Date value (string, datetime, or None)

    Returns:
        datetime or None
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    return None


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
        text_match: str | None = None,
    ) -> list[RecallResult]:
        """Search memories with filters.

        Args:
            query: Optional semantic query
            memory_type: Filter by type
            tags: Filter by tags
            date_from: Filter by date range start (ISO format or datetime)
            date_to: Filter by date range end (ISO format or datetime)
            importance_min: Minimum importance
            project: Filter by project
            limit: Maximum results
            sort_by: Sort order
            text_match: Optional keyword that must appear in content

        Returns:
            List of RecallResults
        """
        parsed_date_from = _parse_date(date_from)
        parsed_date_to = _parse_date(date_to)

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
            text_match=text_match,
        )
