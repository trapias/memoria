"""Multi-strategy recall with Reciprocal Rank Fusion (RRF).

Combines semantic vector search with keyword full-text search for
improved retrieval quality. Optionally includes graph-based retrieval
when PostgreSQL is available.
"""

import asyncio
import logging
import math
from datetime import UTC, datetime
from typing import Any

from mcp_memoria.core.memory_types import MemoryItem, MemoryType, RecallResult
from mcp_memoria.embeddings.ollama_client import OllamaEmbedder
from mcp_memoria.storage.qdrant_store import QdrantStore, SearchResult

logger = logging.getLogger(__name__)

# RRF constant — standard value from the original paper (Cormack et al.)
RRF_K = 60


def _rrf_score(rank: int, weight: float = 1.0) -> float:
    """Compute RRF score for a result at the given rank.

    Args:
        rank: 1-based rank position
        weight: Strategy weight multiplier

    Returns:
        RRF contribution score
    """
    return weight / (RRF_K + rank)


def _recency_factor(created_at: datetime) -> float:
    """Compute a recency factor (0-1) for ranking keyword results.

    More recent memories rank higher. Uses exponential decay with
    half-life of 30 days.

    Args:
        created_at: Memory creation timestamp

    Returns:
        Recency factor between 0 and 1
    """
    now = datetime.now(UTC)
    try:
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        age_days = max((now - created_at).total_seconds() / 86400, 0)
    except Exception:
        age_days = 0
    half_life = 30.0
    return math.exp(-0.693 * age_days / half_life)


