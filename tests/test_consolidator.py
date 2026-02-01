"""Tests for MemoryConsolidator."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from mcp_memoria.core.consolidation import (
    ConsolidationResult,
    MemoryConsolidator,
)
from mcp_memoria.storage.qdrant_store import SearchResult


@pytest.fixture
def mock_store():
    """Create a mock QdrantStore."""
    store = MagicMock()
    store.scroll = AsyncMock(return_value=([], None))
    store.search = AsyncMock(return_value=[])
    store.get = AsyncMock(return_value=[])
    store.update_payload = AsyncMock(return_value=True)
    store.delete = AsyncMock(return_value=0)
    return store


@pytest.fixture
def consolidator(mock_store):
    """Create a consolidator with mocked store."""
    return MemoryConsolidator(store=mock_store)


class TestConsolidate:
    """Tests for consolidate method."""

    @pytest.mark.asyncio
    async def test_consolidate_empty_collection(self, consolidator, mock_store):
        """Test consolidation on empty collection."""
        result = await consolidator.consolidate(
            collection="episodic",
            similarity_threshold=0.9,
            dry_run=True,
        )

        assert isinstance(result, ConsolidationResult)
        assert result.merged_count == 0
        assert result.total_processed == 0
        assert result.dry_run is True

    @pytest.mark.asyncio
    async def test_consolidate_no_similar_memories(self, consolidator, mock_store):
        """Test consolidation with no similar memories."""
        # Single memory, no similar ones
        memory = SearchResult(
            id="mem1",
            score=1.0,
            payload={"content": "test", "chunk_index": 0},
            vector=[0.1] * 768,
        )
        mock_store.scroll.return_value = ([memory], None)
        mock_store.search.return_value = []  # No similar memories

        result = await consolidator.consolidate(
            collection="episodic",
            similarity_threshold=0.9,
            dry_run=True,
        )

        assert result.merged_count == 0
        assert result.total_processed == 1


class TestApplyForgetting:
    """Tests for apply_forgetting method."""

    @pytest.mark.asyncio
    async def test_forgetting_empty_collection(self, consolidator, mock_store):
        """Test forgetting on empty collection."""
        result = await consolidator.apply_forgetting(
            collection="episodic",
            max_age_days=30,
            min_importance=0.3,
            dry_run=True,
        )

        assert result.forgotten_count == 0
        assert result.dry_run is True

    @pytest.mark.asyncio
    async def test_forgetting_skips_recent_memories(self, consolidator, mock_store):
        """Test that recent memories are not forgotten."""
        recent_memory = SearchResult(
            id="mem1",
            score=1.0,
            payload={
                "content": "recent",
                "chunk_index": 0,
                "accessed_at": datetime.now().isoformat(),
                "importance": 0.1,
                "access_count": 0,
            },
        )
        mock_store.scroll.return_value = ([recent_memory], None)

        result = await consolidator.apply_forgetting(
            collection="episodic",
            max_age_days=30,
            min_importance=0.3,
            dry_run=True,
        )

        assert result.forgotten_count == 0

    @pytest.mark.asyncio
    async def test_forgetting_targets_old_low_importance(self, consolidator, mock_store):
        """Test that old, low-importance, unaccessed memories are forgotten."""
        old_date = datetime.now() - timedelta(days=60)
        old_memory = SearchResult(
            id="mem1",
            score=1.0,
            payload={
                "content": "old",
                "chunk_index": 0,
                "parent_id": "mem1",
                "accessed_at": old_date.isoformat(),
                "importance": 0.1,
                "access_count": 0,
            },
        )
        mock_store.scroll.return_value = ([old_memory], None)

        result = await consolidator.apply_forgetting(
            collection="episodic",
            max_age_days=30,
            min_importance=0.3,
            dry_run=True,
        )

        assert result.forgotten_count == 1


class TestBoostOnAccess:
    """Tests for boost_on_access method."""

    @pytest.mark.asyncio
    async def test_boost_increases_importance(self, consolidator, mock_store):
        """Test that boost increases importance."""
        memory = SearchResult(
            id="mem1",
            score=1.0,
            payload={
                "importance": 0.5,
                "access_count": 5,
                "is_chunk": False,
            },
        )
        mock_store.get.return_value = [memory]

        new_importance = await consolidator.boost_on_access(
            collection="episodic",
            memory_id="mem1",
            boost_amount=0.1,
        )

        assert new_importance == 0.6
        mock_store.update_payload.assert_called_once()

    @pytest.mark.asyncio
    async def test_boost_caps_at_max(self, consolidator, mock_store):
        """Test that importance is capped at max."""
        memory = SearchResult(
            id="mem1",
            score=1.0,
            payload={
                "importance": 0.95,
                "access_count": 10,
                "is_chunk": False,
            },
        )
        mock_store.get.return_value = [memory]

        new_importance = await consolidator.boost_on_access(
            collection="episodic",
            memory_id="mem1",
            boost_amount=0.1,
            max_importance=1.0,
        )

        assert new_importance == 1.0

    @pytest.mark.asyncio
    async def test_boost_missing_memory(self, consolidator, mock_store):
        """Test boost on non-existent memory."""
        mock_store.get.return_value = []

        new_importance = await consolidator.boost_on_access(
            collection="episodic",
            memory_id="nonexistent",
        )

        assert new_importance == 0.0
        mock_store.update_payload.assert_not_called()


class TestBoostOnAccessBatch:
    """Tests for boost_on_access_batch method."""

    @pytest.mark.asyncio
    async def test_batch_boost_empty_list(self, consolidator, mock_store):
        """Test batch boost with empty list."""
        await consolidator.boost_on_access_batch([])
        mock_store.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_batch_boost_multiple_memories(self, consolidator, mock_store):
        """Test batch boost with multiple memories."""
        memories = [
            SearchResult(
                id="mem1",
                score=1.0,
                payload={
                    "importance": 0.5,
                    "access_count": 1,
                    "is_chunk": False,
                    "parent_id": "mem1",
                },
            ),
        ]
        mock_store.get.return_value = memories
        mock_store.scroll.return_value = ([], None)

        await consolidator.boost_on_access_batch([
            ("episodic", "mem1"),
            ("semantic", "mem2"),
        ])

        # Should call get for each collection
        assert mock_store.get.call_count >= 1
