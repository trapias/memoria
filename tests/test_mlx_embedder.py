"""Tests for the MLX / OpenAI-compatible embedder backend.

These tests mock httpx so they run without a live omlx/mlx_lm.server.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from mcp_memoria.embeddings.openai_client import MLXEmbedder


def _resp(payload: dict) -> MagicMock:
    r = MagicMock()
    r.raise_for_status = MagicMock()
    r.json = MagicMock(return_value=payload)
    return r


@pytest.fixture
def embedder():
    emb = MLXEmbedder(
        host="http://127.0.0.1:8000/v1",
        model="multilingual-e5-base-mlx",
        api_key="testkey",
        llm_model="mlx-community--Llama-3.2-3B-Instruct-4bit",
        dimensions=768,
        enable_rate_limiting=False,
    )
    emb._client = MagicMock()
    emb._client.post = AsyncMock()
    emb._client.get = AsyncMock()
    return emb


class TestMLXEmbedder:
    def test_initialization(self, embedder):
        assert embedder.model == "multilingual-e5-base-mlx"
        assert embedder.dimensions == 768
        assert embedder.host == "http://127.0.0.1:8000/v1"

    def test_e5_prefixes(self, embedder):
        assert embedder._apply_prefix("x", "query") == "query: x"
        assert embedder._apply_prefix("x", "document") == "passage: x"

    @pytest.mark.asyncio
    async def test_embed(self, embedder):
        embedder._client.post.return_value = _resp(
            {"data": [{"index": 0, "embedding": [0.1] * 768}]}
        )
        result = await embedder.embed("ciao", text_type="query", use_cache=False)
        assert result.dimensions == 768
        assert result.cached is False
        # endpoint + prefixed input
        args, kwargs = embedder._client.post.call_args
        assert args[0] == "/embeddings"
        assert kwargs["json"]["input"] == ["query: ciao"]

    @pytest.mark.asyncio
    async def test_embed_batch_preserves_order(self, embedder):
        # Server returns out of order; client must re-sort by index
        embedder._client.post.return_value = _resp(
            {
                "data": [
                    {"index": 1, "embedding": [0.2] * 768},
                    {"index": 0, "embedding": [0.1] * 768},
                ]
            }
        )
        results = await embedder.embed_batch(["a", "b"], use_cache=False)
        assert len(results) == 2
        assert results[0].embedding[0] == 0.1
        assert results[1].embedding[0] == 0.2

    @pytest.mark.asyncio
    async def test_check_connection(self, embedder):
        embedder._client.get.return_value = _resp({"data": []})
        assert await embedder.check_connection() is True

    @pytest.mark.asyncio
    async def test_ensure_model_present(self, embedder):
        embedder._client.get.return_value = _resp(
            {"data": [{"id": "multilingual-e5-base-mlx"}]}
        )
        assert await embedder.ensure_model() is True

    @pytest.mark.asyncio
    async def test_ensure_model_absent(self, embedder):
        embedder._client.get.return_value = _resp({"data": [{"id": "other"}]})
        assert await embedder.ensure_model() is False

    @pytest.mark.asyncio
    async def test_generate(self, embedder):
        embedder._client.post.return_value = _resp(
            {"choices": [{"message": {"content": "CIAO"}}]}
        )
        out = await embedder.generate("say ciao", system="be terse", temperature=0.0)
        assert out == "CIAO"
        args, kwargs = embedder._client.post.call_args
        assert args[0] == "/chat/completions"
        assert kwargs["json"]["messages"][0]["role"] == "system"