class MultiRecall:
    """Multi-strategy recall engine with RRF fusion.

    Strategies:
    1. Semantic: Vector similarity search (primary)
    2. Keyword: Full-text MatchText search ranked by quality
    3. Graph: Neighbor traversal (optional, requires GraphManager)
    """

    def __init__(
        self,
        vector_store: QdrantStore,
        embedder: OllamaEmbedder,
        graph_manager: Any | None = None,
        semantic_weight: float = 1.0,
        keyword_weight: float = 0.5,
        graph_weight: float = 0.3,
    ):
        self.vector_store = vector_store
        self.embedder = embedder
        self.graph_manager = graph_manager
        self.semantic_weight = semantic_weight
        self.keyword_weight = keyword_weight
        self.graph_weight = graph_weight

    async def hybrid_recall(
        self,
        query: str,
        memory_types: list[MemoryType | str],
        limit: int = 5,
        min_score: float = 0.5,
        filters: dict[str, Any] | None = None,
    ) -> list[RecallResult]:
        """Run multi-strategy recall with RRF fusion.

        Args:
            query: Search query
            memory_types: Memory types to search (enum or string)
            limit: Maximum results to return
            min_score: Minimum similarity score for semantic search
            filters: Additional filter conditions

        Returns:
            Fused list of RecallResults
        """
        # Normalize memory_types to enums
        memory_types = [MemoryType(t) if isinstance(t, str) else t for t in memory_types]
        # Run semantic and keyword strategies in parallel
        semantic_task = self._semantic_strategy(
            query, memory_types, limit * 3, min_score, filters
        )
        keyword_task = self._keyword_strategy(
            query, memory_types, limit * 3, filters
        )

        tasks = [semantic_task, keyword_task]

        # Include graph strategy if available and we have semantic results to seed from
        # Graph runs after semantic since it needs a seed memory_id
        results = await asyncio.gather(*tasks, return_exceptions=True)

        semantic_results = results[0] if not isinstance(results[0], Exception) else []
        keyword_results = results[1] if not isinstance(results[1], Exception) else []

        if isinstance(results[0], Exception):
            logger.warning(f"Semantic strategy failed: {results[0]}")
        if isinstance(results[1], Exception):
            logger.warning(f"Keyword strategy failed: {results[1]}")

        # Run graph strategy seeded from top semantic result
        graph_results: list[tuple[str, MemoryItem]] = []
        if self.graph_manager and semantic_results:
            try:
                top_id = semantic_results[0][0]  # parent_id
                graph_results = await self._graph_strategy(
                    top_id, memory_types, limit * 2
                )
            except Exception as e:
                logger.warning(f"Graph strategy failed: {e}")

        # RRF fusion
        fused = self._rrf_fuse(
            semantic_results, keyword_results, graph_results
        )

        # Return top results
        return fused[:limit]

    async def _semantic_strategy(
        self,
        query: str,
        memory_types: list[MemoryType],
        limit: int,
        min_score: float,
        filters: dict[str, Any] | None,
    ) -> list[tuple[str, MemoryItem, float]]:
        """Semantic vector search strategy.

        Returns:
            List of (parent_id, MemoryItem, score) tuples
        """
        result = await self.embedder.embed(query, text_type="query")

        all_results: list[tuple[SearchResult, MemoryType]] = []
        for memory_type in memory_types:
            search_results = await self.vector_store.search(
                collection=memory_type.value,
                vector=result.embedding,
                limit=limit,
                score_threshold=min_score,
                filter_conditions=filters,
            )
            for sr in search_results:
                all_results.append((sr, memory_type))

        # Deduplicate by parent_id
        best_by_parent: dict[str, tuple[SearchResult, MemoryType]] = {}
        for sr, mt in all_results:
            parent_id = sr.payload.get("parent_id", sr.id)
            if parent_id not in best_by_parent or sr.score > best_by_parent[parent_id][0].score:
                best_by_parent[parent_id] = (sr, mt)

        results = []
        for parent_id, (sr, _mt) in best_by_parent.items():
            memory = MemoryItem.from_payload(parent_id, sr.payload)
            results.append((parent_id, memory, sr.score))

        # Sort by score descending
        results.sort(key=lambda x: x[2], reverse=True)
        return results

    async def _keyword_strategy(
        self,
        query: str,
        memory_types: list[MemoryType],
        limit: int,
        filters: dict[str, Any] | None,
    ) -> list[tuple[str, MemoryItem, float]]:
        """Keyword full-text search strategy.

        Uses Qdrant MatchText for keyword matching, then ranks results
        by importance * recency as a quality proxy.

        Returns:
            List of (parent_id, MemoryItem, quality_score) tuples
        """
        # Build filter with text match
        keyword_filters = dict(filters) if filters else {}
        keyword_filters["__text_match"] = query

        all_results: list[SearchResult] = []
        for memory_type in memory_types:
            scroll_results, _ = await self.vector_store.scroll(
                collection=memory_type.value,
                limit=limit,
                filter_conditions=keyword_filters,
            )
            all_results.extend(scroll_results)

        # Deduplicate by parent_id
        best_by_parent: dict[str, SearchResult] = {}
        for sr in all_results:
            parent_id = sr.payload.get("parent_id", sr.id)
            if parent_id not in best_by_parent:
                best_by_parent[parent_id] = sr

        # Build results with quality ranking
        results = []
        for parent_id, sr in best_by_parent.items():
            memory = MemoryItem.from_payload(parent_id, sr.payload)
            # Quality score: importance * recency
            quality = memory.importance * _recency_factor(memory.created_at)
            results.append((parent_id, memory, quality))

        # Sort by quality descending
        results.sort(key=lambda x: x[2], reverse=True)
        return results

    async def _graph_strategy(
        self,
        seed_memory_id: str,
        memory_types: list[MemoryType],
        limit: int,
    ) -> list[tuple[str, MemoryItem]]:
        """Graph neighbor traversal strategy.

        Finds memories connected to the seed via knowledge graph relations.

        Returns:
            List of (parent_id, MemoryItem) tuples
        """
        if not self.graph_manager:
            return []

        neighbors = await self.graph_manager.get_neighbors(
            memory_id=seed_memory_id,
            depth=2,
            include_content=False,
        )

        # Fetch memory content for each neighbor from Qdrant
        results = []
        type_values = {mt.value for mt in memory_types}

        for neighbor in neighbors[:limit]:
            mid = neighbor["memory_id"]
            # Try each collection to find the memory
            for collection in type_values:
                found = await self.vector_store.get(
                    collection=collection,
                    ids=[mid],
                )
                if found:
                    memory = MemoryItem.from_payload(mid, found[0].payload)
                    results.append((mid, memory))
                    break

        return results

    def _rrf_fuse(
        self,
        semantic_results: list[tuple[str, MemoryItem, float]],
        keyword_results: list[tuple[str, MemoryItem, float]],
        graph_results: list[tuple[str, MemoryItem]],
    ) -> list[RecallResult]:
        """Fuse results from multiple strategies using Reciprocal Rank Fusion.

        RRF score: score(d) = Σ weight_i / (k + rank_i)

        Args:
            semantic_results: (parent_id, memory, score) from vector search
            keyword_results: (parent_id, memory, quality) from keyword search
            graph_results: (parent_id, memory) from graph traversal

        Returns:
            Fused and sorted RecallResults
        """
        # Accumulate RRF scores per parent_id
        rrf_scores: dict[str, float] = {}
        memories: dict[str, MemoryItem] = {}
        original_scores: dict[str, float] = {}

        # Semantic contributions
        for rank, (pid, memory, score) in enumerate(semantic_results, 1):
            rrf_scores[pid] = rrf_scores.get(pid, 0) + _rrf_score(rank, self.semantic_weight)
            memories[pid] = memory
            original_scores[pid] = score

        # Keyword contributions
        for rank, (pid, memory, _quality) in enumerate(keyword_results, 1):
            rrf_scores[pid] = rrf_scores.get(pid, 0) + _rrf_score(rank, self.keyword_weight)
            if pid not in memories:
                memories[pid] = memory

        # Graph contributions
        for rank, (pid, memory) in enumerate(graph_results, 1):
            rrf_scores[pid] = rrf_scores.get(pid, 0) + _rrf_score(rank, self.graph_weight)
            if pid not in memories:
                memories[pid] = memory

        # Build sorted results
        sorted_pids = sorted(rrf_scores.keys(), key=lambda p: rrf_scores[p], reverse=True)

        results = []
        for pid in sorted_pids:
            # Use original semantic score if available, otherwise RRF score normalized
            score = original_scores.get(pid, rrf_scores[pid])
            results.append(
                RecallResult(
                    memory=memories[pid],
                    score=score,
                )
            )

        return results
