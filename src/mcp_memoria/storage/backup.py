"""Backup and restore functionality for memories."""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator

from mcp_memoria.storage.collections import CollectionManager, MemoryCollection
from mcp_memoria.storage.qdrant_store import QdrantStore

logger = logging.getLogger(__name__)


class PathTraversalError(Exception):
    """Raised when a path traversal attack is detected."""

    pass


def validate_safe_path(path: Path, allowed_dirs: list[Path] | None = None) -> Path:
    """Validate that a path is safe and doesn't escape allowed directories.

    Args:
        path: Path to validate
        allowed_dirs: Optional list of allowed parent directories.
                     If None, defaults to user's home directory and /tmp.

    Returns:
        Resolved absolute path

    Raises:
        PathTraversalError: If path escapes allowed directories
        ValueError: If path is invalid
    """
    # Resolve to absolute path, following symlinks
    try:
        resolved = path.resolve()
    except (OSError, ValueError) as e:
        raise ValueError(f"Invalid path: {path}") from e

    # Default allowed directories: home and temp
    if allowed_dirs is None:
        home = Path.home()
        allowed_dirs = [
            home,
            Path("/tmp"),
            Path(os.environ.get("TMPDIR", "/tmp")),
        ]

    # Check if resolved path is under any allowed directory
    for allowed in allowed_dirs:
        try:
            allowed_resolved = allowed.resolve()
            # Check if resolved path starts with allowed path
            if resolved == allowed_resolved or allowed_resolved in resolved.parents:
                return resolved
        except (OSError, ValueError):
            continue

    raise PathTraversalError(
        f"Path '{path}' resolves to '{resolved}' which is outside allowed directories. "
        f"Allowed: {[str(d) for d in allowed_dirs]}"
    )


