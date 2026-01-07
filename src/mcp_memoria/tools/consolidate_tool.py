"""Memory consolidation tool."""

from typing import Any

from mcp_memoria.core.consolidation import ConsolidationResult
from mcp_memoria.core.memory_manager import MemoryManager


class ConsolidateMemoryTool:
    """Tool for consolidating similar memories and applying forgetting."""

    name = "memoria_consolidate"
    description = "Consolidate memories and apply forgetting curve"

    def __init__(self, memory_manager: MemoryManager):
        self.memory_manager = memory_manager

    async def execute(
        self,
        similarity_threshold: float = 0.9,
        forget_days: int = 30,
        min_importance: float = 0.3,
        dry_run: bool = True,
    ) -> dict[str, ConsolidationResult]:
        """Consolidate memories.

        Args:
            similarity_threshold: Threshold for merging similar memories
            forget_days: Days before forgetting unused memories
            min_importance: Minimum importance to retain
            dry_run: Preview without making changes

        Returns:
            Dict of collection name -> ConsolidationResult
        """
        return await self.memory_manager.consolidate(
            similarity_threshold=similarity_threshold,
            forget_days=forget_days,
            min_importance=min_importance,
            dry_run=dry_run,
        )
