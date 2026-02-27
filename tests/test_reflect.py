"""Tests for the Reflect tool."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from mcp_memoria.core.memory_types import MemoryItem, MemoryType, RecallResult
from mcp_memoria.core.reflect import Reflector, _DEPTH_LIMITS, _STYLE_INSTRUCTIONS


class TestReflector:
    """Test Reflector class."""

    def _make_result(self, mid: str, content: str, score: float = 0.8) -> RecallResult:
        return RecallResult(
            memory=MemoryItem(
                id=mid,
                content=content,
                memory_type=MemoryType.SEMANTIC,
                importance=0.7,
                tags=["test"],
                created_at=datetime(2026, 1, 15),
            ),
            score=score,
        )

    def test_depth_limits(self):
        assert _DEPTH_LIMITS["quick"] == 5
        assert _DEPTH_LIMITS["thorough"] == 15
        assert _DEPTH_LIMITS["deep"] == 30

    def test_all_styles_have_instructions(self):
        for style in ["synthesis", "timeline", "comparison", "analysis"]:
            assert style in _STYLE_INSTRUCTIONS

    def test_format_memories(self):
        reflector = Reflector.__new__(Reflector)
        results = [
            self._make_result("m1", "Python is great", 0.9),
            self._make_result("m2", "Rust is fast", 0.7),
        ]
        formatted = reflector._format_memories(results)
        assert "[1]" in formatted
        assert "[2]" in formatted
        assert "Python is great" in formatted
        assert "Rust is fast" in formatted
        assert "semantic" in formatted
        assert "2026-01-15" in formatted

    @pytest.mark.asyncio
    async def test_reflect_no_results(self):
        mm = AsyncMock()
        mm.recall = AsyncMock(return_value=[])
        embedder = AsyncMock()

        reflector = Reflector(memory_manager=mm, embedder=embedder)
        result = await reflector.reflect(query="test", style="synthesis")

        assert result["sources"] == 0
        assert "No relevant memories" in result["reflection"]

    @pytest.mark.asyncio
    async def test_reflect_calls_generate(self):
        results = [self._make_result("m1", "fact about Python")]
        mm = AsyncMock()
        mm.recall = AsyncMock(return_value=results)

        embedder = AsyncMock()
        embedder.generate = AsyncMock(return_value="Python is versatile.")

        reflector = Reflector(memory_manager=mm, embedder=embedder)
        result = await reflector.reflect(query="tell me about Python")

        assert result["sources"] == 1
        assert result["style"] == "synthesis"
        assert result["reflection"] == "Python is versatile."
        embedder.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_reflect_depth_controls_limit(self):
        mm = AsyncMock()
        mm.recall = AsyncMock(return_value=[])
        embedder = AsyncMock()

        reflector = Reflector(memory_manager=mm, embedder=embedder)

        await reflector.reflect(query="test", depth="quick")
        call_kwargs = mm.recall.call_args.kwargs
        assert call_kwargs["limit"] == 5

        await reflector.reflect(query="test", depth="deep")
        call_kwargs = mm.recall.call_args.kwargs
        assert call_kwargs["limit"] == 30

    @pytest.mark.asyncio
    async def test_reflect_uses_hybrid_recall(self):
        mm = AsyncMock()
        mm.recall = AsyncMock(return_value=[])
        embedder = AsyncMock()

        reflector = Reflector(memory_manager=mm, embedder=embedder)
        await reflector.reflect(query="test")

        call_kwargs = mm.recall.call_args.kwargs
        assert call_kwargs["hybrid"] is True

    @pytest.mark.asyncio
    async def test_reflect_handles_llm_error(self):
        results = [self._make_result("m1", "some fact")]
        mm = AsyncMock()
        mm.recall = AsyncMock(return_value=results)

        embedder = AsyncMock()
        embedder.generate = AsyncMock(side_effect=RuntimeError("LLM offline"))

        reflector = Reflector(memory_manager=mm, embedder=embedder)
        result = await reflector.reflect(query="test")

        assert "failed" in result["reflection"].lower()
        assert result["sources"] == 1