class MemoryBackup:
    """Handles export and import of memories."""

    def __init__(self, store: QdrantStore, collection_manager: CollectionManager):
        """Initialize backup handler.

        Args:
            store: Qdrant store instance
            collection_manager: Collection manager instance
        """
        self.store = store
        self.collection_manager = collection_manager

    async def export_to_json(
        self,
        output_path: Path,
        memory_types: list[str] | None = None,
        include_vectors: bool = False,
    ) -> dict[str, Any]:
        """Export memories to JSON file.

        Args:
            output_path: Output file path
            memory_types: Types to export (all if None)
            include_vectors: Include embedding vectors

        Returns:
            Export summary

        Raises:
            PathTraversalError: If output_path escapes allowed directories
        """
        # Validate path to prevent path traversal attacks
        output_path = validate_safe_path(output_path)

        types_to_export = memory_types or [m.value for m in MemoryCollection]
        export_data = {
            "version": "1.0",
            "exported_at": datetime.now().isoformat(),
            "include_vectors": include_vectors,
            "collections": {},
        }

        total_count = 0

        for memory_type in types_to_export:
            if not self.collection_manager.collection_exists(memory_type):
                continue

            memories = []
            async for memory in self._scroll_collection(memory_type, include_vectors):
                memories.append(memory)
                total_count += 1

            export_data["collections"][memory_type] = memories
            logger.info(f"Exported {len(memories)} memories from {memory_type}")

        # Write to file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Export complete: {total_count} memories to {output_path}")

        return {
            "total_memories": total_count,
            "collections": {k: len(v) for k, v in export_data["collections"].items()},
            "output_path": str(output_path),
            "include_vectors": include_vectors,
        }

    async def export_to_jsonl(
        self,
        output_path: Path,
        memory_types: list[str] | None = None,
        include_vectors: bool = False,
    ) -> dict[str, Any]:
        """Export memories to JSONL file (streaming format).

        Args:
            output_path: Output file path
            memory_types: Types to export (all if None)
            include_vectors: Include embedding vectors

        Returns:
            Export summary

        Raises:
            PathTraversalError: If output_path escapes allowed directories
        """
        # Validate path to prevent path traversal attacks
        output_path = validate_safe_path(output_path)

        types_to_export = memory_types or [m.value for m in MemoryCollection]
        output_path.parent.mkdir(parents=True, exist_ok=True)

        counts = {}
        total_count = 0

        with open(output_path, "w", encoding="utf-8") as f:
            for memory_type in types_to_export:
                if not self.collection_manager.collection_exists(memory_type):
                    continue

                count = 0
                async for memory in self._scroll_collection(memory_type, include_vectors):
                    memory["_collection"] = memory_type
                    f.write(json.dumps(memory, ensure_ascii=False) + "\n")
                    count += 1
                    total_count += 1

                counts[memory_type] = count
                logger.info(f"Exported {count} memories from {memory_type}")

        logger.info(f"Export complete: {total_count} memories to {output_path}")

        return {
            "total_memories": total_count,
            "collections": counts,
            "output_path": str(output_path),
            "format": "jsonl",
        }

    async def import_from_json(
        self,
        input_path: Path,
        merge: bool = True,
    ) -> dict[str, Any]:
        """Import memories from JSON file.

        Args:
            input_path: Input file path
            merge: If True, merge with existing; if False, replace

        Returns:
            Import summary

        Raises:
            PathTraversalError: If input_path escapes allowed directories
        """
        # Validate path to prevent path traversal attacks
        input_path = validate_safe_path(input_path)

        with open(input_path, encoding="utf-8") as f:
            import_data = json.load(f)

        # Validate format
        if "collections" not in import_data:
            raise ValueError("Invalid import file format: missing 'collections'")

        include_vectors = import_data.get("include_vectors", False)
        total_imported = 0
        counts = {}

        for memory_type, memories in import_data["collections"].items():
            # Ensure collection exists
            if not self.collection_manager.collection_exists(memory_type):
                try:
                    collection = MemoryCollection(memory_type)
                    await self.collection_manager._create_collection(collection)
                except ValueError:
                    logger.warning(f"Skipping unknown memory type: {memory_type}")
                    continue

            if not merge:
                # Clear existing data
                await self.store.delete(
                    collection=memory_type,
                    filter_conditions={},
                )

            # Import memories
            count = 0
            for memory in memories:
                memory_id = memory.get("id")
                vector = memory.get("vector")
                payload = memory.get("payload", {})

                if not include_vectors or not vector:
                    # Skip if no vector and vectors weren't exported
                    logger.warning(f"Skipping memory {memory_id}: no vector data")
                    continue

                await self.store.upsert(
                    collection=memory_type,
                    vector=vector,
                    payload=payload,
                    id=memory_id,
                )
                count += 1

            counts[memory_type] = count
            total_imported += count
            logger.info(f"Imported {count} memories to {memory_type}")

        return {
            "total_imported": total_imported,
            "collections": counts,
            "source_file": str(input_path),
            "merge_mode": merge,
        }

    async def import_from_jsonl(
        self,
        input_path: Path,
        merge: bool = True,
    ) -> dict[str, Any]:
        """Import memories from JSONL file.

        Args:
            input_path: Input file path
            merge: If True, merge with existing; if False, replace

        Returns:
            Import summary

        Raises:
            PathTraversalError: If input_path escapes allowed directories
        """
        # Validate path to prevent path traversal attacks
        input_path = validate_safe_path(input_path)

        if not merge:
            # Clear all collections first
            for memory_type in MemoryCollection:
                if self.collection_manager.collection_exists(memory_type.value):
                    await self.store.delete(
                        collection=memory_type.value,
                        filter_conditions={},
                    )

        counts: dict[str, int] = {}
        total_imported = 0

        with open(input_path, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue

                memory = json.loads(line)
                memory_type = memory.pop("_collection", "episodic")

                # Ensure collection exists
                if not self.collection_manager.collection_exists(memory_type):
                    try:
                        collection = MemoryCollection(memory_type)
                        await self.collection_manager._create_collection(collection)
                    except ValueError:
                        continue

                memory_id = memory.get("id")
                vector = memory.get("vector")
                payload = memory.get("payload", {})

                if not vector:
                    continue

                await self.store.upsert(
                    collection=memory_type,
                    vector=vector,
                    payload=payload,
                    id=memory_id,
                )

                counts[memory_type] = counts.get(memory_type, 0) + 1
                total_imported += 1

        logger.info(f"Import complete: {total_imported} memories from {input_path}")

        return {
            "total_imported": total_imported,
            "collections": counts,
            "source_file": str(input_path),
            "merge_mode": merge,
        }

    async def _scroll_collection(
        self,
        collection: str,
        with_vectors: bool = False,
    ) -> AsyncIterator[dict[str, Any]]:
        """Scroll through all memories in a collection.

        Deduplicates chunked memories by parent_id, exporting full_content
        and stripping chunk-specific fields.

        Args:
            collection: Collection name
            with_vectors: Include vectors

        Yields:
            Memory dicts
        """
        offset = None
        seen_parents: set[str] = set()

        while True:
            results, next_offset = await self.store.scroll(
                collection=collection,
                limit=100,
                offset=offset,
                with_vectors=with_vectors,
            )

            for result in results:
                parent_id = result.payload.get("parent_id", result.id)

                # Deduplicate: only export once per logical memory
                if parent_id in seen_parents:
                    continue
                seen_parents.add(parent_id)

                # Build clean payload: use full_content if available, strip chunk fields
                payload = dict(result.payload)
                if "full_content" in payload:
                    payload["content"] = payload.pop("full_content")
                # Remove chunk-specific fields from export
                for chunk_field in ("is_chunk", "parent_id", "chunk_index", "chunk_count", "full_content"):
                    payload.pop(chunk_field, None)

                memory = {
                    "id": parent_id,
                    "payload": payload,
                }
                if with_vectors and result.vector:
                    memory["vector"] = result.vector

                yield memory

            if not next_offset:
                break

            offset = next_offset
