"""Central memory manager coordinating all memory operations."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid5

from mcp_memoria.config.settings import Settings
from mcp_memoria.core.consolidation import ConsolidationResult, MemoryConsolidator
from mcp_memoria.core.memory_types import (
    MemoryItem,
    MemoryType,
    RecallResult,
    create_memory,
)
from mcp_memoria.core.working_memory import WorkingMemory
from mcp_memoria.embeddings.chunking import ChunkingConfig, TextChunker
from mcp_memoria.embeddings.embedding_cache import EmbeddingCache
from mcp_memoria.embeddings.ollama_client import OllamaEmbedder
from mcp_memoria.storage.backup import MemoryBackup
from mcp_memoria.storage.collections import CollectionManager, MemoryCollection
from mcp_memoria.storage.qdrant_store import QdrantStore

logger = logging.getLogger(__name__)

# Namespace UUID for generating deterministic chunk IDs
_CHUNK_NAMESPACE = UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")


def _chunk_id(parent_id: str, chunk_index: int) -> str:
    """Generate a deterministic UUID for a chunk.

    Args:
        parent_id: Parent memory UUID string
        chunk_index: Chunk index

    Returns:
        Deterministic UUID string
    """
    return str(uuid5(_CHUNK_NAMESPACE, f"{parent_id}__chunk_{chunk_index}"))


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
        self._init_chunker()
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

    def _init_chunker(self) -> None:
        """Initialize text chunker."""
        self.chunker = TextChunker(
            ChunkingConfig(
                chunk_size=self.settings.chunk_size,
                chunk_overlap=self.settings.chunk_overlap,
            )
        )

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

        needs_chunking = len(content) > self.settings.chunk_size

        if needs_chunking:
            # Chunk the content and store each chunk as a separate point
            chunks = self.chunker.chunk(content)
            chunk_count = len(chunks)
            base_payload = memory.to_payload()

            points = []
            for chunk in chunks:
                chunk_id = _chunk_id(memory.id, chunk.chunk_index)
                embedding_result = await self.embedder.embed(chunk.text, text_type="document")
                chunk_payload = {
                    **base_payload,
                    "content": chunk.text,
                    "full_content": content,
                    "is_chunk": True,
                    "parent_id": memory.id,
                    "chunk_index": chunk.chunk_index,
                    "chunk_count": chunk_count,
                }
                points.append((embedding_result.embedding, chunk_payload, chunk_id))

            await self.vector_store.upsert_batch(
                collection=memory_type.value,
                points=points,
            )
            logger.info(f"Stored {memory_type.value} memory {memory.id} in {chunk_count} chunks")
        else:
            # Single-point storage (backward compatible)
            result = await self.embedder.embed(content, text_type="document")
            payload = memory.to_payload()
            payload["is_chunk"] = False
            payload["parent_id"] = memory.id

            await self.vector_store.upsert(
                collection=memory_type.value,
                vector=result.embedding,
                payload=payload,
                id=memory.id,
            )

        # Cache in working memory (use mode='json' to serialize datetimes to ISO strings)
        self.working_memory.cache_memory(
            memory.id,
            {"memory": memory.model_dump(mode='json')},
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
        text_match: str | None = None,
    ) -> list[RecallResult]:
        """Recall memories similar to a query.

        Args:
            query: Search query
            memory_types: Types to search (all if None)
            limit: Maximum results
            min_score: Minimum similarity score
            filters: Additional filters
            text_match: Optional keyword that must appear in content

        Returns:
            List of RecallResults
        """
        limit = limit or self.settings.default_recall_limit
        min_score = min_score or self.settings.min_similarity_score

        if memory_types is None:
            memory_types = [MemoryType.EPISODIC, MemoryType.SEMANTIC, MemoryType.PROCEDURAL]
        else:
            memory_types = [MemoryType(t) if isinstance(t, str) else t for t in memory_types]

        # Add text_match to filters if provided
        if text_match:
            filters = dict(filters) if filters else {}
            filters["__text_match"] = text_match

        # Generate query embedding
        result = await self.embedder.embed(query, text_type="query")

        # Over-fetch to compensate for chunk deduplication
        fetch_limit = limit * 3

        all_results = []

        for memory_type in memory_types:
            # Search in collection
            search_results = await self.vector_store.search(
                collection=memory_type.value,
                vector=result.embedding,
                limit=fetch_limit,
                score_threshold=min_score,
                filter_conditions=filters,
            )

            for sr in search_results:
                all_results.append((sr, memory_type))

        # Deduplicate by parent_id: keep the best score per logical memory
        best_by_parent: dict[str, tuple] = {}
        for sr, memory_type in all_results:
            parent_id = sr.payload.get("parent_id", sr.id)
            if parent_id not in best_by_parent or sr.score > best_by_parent[parent_id][0].score:
                best_by_parent[parent_id] = (sr, memory_type)

        # Build deduplicated results
        deduped_results = []
        for parent_id, (sr, memory_type) in best_by_parent.items():
            memory = MemoryItem.from_payload(parent_id, sr.payload)

            # Boost importance on access
            await self.consolidator.boost_on_access(
                collection=memory_type.value,
                memory_id=sr.id,
            )

            deduped_results.append(
                RecallResult(
                    memory=memory,
                    score=sr.score,
                )
            )

        # Sort by score and limit
        deduped_results.sort(key=lambda x: x.score, reverse=True)
        deduped_results = deduped_results[:limit]

        # Log action
        self.working_memory.add_to_history(
            "recall_memory",
            {
                "query": query[:100],
                "results_count": len(deduped_results),
                "types": [t.value for t in memory_types],
            },
        )

        return deduped_results

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
        text_match: str | None = None,
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
            text_match: Optional keyword that must appear in content

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
        if text_match:
            filters["__text_match"] = text_match

        if query:
            # Semantic search
            types = [MemoryType(memory_type)] if memory_type else None
            return await self.recall(
                query=query,
                memory_types=types,
                limit=limit,
                filters=filters if filters else None,
                text_match=None,  # already in filters
            )
        else:
            # Filter-only search (scroll through collection)
            collections = (
                [MemoryType(memory_type).value]
                if memory_type
                else [m.value for m in MemoryType]
            )

            # Over-fetch for chunk deduplication
            fetch_limit = limit * 3

            all_scroll_results = []
            for collection in collections:
                scroll_results, _ = await self.vector_store.scroll(
                    collection=collection,
                    limit=fetch_limit,
                    filter_conditions=filters if filters else None,
                )
                all_scroll_results.extend(scroll_results)

            # Deduplicate by parent_id
            seen_parents: dict[str, Any] = {}
            for sr in all_scroll_results:
                parent_id = sr.payload.get("parent_id", sr.id)
                if parent_id not in seen_parents:
                    seen_parents[parent_id] = sr

            results = []
            for parent_id, sr in seen_parents.items():
                memory = MemoryItem.from_payload(parent_id, sr.payload)
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
            try:
                return MemoryItem.from_payload(memory_id, cached["memory"])
            except Exception as e:
                logger.error(f"Error parsing cached memory {memory_id}: {e}")
                logger.error(f"Cache data types: {[(k, type(v).__name__) for k, v in cached['memory'].items()]}")
                raise

        # Get from store — try direct ID first
        results = await self.vector_store.get(collection=memory_type.value, ids=[memory_id])

        if not results:
            # Fallback: try chunk_0 ID (memory was chunked)
            chunk_0_id = _chunk_id(memory_id, 0)
            results = await self.vector_store.get(collection=memory_type.value, ids=[chunk_0_id])

        if results:
            try:
                # Use parent_id as the memory ID for chunked memories
                parent_id = results[0].payload.get("parent_id", results[0].id)
                memory = MemoryItem.from_payload(parent_id, results[0].payload)
                return memory
            except Exception as e:
                logger.error(f"Error parsing Qdrant memory {results[0].id}: {e}")
                logger.error(f"Payload types: {[(k, type(v).__name__) for k, v in results[0].payload.items()]}")
                raise

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

        if content and content != existing.content:
            # Content changed: delete all old chunks/points and re-store
            await self._delete_memory_points(memory_id, memory_type.value)

            # Re-store with new content (preserving original metadata)
            updated = await self.store(
                content=content,
                memory_type=memory_type,
                tags=tags if tags is not None else existing.tags,
                importance=importance if importance is not None else existing.importance,
                metadata=metadata or existing.metadata,
            )
            # The new memory gets a new ID from store(), but we want to keep the original ID.
            # So we delete the newly-created points and re-create them with the old ID.
            new_id = updated.id
            await self._delete_memory_points(new_id, memory_type.value)

            # Re-create with original ID
            updated_memory = create_memory(
                content=content,
                memory_type=memory_type,
                tags=tags if tags is not None else existing.tags,
                importance=importance if importance is not None else existing.importance,
                metadata=metadata or existing.metadata,
            )
            updated_memory.id = memory_id
            updated_memory.created_at = existing.created_at

            needs_chunking = len(content) > self.settings.chunk_size
            if needs_chunking:
                chunks = self.chunker.chunk(content)
                chunk_count = len(chunks)
                base_payload = updated_memory.to_payload()
                base_payload["updated_at"] = datetime.now().isoformat()

                points = []
                for chunk in chunks:
                    chunk_id = _chunk_id(memory_id, chunk.chunk_index)
                    emb = await self.embedder.embed(chunk.text, text_type="document")
                    chunk_payload = {
                        **base_payload,
                        "content": chunk.text,
                        "full_content": content,
                        "is_chunk": True,
                        "parent_id": memory_id,
                        "chunk_index": chunk.chunk_index,
                        "chunk_count": chunk_count,
                    }
                    points.append((emb.embedding, chunk_payload, chunk_id))

                await self.vector_store.upsert_batch(
                    collection=memory_type.value,
                    points=points,
                )
            else:
                emb = await self.embedder.embed(content, text_type="document")
                payload = updated_memory.to_payload()
                payload["updated_at"] = datetime.now().isoformat()
                payload["is_chunk"] = False
                payload["parent_id"] = memory_id

                await self.vector_store.upsert(
                    collection=memory_type.value,
                    vector=emb.embedding,
                    payload=payload,
                    id=memory_id,
                )
        else:
            # Metadata-only update: apply to all points for this memory
            update_payload: dict[str, Any] = {"updated_at": datetime.now().isoformat()}
            if tags is not None:
                update_payload["tags"] = tags
            if importance is not None:
                update_payload["importance"] = importance
            if metadata:
                update_payload.update(metadata)

            point_ids = await self._get_memory_point_ids(memory_id, memory_type.value)
            for pid in point_ids:
                await self.vector_store.update_payload(
                    collection=memory_type.value,
                    id=pid,
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

            total_deleted = 0
            for mid in memory_ids:
                deleted = await self._delete_memory_points(mid, memory_type.value)
                total_deleted += max(deleted, 1)  # count at least 1 per requested ID
                self.working_memory.invalidate_cache(mid)

            return total_deleted

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

    async def _get_memory_point_ids(self, memory_id: str, collection: str) -> list[str]:
        """Find all Qdrant point IDs belonging to a logical memory.

        Looks for both the direct ID and any chunks with matching parent_id.

        Args:
            memory_id: Logical memory ID
            collection: Collection name

        Returns:
            List of point IDs
        """
        ids = []

        # Check if direct ID exists
        direct = await self.vector_store.get(collection=collection, ids=[memory_id])
        if direct:
            ids.append(memory_id)

        # Find chunks by parent_id
        chunk_results, _ = await self.vector_store.scroll(
            collection=collection,
            limit=1000,
            filter_conditions={"parent_id": memory_id},
        )
        for cr in chunk_results:
            if cr.id not in ids:
                ids.append(cr.id)

        return ids

    async def _delete_memory_points(self, memory_id: str, collection: str) -> int:
        """Delete all Qdrant points belonging to a logical memory.

        Args:
            memory_id: Logical memory ID
            collection: Collection name

        Returns:
            Number of points deleted
        """
        point_ids = await self._get_memory_point_ids(memory_id, collection)
        if point_ids:
            await self.vector_store.delete(collection=collection, ids=point_ids)
        return len(point_ids)

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
