"""Central memory manager coordinating all memory operations."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from mcp_memoria.config.settings import Settings
from mcp_memoria.core.consolidation import ConsolidationResult, MemoryConsolidator
from mcp_memoria.core.memory_types import (
    MemoryItem,
    MemoryType,
    RecallResult,
    create_memory,
)
from mcp_memoria.core.working_memory import WorkingMemory
from mcp_memoria.embeddings.embedding_cache import EmbeddingCache
from mcp_memoria.embeddings.ollama_client import OllamaEmbedder
from mcp_memoria.storage.backup import MemoryBackup
from mcp_memoria.storage.collections import CollectionManager, MemoryCollection
from mcp_memoria.storage.qdrant_store import QdrantStore

logger = logging.getLogger(__name__)


class MemoryManager:
    """Central manager for all memory operations.

    Coordinates between embeddings, storage, and working memory
    to provide a unified interface for memory management.
    """

    def __init__(self, settings: Settings | None = None):
        """Initialize memory manager.

        Args:
            settings: Application settings
        """
        self.settings = settings or Settings()
        self.settings.ensure_directories()

        # Initialize components
        self._init_storage()
        self._init_embeddings()
        self._init_working_memory()
        self._initialized = False

    def _init_storage(self) -> None:
        """Initialize storage components."""
        # Use server mode if host is set, otherwise local mode
        qdrant_path = None if self.settings.qdrant_host else self.settings.qdrant_path

        self.vector_store = QdrantStore(
            path=qdrant_path,
            host=self.settings.qdrant_host,
            port=self.settings.qdrant_port,
            vector_size=self.settings.embedding_dimensions,
        )
        self.collections = CollectionManager(
            store=self.vector_store,
            vector_size=self.settings.embedding_dimensions,
        )
        self.consolidator = MemoryConsolidator(store=self.vector_store)
        self.backup = MemoryBackup(store=self.vector_store, collection_manager=self.collections)

    def _init_embeddings(self) -> None:
        """Initialize embedding components."""
        self.cache = (
            EmbeddingCache(self.settings.cache_path) if self.settings.cache_enabled else None
        )
        self.embedder = OllamaEmbedder(
            host=self.settings.ollama_host,
            model=self.settings.embedding_model,
            cache=self.cache,
        )

    def _init_working_memory(self) -> None:
        """Initialize working memory."""
        self.working_memory = WorkingMemory(max_size=100, default_ttl=3600)

    async def initialize(self) -> bool:
        """Initialize the memory system.

        Returns:
            True if successful
        """
        if self._initialized:
            return True

        logger.info("Initializing memory system...")

        # Check Ollama connection
        if not await self.embedder.check_connection():
            logger.error("Failed to connect to Ollama")
            return False

        # Ensure embedding model is available
        if not await self.embedder.ensure_model():
            logger.error(f"Failed to ensure model {self.settings.embedding_model}")
            return False

        # Initialize collections
        results = await self.collections.initialize_collections()
        for name, created in results.items():
            if created:
                logger.info(f"Created collection: {name}")

        self._initialized = True
        logger.info("Memory system initialized successfully")
        return True

    async def store(
        self,
        content: str,
        memory_type: MemoryType | str = MemoryType.EPISODIC,
        tags: list[str] | None = None,
        importance: float = 0.5,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryItem:
        """Store a new memory.

        Args:
            content: Memory content
            memory_type: Type of memory
            tags: Optional tags
            importance: Importance score (0-1)
            metadata: Additional metadata

        Returns:
            Created MemoryItem
        """
        if isinstance(memory_type, str):
            memory_type = MemoryType(memory_type)

        # Create memory item
        memory = create_memory(
            content=content,
            memory_type=memory_type,
            tags=tags or [],
            importance=importance,
            metadata=metadata or {},
        )

        # Add current context
        project = self.working_memory.get_current_project()
        if project and hasattr(memory, "project"):
            memory.project = project

        # Generate embedding
        result = await self.embedder.embed(content, text_type="document")

        # Store in Qdrant
        await self.vector_store.upsert(
            collection=memory_type.value,
            vector=result.embedding,
            payload=memory.to_payload(),
            id=memory.id,
        )

        # Cache in working memory
        self.working_memory.cache_memory(
            memory.id,
            {"memory": memory.model_dump(), "vector": result.embedding},
        )

        # Log action
        self.working_memory.add_to_history(
            "store_memory",
            {"id": memory.id, "type": memory_type.value, "content_preview": content[:100]},
        )

        logger.info(f"Stored {memory_type.value} memory: {memory.id}")
        return memory

    async def recall(
        self,
        query: str,
        memory_types: list[MemoryType | str] | None = None,
        limit: int | None = None,
        min_score: float | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[RecallResult]:
        """Recall memories similar to a query.

        Args:
            query: Search query
            memory_types: Types to search (all if None)
            limit: Maximum results
            min_score: Minimum similarity score
            filters: Additional filters

        Returns:
            List of RecallResults
        """
        limit = limit or self.settings.default_recall_limit
        min_score = min_score or self.settings.min_similarity_score

        if memory_types is None:
            memory_types = [MemoryType.EPISODIC, MemoryType.SEMANTIC, MemoryType.PROCEDURAL]
        else:
            memory_types = [MemoryType(t) if isinstance(t, str) else t for t in memory_types]

        # Generate query embedding
        result = await self.embedder.embed(query, text_type="query")

        all_results = []

        for memory_type in memory_types:
            # Search in collection
            search_results = await self.vector_store.search(
                collection=memory_type.value,
                vector=result.embedding,
                limit=limit,
                score_threshold=min_score,
                filter_conditions=filters,
            )

            for sr in search_results:
                memory = MemoryItem.from_payload(sr.id, sr.payload)

                # Boost importance on access
                await self.consolidator.boost_on_access(
                    collection=memory_type.value,
                    memory_id=sr.id,
                )

                all_results.append(
                    RecallResult(
                        memory=memory,
                        score=sr.score,
                    )
                )

        # Sort by score and limit
        all_results.sort(key=lambda x: x.score, reverse=True)
        all_results = all_results[:limit]

        # Log action
        self.working_memory.add_to_history(
            "recall_memory",
            {
                "query": query[:100],
                "results_count": len(all_results),
                "types": [t.value for t in memory_types],
            },
        )

        return all_results

    async def search(
        self,
        query: str | None = None,
        memory_type: MemoryType | str | None = None,
        tags: list[str] | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        importance_min: float | None = None,
        project: str | None = None,
        limit: int = 10,
        sort_by: str = "relevance",
    ) -> list[RecallResult]:
        """Advanced search with filters.

        Args:
            query: Optional semantic query
            memory_type: Filter by type
            tags: Filter by tags
            date_from: Filter by date range start
            date_to: Filter by date range end
            importance_min: Minimum importance
            project: Filter by project
            limit: Maximum results
            sort_by: Sort order

        Returns:
            List of RecallResults
        """
        filters = {}

        if tags:
            filters["tags"] = tags
        if importance_min:
            filters["importance"] = {"gte": importance_min}
        if project:
            filters["project"] = project
        if date_from:
            filters["created_at"] = filters.get("created_at", {})
            filters["created_at"]["gte"] = date_from.isoformat()
        if date_to:
            filters["created_at"] = filters.get("created_at", {})
            filters["created_at"]["lte"] = date_to.isoformat()

        if query:
            # Semantic search
            types = [MemoryType(memory_type)] if memory_type else None
            return await self.recall(
                query=query,
                memory_types=types,
                limit=limit,
                filters=filters if filters else None,
            )
        else:
            # Filter-only search (scroll through collection)
            collections = (
                [MemoryType(memory_type).value]
                if memory_type
                else [m.value for m in MemoryType]
            )

            results = []
            for collection in collections:
                scroll_results, _ = await self.vector_store.scroll(
                    collection=collection,
                    limit=limit,
                    filter_conditions=filters if filters else None,
                )

                for sr in scroll_results:
                    memory = MemoryItem.from_payload(sr.id, sr.payload)
                    results.append(RecallResult(memory=memory, score=1.0))

            # Sort
            if sort_by == "date":
                results.sort(key=lambda x: x.memory.created_at, reverse=True)
            elif sort_by == "importance":
                results.sort(key=lambda x: x.memory.importance, reverse=True)
            elif sort_by == "access_count":
                results.sort(key=lambda x: x.memory.access_count, reverse=True)

            return results[:limit]

    async def get(self, memory_id: str, memory_type: MemoryType | str) -> MemoryItem | None:
        """Get a specific memory by ID.

        Args:
            memory_id: Memory ID
            memory_type: Memory type

        Returns:
            MemoryItem or None
        """
        if isinstance(memory_type, str):
            memory_type = MemoryType(memory_type)

        # Check working memory cache first
        cached = self.working_memory.get_cached_memory(memory_id)
        if cached:
            return MemoryItem.from_payload(memory_id, cached["memory"])

        # Get from store
        results = await self.vector_store.get(collection=memory_type.value, ids=[memory_id])

        if results:
            memory = MemoryItem.from_payload(results[0].id, results[0].payload)
            return memory

        return None

    async def update(
        self,
        memory_id: str,
        memory_type: MemoryType | str,
        content: str | None = None,
        tags: list[str] | None = None,
        importance: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryItem | None:
        """Update an existing memory.

        Args:
            memory_id: Memory ID
            memory_type: Memory type
            content: New content (re-embeds if changed)
            tags: New tags
            importance: New importance
            metadata: Additional metadata to merge

        Returns:
            Updated MemoryItem or None
        """
        if isinstance(memory_type, str):
            memory_type = MemoryType(memory_type)

        # Get existing memory
        existing = await self.get(memory_id, memory_type)
        if not existing:
            return None

        # Build update payload
        update_payload: dict[str, Any] = {"updated_at": datetime.now().isoformat()}

        if content and content != existing.content:
            # Re-embed if content changed
            result = await self.embedder.embed(content, text_type="document")

            # Update with new vector
            await self.vector_store.upsert(
                collection=memory_type.value,
                vector=result.embedding,
                payload={**existing.to_payload(), "content": content, **update_payload},
                id=memory_id,
            )
        else:
            if tags is not None:
                update_payload["tags"] = tags
            if importance is not None:
                update_payload["importance"] = importance
            if metadata:
                update_payload.update(metadata)

            await self.vector_store.update_payload(
                collection=memory_type.value,
                id=memory_id,
                payload=update_payload,
                merge=True,
            )

        # Invalidate cache
        self.working_memory.invalidate_cache(memory_id)

        # Return updated memory
        return await self.get(memory_id, memory_type)

    async def delete(
        self,
        memory_ids: list[str] | None = None,
        memory_type: MemoryType | str | None = None,
        filters: dict[str, Any] | None = None,
    ) -> int:
        """Delete memories.

        Args:
            memory_ids: Specific IDs to delete
            memory_type: Memory type (required if deleting by ID)
            filters: Delete by filter

        Returns:
            Number of memories deleted
        """
        if memory_ids:
            if not memory_type:
                raise ValueError("memory_type required when deleting by ID")

            if isinstance(memory_type, str):
                memory_type = MemoryType(memory_type)

            deleted = await self.vector_store.delete(
                collection=memory_type.value,
                ids=memory_ids,
            )

            for mid in memory_ids:
                self.working_memory.invalidate_cache(mid)

            return deleted

        elif filters:
            total_deleted = 0
            collections = (
                [MemoryType(memory_type).value]
                if memory_type
                else [m.value for m in MemoryType]
            )

            for collection in collections:
                deleted = await self.vector_store.delete(
                    collection=collection,
                    filter_conditions=filters,
                )
                total_deleted += deleted

            return total_deleted

        return 0

    async def consolidate(
        self,
        similarity_threshold: float | None = None,
        forget_days: int | None = None,
        min_importance: float | None = None,
        dry_run: bool = True,
    ) -> dict[str, ConsolidationResult]:
        """Run consolidation on all collections.

        Args:
            similarity_threshold: Threshold for merging similar memories
            forget_days: Days before forgetting unused memories
            min_importance: Minimum importance to retain
            dry_run: If True, don't actually modify

        Returns:
            Dict of collection name -> ConsolidationResult
        """
        similarity_threshold = similarity_threshold or self.settings.consolidation_threshold
        forget_days = forget_days or self.settings.forgetting_days
        min_importance = min_importance or self.settings.min_importance_threshold

        results = {}

        for memory_type in MemoryType:
            # Merge similar
            merge_result = await self.consolidator.consolidate(
                collection=memory_type.value,
                similarity_threshold=similarity_threshold,
                dry_run=dry_run,
            )

            # Apply forgetting
            forget_result = await self.consolidator.apply_forgetting(
                collection=memory_type.value,
                max_age_days=forget_days,
                min_importance=min_importance,
                dry_run=dry_run,
            )

            results[memory_type.value] = ConsolidationResult(
                merged_count=merge_result.merged_count,
                forgotten_count=forget_result.forgotten_count,
                updated_count=0,
                total_processed=merge_result.total_processed,
                duration_seconds=merge_result.duration_seconds + forget_result.duration_seconds,
                dry_run=dry_run,
            )

        return results

    async def export(
        self,
        output_path: Path,
        format: str = "json",
        memory_types: list[str] | None = None,
        include_vectors: bool = False,
    ) -> dict[str, Any]:
        """Export memories to file.

        Args:
            output_path: Output file path
            format: Export format (json, jsonl)
            memory_types: Types to export
            include_vectors: Include embedding vectors

        Returns:
            Export summary
        """
        if format == "jsonl":
            return await self.backup.export_to_jsonl(
                output_path=output_path,
                memory_types=memory_types,
                include_vectors=include_vectors,
            )
        else:
            return await self.backup.export_to_json(
                output_path=output_path,
                memory_types=memory_types,
                include_vectors=include_vectors,
            )

    async def import_memories(
        self,
        input_path: Path,
        merge: bool = True,
    ) -> dict[str, Any]:
        """Import memories from file.

        Args:
            input_path: Input file path
            merge: Merge with existing or replace

        Returns:
            Import summary
        """
        if input_path.suffix == ".jsonl":
            return await self.backup.import_from_jsonl(input_path, merge=merge)
        else:
            return await self.backup.import_from_json(input_path, merge=merge)

    def get_stats(self) -> dict[str, Any]:
        """Get system statistics.

        Returns:
            Statistics dict
        """
        collection_stats = self.collections.get_collection_stats()
        working_stats = self.working_memory.get_stats()
        model_info = self.embedder.get_model_info()

        total_memories = sum(
            c.get("points_count", 0)
            for c in collection_stats.values()
            if isinstance(c, dict) and "points_count" in c
        )

        return {
            "total_memories": total_memories,
            "collections": collection_stats,
            "working_memory": working_stats,
            "embedding_model": model_info,
            "settings": {
                "qdrant_path": str(self.settings.qdrant_path),
                "cache_enabled": self.settings.cache_enabled,
            },
        }

    def set_context(self, key: str, value: Any) -> None:
        """Set working memory context.

        Args:
            key: Context key
            value: Context value
        """
        self.working_memory.set_context(key, value)

    def get_context(self, key: str) -> Any:
        """Get working memory context.

        Args:
            key: Context key

        Returns:
            Context value
        """
        return self.working_memory.get_context(key)
