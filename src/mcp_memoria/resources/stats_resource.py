"""Statistics resource for MCP."""

from typing import Any

from mcp_memoria.core.memory_manager import MemoryManager


class StatsResource:
    """Resource for memory system statistics."""

    def __init__(self, memory_manager: MemoryManager):
        self.memory_manager = memory_manager

    def get_stats(self) -> dict[str, Any]:
        """Get system statistics.

        Returns:
            Statistics dict
        """
        return self.memory_manager.get_stats()

    def get_collection_stats(self) -> dict[str, Any]:
        """Get per-collection statistics.

        Returns:
            Collection statistics
        """
        stats = self.memory_manager.get_stats()
        return stats.get("collections", {})

    def get_usage_stats(self) -> dict[str, Any]:
        """Get usage statistics.

        Returns:
            Usage statistics
        """
        stats = self.memory_manager.get_stats()
        working = stats.get("working_memory", {})

        return {
            "total_memories": stats.get("total_memories", 0),
            "session_duration": working.get("session_duration_seconds", 0),
            "cached_memories": working.get("cached_memories", 0),
            "context_items": working.get("context_items", 0),
        }
