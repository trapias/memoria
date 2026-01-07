"""Memory export and import tools."""

from pathlib import Path
from typing import Any

from mcp_memoria.core.memory_manager import MemoryManager


class ExportMemoryTool:
    """Tool for exporting memories to file."""

    name = "memoria_export"
    description = "Export memories to a file"

    def __init__(self, memory_manager: MemoryManager):
        self.memory_manager = memory_manager

    async def execute(
        self,
        output_path: str,
        format: str = "json",
        memory_types: list[str] | None = None,
        include_vectors: bool = False,
    ) -> dict[str, Any]:
        """Export memories.

        Args:
            output_path: Output file path
            format: Export format (json, jsonl)
            memory_types: Types to export (all if None)
            include_vectors: Include embedding vectors

        Returns:
            Export summary
        """
        return await self.memory_manager.export(
            output_path=Path(output_path),
            format=format,
            memory_types=memory_types,
            include_vectors=include_vectors,
        )


class ImportMemoryTool:
    """Tool for importing memories from file."""

    name = "memoria_import"
    description = "Import memories from a file"

    def __init__(self, memory_manager: MemoryManager):
        self.memory_manager = memory_manager

    async def execute(
        self,
        input_path: str,
        merge: bool = True,
    ) -> dict[str, Any]:
        """Import memories.

        Args:
            input_path: Input file path
            merge: Merge with existing (False to replace)

        Returns:
            Import summary
        """
        return await self.memory_manager.import_memories(
            input_path=Path(input_path),
            merge=merge,
        )
