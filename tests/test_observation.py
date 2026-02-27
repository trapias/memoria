"""Tests for Observation Consolidation."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_memoria.core.memory_types import MemoryItem, MemoryType
from mcp_memoria.core.observation import (
    ObservationCluster,
    ObservationConsolidator,
)


class TestObservationCluster:
    def _make_mem(self, mid: str, content: str = "test") -> MemoryItem:
        return MemoryItem(
            id=mid, content=content, memory_type=MemoryType.SEMANTIC
        )

    def test_cluster_member_ids(self):
        m1, m2, m3 = self._make_mem("a"), self._make_mem("b"), self._make_mem("c")
        cluster = ObservationCluster(seed=m1, members=[m1, m2, m3], similarity=0.8)
        assert cluster.member_ids == ["a", "b", "c"]

    def test_cluster_len(self):
        m1, m2 = self._make_mem("a"), self._make_mem("b")
        cluster = ObservationCluster(seed=m1, members=[m1, m2], similarity=0.9)
        assert len(cluster) == 2


class TestCosineSimilarity:
    def test_identical_vectors(self):
        sim = ObservationConsolidator._cosine_similarity([1, 0, 0], [1, 0, 0])
        assert sim == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        sim = ObservationConsolidator._cosine_similarity([1, 0], [0, 1])
        assert sim == pytest.approx(0.0)

    def test_opposite_vectors(self):
        sim = ObservationConsolidator._cosine_similarity([1, 0], [-1, 0])
        assert sim == pytest.approx(-1.0)

    def test_similar_vectors(self):
        sim = ObservationConsolidator._cosine_similarity([1, 1], [1, 0.9])
        assert sim > 0.95

    def test_zero_vector(self):
        sim = ObservationConsolidator._cosine_similarity([0, 0], [1, 1])
        assert sim == 0.0


class TestGenerateObservations:
    def _make_mem(self, mid: str, content: str = "test") -> MemoryItem:
        return MemoryItem(
            id=mid, content=content, memory_type=MemoryType.SEMANTIC, importance=0.5
        )

    @pytest.mark.asyncio
    async def test_no_clusters_returns_empty(self):
        mm = AsyncMock()
        embedder = AsyncMock()
        consolidator = ObservationConsolidator(
            memory_manager=mm, embedder=embedder
        )
        result = await consolidator.generate_observations(clusters=[])
        assert result == []

    @pytest.mark.asyncio
    async def test_dry_run_does_not_store(self):
        mm = AsyncMock()
        embedder = AsyncMock()
        embedder.generate = AsyncMock(return_value="This is an insight.")

        cluster = ObservationCluster(
            seed=self._make_mem("a"),
            members=[self._make_mem("a"), self._make_mem("b"), self._make_mem("c")],
            similarity=0.8,
        )

        consolidator = ObservationConsolidator(
            memory_manager=mm, embedder=embedder
        )
        result = await consolidator.generate_observations(
            clusters=[cluster], dry_run=True
        )

        assert len(result) == 1
        assert result[0]["observation"] == "This is an insight."
        assert result[0]["stored"] is False
        assert result[0]["source_count"] == 3
        mm.store.assert_not_called()

    @pytest.mark.asyncio
    async def test_store_when_not_dry_run(self):
        mm = AsyncMock()
        stored_mem = self._make_mem("obs-1", "observation text")
        mm.store = AsyncMock(return_value=stored_mem)

        embedder = AsyncMock()
        embedder.generate = AsyncMock(return_value="Pattern found.")

        cluster = ObservationCluster(
            seed=self._make_mem("a"),
            members=[self._make_mem("a"), self._make_mem("b"), self._make_mem("c")],
            similarity=0.8,
        )

        consolidator = ObservationConsolidator(
            memory_manager=mm, embedder=embedder
        )
        result = await consolidator.generate_observations(
            clusters=[cluster], dry_run=False
        )

        assert result[0]["stored"] is True
        assert result[0]["observation_id"] == "obs-1"
        mm.store.assert_called_once()

    @pytest.mark.asyncio
    async def test_llm_failure_skips_cluster(self):
        mm = AsyncMock()
        embedder = AsyncMock()
        embedder.generate = AsyncMock(side_effect=RuntimeError("LLM down"))

        cluster = ObservationCluster(
            seed=self._make_mem("a"),
            members=[self._make_mem("a"), self._make_mem("b"), self._make_mem("c")],
            similarity=0.8,
        )

        consolidator = ObservationConsolidator(
            memory_manager=mm, embedder=embedder
        )
        result = await consolidator.generate_observations(clusters=[cluster])

        assert len(result) == 0  # Skipped due to error

    @pytest.mark.asyncio
    async def test_graph_relations_created(self):
        mm = AsyncMock()
        stored_mem = self._make_mem("obs-1")
        mm.store = AsyncMock(return_value=stored_mem)

        gm = AsyncMock()
        gm.add_relation = AsyncMock()

        embedder = AsyncMock()
        embedder.generate = AsyncMock(return_value="Insight here.")

        members = [self._make_mem("a"), self._make_mem("b"), self._make_mem("c")]
        cluster = ObservationCluster(
            seed=members[0], members=members, similarity=0.8
        )

        consolidator = ObservationConsolidator(
            memory_manager=mm, embedder=embedder, graph_manager=gm
        )
        await consolidator.generate_observations(clusters=[cluster], dry_run=False)

        assert gm.add_relation.call_count == 3  # one per source member
