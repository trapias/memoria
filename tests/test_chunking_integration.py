"""Integration tests for chunking + full-text search features."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_memoria.config.settings import Settings
from mcp_memoria.core.memory_manager import MemoryManager
from mcp_memoria.core.memory_types import MemoryItem, MemoryType
from mcp_memoria.embeddings.ollama_client import EmbeddingResult


def make_embedding(dim: int = 768, seed: float = 0.1) -> list[float]:
    """Create a deterministic fake embedding vector."""
    import hashlib

    h = hashlib.md5(str(seed).encode()).hexdigest()
    base = [int(h[i : i + 2], 16) / 255.0 for i in range(0, 32, 2)]
    # Repeat to fill dimensions
    return (base * (dim // len(base) + 1))[:dim]


def make_embedder_mock():
    """Create a mock embedder that returns deterministic embeddings."""
    embedder = AsyncMock()
    call_count = 0

    async def embed_side_effect(text, text_type="document", use_cache=True):
        nonlocal call_count
        call_count += 1
        return EmbeddingResult(
            embedding=make_embedding(seed=hash(text) % 1000 / 1000.0),
            model="test-model",
            dimensions=768,
            cached=False,
        )

    embedder.embed = AsyncMock(side_effect=embed_side_effect)
    embedder.embed_batch = AsyncMock(side_effect=lambda texts, **kw: asyncio.gather(
        *[embed_side_effect(t) for t in texts]
    ))
    embedder.check_connection = AsyncMock(return_value=True)
    embedder.ensure_model = AsyncMock(return_value=True)
    embedder.get_model_info = MagicMock(return_value={
        "model": "test-model",
        "host": "http://localhost:11434",
        "dimensions": 768,
    })
    return embedder


@pytest.fixture
def manager(tmp_path):
    """Create a MemoryManager with in-memory Qdrant and mock embedder."""
    settings = Settings(
        qdrant_path=tmp_path / "qdrant",
        cache_path=tmp_path / "cache",
        chunk_size=100,  # Low threshold for testing
        chunk_overlap=20,
    )

    mgr = MemoryManager.__new__(MemoryManager)
    mgr.settings = settings

    # Init storage with in-memory Qdrant
    from mcp_memoria.storage.qdrant_store import QdrantStore
    from mcp_memoria.storage.collections import CollectionManager
    from mcp_memoria.core.consolidation import MemoryConsolidator
    from mcp_memoria.storage.backup import MemoryBackup
    from mcp_memoria.core.working_memory import WorkingMemory
    from mcp_memoria.embeddings.chunking import ChunkingConfig, TextChunker

    mgr.vector_store = QdrantStore()  # in-memory mode
    mgr.collections = CollectionManager(
        store=mgr.vector_store,
        vector_size=768,
    )
    mgr.consolidator = MemoryConsolidator(store=mgr.vector_store)
    mgr.backup = MemoryBackup(store=mgr.vector_store, collection_manager=mgr.collections)
    mgr.embedder = make_embedder_mock()
    mgr.cache = None
    mgr.working_memory = WorkingMemory(max_size=100, default_ttl=3600)
    mgr.chunker = TextChunker(
        ChunkingConfig(chunk_size=100, chunk_overlap=20)
    )
    mgr._initialized = False

    return mgr


@pytest.fixture
async def initialized_manager(manager):
    """Return an initialized manager with collections created."""
    await manager.collections.initialize_collections()
    manager._initialized = True
    return manager


class TestStoreShortContent:
    """Short content should not be chunked."""

    @pytest.mark.asyncio
    async def test_store_short_content_not_chunked(self, initialized_manager):
        mgr = initialized_manager
        memory = await mgr.store(
            content="Short memory content.",
            memory_type="episodic",
            tags=["test"],
        )

        # Should store as a single point, not chunked
        results = await mgr.vector_store.get(
            collection="episodic", ids=[memory.id]
        )
        assert len(results) == 1
        payload = results[0].payload
        assert payload["is_chunk"] is False
        assert payload["parent_id"] == memory.id
        assert "full_content" not in payload


class TestStoreLongContent:
    """Long content should be chunked into multiple points."""

    @pytest.mark.asyncio
    async def test_store_long_content_chunked(self, initialized_manager):
        mgr = initialized_manager
        long_content = "This is a sentence for testing purposes. " * 10  # ~410 chars

        memory = await mgr.store(
            content=long_content,
            memory_type="semantic",
            tags=["chunked"],
            importance=0.8,
        )

        # Should NOT have a direct point with memory.id
        direct = await mgr.vector_store.get(collection="semantic", ids=[memory.id])
        assert len(direct) == 0

        # Should have chunk points with parent_id
        chunk_results, _ = await mgr.vector_store.scroll(
            collection="semantic",
            limit=100,
            filter_conditions={"parent_id": memory.id},
        )
        assert len(chunk_results) >= 2

        # Verify chunk payload structure
        for chunk in chunk_results:
            p = chunk.payload
            assert p["is_chunk"] is True
            assert p["parent_id"] == memory.id
            assert p["full_content"] == long_content
            assert p["chunk_count"] == len(chunk_results)
            assert "chunk_index" in p
            assert p["tags"] == ["chunked"]
            assert p["importance"] == 0.8


class TestRecallDeduplicatesChunks:
    """Recall should return one result per logical memory, not per chunk."""

    @pytest.mark.asyncio
    async def test_recall_deduplicates_chunks(self, initialized_manager):
        mgr = initialized_manager
        long_content = "Unique content about machine learning and neural networks. " * 10

        await mgr.store(
            content=long_content,
            memory_type="semantic",
        )

        results = await mgr.recall(query="machine learning", limit=10)
        # Should get exactly 1 result despite multiple chunks
        assert len(results) == 1


class TestRecallReturnsFullContent:
    """Recall should return the full original content, not chunk text."""

    @pytest.mark.asyncio
    async def test_recall_returns_full_content(self, initialized_manager):
        mgr = initialized_manager
        long_content = "Full original content about Python programming. " * 10

        await mgr.store(content=long_content, memory_type="semantic")

        results = await mgr.recall(query="Python programming", limit=5)
        assert len(results) >= 1
        # The returned content should be the full original, not a chunk
        assert results[0].memory.content == long_content


class TestDeleteRemovesAllChunks:
    """Deleting a memory should remove all its chunks."""

    @pytest.mark.asyncio
    async def test_delete_removes_all_chunks(self, initialized_manager):
        mgr = initialized_manager
        long_content = "Content to be deleted soon. " * 10

        memory = await mgr.store(content=long_content, memory_type="episodic")
        memory_id = memory.id

        # Verify chunks exist
        chunks_before, _ = await mgr.vector_store.scroll(
            collection="episodic",
            limit=100,
            filter_conditions={"parent_id": memory_id},
        )
        assert len(chunks_before) >= 2

        # Delete
        deleted = await mgr.delete(memory_ids=[memory_id], memory_type="episodic")
        assert deleted >= 1

        # Verify all chunks are gone
        chunks_after, _ = await mgr.vector_store.scroll(
            collection="episodic",
            limit=100,
            filter_conditions={"parent_id": memory_id},
        )
        assert len(chunks_after) == 0


class TestUpdateContentRechunks:
    """Updating content should delete old chunks and re-chunk."""

    @pytest.mark.asyncio
    async def test_update_content_rechunks(self, initialized_manager):
        mgr = initialized_manager
        original = "Original long content for update test. " * 10

        memory = await mgr.store(content=original, memory_type="semantic")
        memory_id = memory.id

        # Count original chunks
        original_chunks, _ = await mgr.vector_store.scroll(
            collection="semantic",
            limit=100,
            filter_conditions={"parent_id": memory_id},
        )
        original_count = len(original_chunks)
        assert original_count >= 2

        # Update with different content
        new_content = "Completely new and different content for rechunking. " * 8
        updated = await mgr.update(
            memory_id=memory_id,
            memory_type="semantic",
            content=new_content,
        )
        assert updated is not None
        assert updated.content == new_content

        # Verify chunks are refreshed
        new_chunks, _ = await mgr.vector_store.scroll(
            collection="semantic",
            limit=100,
            filter_conditions={"parent_id": memory_id},
        )
        assert len(new_chunks) >= 1
        # All chunks should have the new full_content
        for chunk in new_chunks:
            assert chunk.payload["full_content"] == new_content


class TestUpdateMetadataUpdatesAllChunks:
    """Metadata-only updates should apply to all chunks."""

    @pytest.mark.asyncio
    async def test_update_metadata_updates_all_chunks(self, initialized_manager):
        mgr = initialized_manager
        content = "Metadata update test content. " * 10

        memory = await mgr.store(
            content=content,
            memory_type="procedural",
            tags=["old-tag"],
            importance=0.5,
        )

        # Update metadata only
        updated = await mgr.update(
            memory_id=memory.id,
            memory_type="procedural",
            tags=["new-tag"],
            importance=0.9,
        )
        assert updated is not None

        # Verify all chunks have updated metadata
        chunks, _ = await mgr.vector_store.scroll(
            collection="procedural",
            limit=100,
            filter_conditions={"parent_id": memory.id},
        )
        for chunk in chunks:
            assert chunk.payload["tags"] == ["new-tag"]
            assert chunk.payload["importance"] == 0.9


class TestGetChunkedMemory:
    """get() should find chunked memories via chunk_0 fallback."""

    @pytest.mark.asyncio
    async def test_get_finds_chunked_memory(self, initialized_manager):
        mgr = initialized_manager
        content = "Memory that will be chunked for get test. " * 10

        memory = await mgr.store(content=content, memory_type="episodic")

        # get() by the original memory ID should work
        retrieved = await mgr.get(memory.id, "episodic")
        assert retrieved is not None
        assert retrieved.id == memory.id
        assert retrieved.content == content


class TestTextMatchFilter:
    """text_match should filter by keyword in content."""

    @pytest.mark.asyncio
    async def test_text_match_filter(self, initialized_manager):
        mgr = initialized_manager

        # Store two different short memories
        await mgr.store(content="Python is a great language", memory_type="semantic")
        await mgr.store(content="Rust is a systems language", memory_type="semantic")

        # Search with text_match (this uses Qdrant full-text index)
        results = await mgr.search(
            memory_type="semantic",
            text_match="Python",
        )

        # All results should contain "Python" in content
        for r in results:
            assert "Python" in r.memory.content


class TestBackwardCompatLegacyMemories:
    """Legacy memories without chunk fields should still work."""

    @pytest.mark.asyncio
    async def test_backward_compat_legacy_memories(self, initialized_manager):
        mgr = initialized_manager

        # Directly insert a legacy-style point (no chunk fields) with a valid UUID
        from mcp_memoria.core.memory_types import MemoryItem, MemoryType
        from datetime import datetime

        legacy_id = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        legacy_payload = {
            "content": "Legacy memory without chunk fields",
            "memory_type": "episodic",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "accessed_at": datetime.now().isoformat(),
            "access_count": 0,
            "importance": 0.5,
            "tags": ["legacy"],
        }

        await mgr.vector_store.upsert(
            collection="episodic",
            vector=make_embedding(seed=0.42),
            payload=legacy_payload,
            id=legacy_id,
        )

        # from_payload should handle missing chunk fields gracefully
        item = MemoryItem.from_payload(legacy_id, legacy_payload)
        assert item.content == "Legacy memory without chunk fields"
        assert item.id == legacy_id

        # get() should find it
        retrieved = await mgr.get(legacy_id, "episodic")
        assert retrieved is not None
        assert retrieved.content == "Legacy memory without chunk fields"

        # recall should include it (deduplicate uses parent_id default = point id)
        results = await mgr.recall(query="legacy memory", limit=10)
        legacy_ids = [r.memory.id for r in results]
        assert legacy_id in legacy_ids


class TestConsolidationSkipsSameParentChunks:
    """Consolidation should not merge chunks from the same parent."""

    @pytest.mark.asyncio
    async def test_consolidation_skips_same_parent_chunks(self, initialized_manager):
        mgr = initialized_manager

        # Store a long memory that gets chunked
        long_content = "Consolidation test content that repeats. " * 10
        memory = await mgr.store(
            content=long_content,
            memory_type="semantic",
            importance=0.8,
        )

        # Run consolidation (dry run)
        result = await mgr.consolidator.consolidate(
            collection="semantic",
            similarity_threshold=0.5,  # Low threshold to potentially match chunks
            dry_run=True,
        )

        # Chunks from the same parent should NOT be counted as merged
        # Since we only have one logical memory, merged_count should be 0
        assert result.merged_count == 0
