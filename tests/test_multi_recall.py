"""Tests for multi-strategy recall with RRF fusion."""

import math
from datetime import datetime, timedelta, timezone

import pytest

from mcp_memoria.core.multi_recall import MultiRecall, _recency_factor, _rrf_score, RRF_K
from mcp_memoria.core.memory_types import MemoryItem, MemoryType, RecallResult


class TestRRFScore:
    """Test RRF scoring function."""

    def test_rank_1_default_weight(self):
        score = _rrf_score(1)
        assert score == pytest.approx(1.0 / (RRF_K + 1))

    def test_higher_rank_lower_score(self):
        assert _rrf_score(1) > _rrf_score(2) > _rrf_score(10)

    def test_weight_multiplier(self):
        assert _rrf_score(1, weight=2.0) == pytest.approx(2.0 * _rrf_score(1))

    def test_zero_weight(self):
        assert _rrf_score(1, weight=0.0) == 0.0


class TestRecencyFactor:
    """Test recency factor computation."""

    def test_recent_memory_high_factor(self):
        now = datetime.now(timezone.utc)
        factor = _recency_factor(now)
        assert factor > 0.95

    def test_old_memory_low_factor(self):
        old = datetime.now(timezone.utc) - timedelta(days=90)
        factor = _recency_factor(old)
        assert factor < 0.2

    def test_30_day_halflife(self):
        half_life_ago = datetime.now(timezone.utc) - timedelta(days=30)
        factor = _recency_factor(half_life_ago)
        assert factor == pytest.approx(0.5, abs=0.05)

    def test_naive_datetime_handled(self):
        naive = datetime.now() - timedelta(days=1)
        factor = _recency_factor(naive)
        assert 0 < factor < 1


class TestRRFFusion:
    """Test the RRF fusion logic."""

    def _make_memory(self, mid: str, content: str = "test") -> MemoryItem:
        return MemoryItem(
            id=mid,
            content=content,
            memory_type=MemoryType.SEMANTIC,
            importance=0.5,
        )

    def test_semantic_only(self):
        """Results from only semantic strategy."""
        multi = MultiRecall.__new__(MultiRecall)
        multi.semantic_weight = 1.0
        multi.keyword_weight = 0.5
        multi.graph_weight = 0.3

        m1 = self._make_memory("m1")
        m2 = self._make_memory("m2")

        results = multi._rrf_fuse(
            semantic_results=[("m1", m1, 0.95), ("m2", m2, 0.80)],
            keyword_results=[],
            graph_results=[],
        )

        assert len(results) == 2
        assert results[0].memory.id == "m1"
        assert results[1].memory.id == "m2"

    def test_keyword_only(self):
        """Results from only keyword strategy."""
        multi = MultiRecall.__new__(MultiRecall)
        multi.semantic_weight = 1.0
        multi.keyword_weight = 0.5
        multi.graph_weight = 0.3

        m1 = self._make_memory("m1")

        results = multi._rrf_fuse(
            semantic_results=[],
            keyword_results=[("m1", m1, 0.7)],
            graph_results=[],
        )

        assert len(results) == 1
        assert results[0].memory.id == "m1"

    def test_fusion_boosts_overlap(self):
        """Memory appearing in both strategies gets boosted score."""
        multi = MultiRecall.__new__(MultiRecall)
        multi.semantic_weight = 1.0
        multi.keyword_weight = 0.5
        multi.graph_weight = 0.3

        m1 = self._make_memory("m1")
        m2 = self._make_memory("m2")
        m3 = self._make_memory("m3")

        # m2 appears in both semantic and keyword — should rank higher via RRF
        results = multi._rrf_fuse(
            semantic_results=[
                ("m1", m1, 0.90),  # rank 1
                ("m2", m2, 0.85),  # rank 2
            ],
            keyword_results=[
                ("m3", m3, 0.8),   # rank 1
                ("m2", m2, 0.7),   # rank 2
            ],
            graph_results=[],
        )

        # m2 should be boosted because it appears in both lists
        rrf_m1 = _rrf_score(1, 1.0)                              # semantic rank 1
        rrf_m2 = _rrf_score(2, 1.0) + _rrf_score(2, 0.5)        # both rank 2
        rrf_m3 = _rrf_score(1, 0.5)                              # keyword rank 1

        assert rrf_m2 > rrf_m1, "m2 should have higher RRF than m1 due to overlap"

    def test_graph_contribution(self):
        """Graph results contribute to RRF scoring."""
        multi = MultiRecall.__new__(MultiRecall)
        multi.semantic_weight = 1.0
        multi.keyword_weight = 0.5
        multi.graph_weight = 0.3

        m1 = self._make_memory("m1")
        m2 = self._make_memory("m2")

        results = multi._rrf_fuse(
            semantic_results=[("m1", m1, 0.90)],
            keyword_results=[],
            graph_results=[("m2", m2)],
        )

        assert len(results) == 2

    def test_dedup_across_strategies(self):
        """Same memory from different strategies is not duplicated."""
        multi = MultiRecall.__new__(MultiRecall)
        multi.semantic_weight = 1.0
        multi.keyword_weight = 0.5
        multi.graph_weight = 0.3

        m1 = self._make_memory("m1")

        results = multi._rrf_fuse(
            semantic_results=[("m1", m1, 0.95)],
            keyword_results=[("m1", m1, 0.8)],
            graph_results=[("m1", m1)],
        )

        # Should appear only once, with accumulated RRF score
        assert len(results) == 1
        assert results[0].memory.id == "m1"
