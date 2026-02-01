"""Tests for OllamaEmbedder."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp_memoria.embeddings.ollama_client import (
    EmbeddingResult,
    MODEL_CONFIGS,
    OllamaEmbedder,
)
from mcp_memoria.core.rate_limiter import CircuitOpenError, RateLimitExceeded


@pytest.fixture
def mock_ollama_client():
    """Create a mock Ollama client."""
    client = MagicMock()
    client.embeddings.return_value = {"embedding": [0.1] * 768}
    client.list.return_value = {"models": [{"name": "nomic-embed-text:latest"}]}
    client.pull = MagicMock()
    return client


@pytest.fixture
def embedder(mock_ollama_client):
    """Create an embedder with mocked client."""
    with patch("mcp_memoria.embeddings.ollama_client.ollama.Client", return_value=mock_ollama_client):
        emb = OllamaEmbedder(
            host="http://localhost:11434",
            model="nomic-embed-text",
            enable_rate_limiting=False,
        )
        emb._client = mock_ollama_client
        return emb


class TestOllamaEmbedder:
    """Tests for OllamaEmbedder class."""

    def test_initialization(self, embedder):
        """Test embedder initialization."""
        assert embedder.model == "nomic-embed-text"
        assert embedder.host == "http://localhost:11434"
        assert embedder.dimensions == 768

    def test_model_config(self, embedder):
        """Test model configuration loading."""
        assert embedder.config == MODEL_CONFIGS["nomic-embed-text"]
        assert "query_prefix" in embedder.config
        assert "document_prefix" in embedder.config

    def test_apply_prefix_query(self, embedder):
        """Test prefix application for queries."""
        result = embedder._apply_prefix("test query", text_type="query")
        assert result.startswith("search_query: ")

    def test_apply_prefix_document(self, embedder):
        """Test prefix application for documents."""
        result = embedder._apply_prefix("test document", text_type="document")
        assert result.startswith("search_document: ")


class TestEmbed:
    """Tests for embed method."""

    @pytest.mark.asyncio
    async def test_embed_returns_result(self, embedder):
        """Test that embed returns proper result."""
        result = await embedder.embed("test text", text_type="document")

        assert isinstance(result, EmbeddingResult)
        assert len(result.embedding) == 768
        assert result.model == "nomic-embed-text"
        assert result.cached is False

    @pytest.mark.asyncio
    async def test_embed_with_cache_hit(self, embedder, mock_ollama_client):
        """Test embedding with cache hit."""
        # Create mock cache
        mock_cache = AsyncMock()
        mock_cache.get.return_value = [0.2] * 768
        embedder.cache = mock_cache

        result = await embedder.embed("test text", use_cache=True)

        assert result.cached is True
        assert result.embedding == [0.2] * 768
        mock_ollama_client.embeddings.assert_not_called()

    @pytest.mark.asyncio
    async def test_embed_with_cache_miss(self, embedder, mock_ollama_client):
        """Test embedding with cache miss."""
        mock_cache = AsyncMock()
        mock_cache.get.return_value = None
        embedder.cache = mock_cache

        result = await embedder.embed("test text", use_cache=True)

        assert result.cached is False
        mock_ollama_client.embeddings.assert_called_once()
        mock_cache.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_embed_error_handling(self, embedder, mock_ollama_client):
        """Test error handling in embed."""
        mock_ollama_client.embeddings.side_effect = Exception("Connection failed")

        with pytest.raises(RuntimeError, match="Failed to generate embedding"):
            await embedder.embed("test text")


class TestEmbedBatch:
    """Tests for embed_batch method."""

    @pytest.mark.asyncio
    async def test_embed_batch_multiple(self, embedder):
        """Test batch embedding of multiple texts."""
        texts = ["text1", "text2", "text3"]
        results = await embedder.embed_batch(texts)

        assert len(results) == 3
        for result in results:
            assert isinstance(result, EmbeddingResult)
            assert len(result.embedding) == 768


class TestConnection:
    """Tests for connection methods."""

    @pytest.mark.asyncio
    async def test_check_connection_success(self, embedder):
        """Test successful connection check."""
        result = await embedder.check_connection()
        assert result is True

    @pytest.mark.asyncio
    async def test_check_connection_failure(self, embedder, mock_ollama_client):
        """Test failed connection check."""
        mock_ollama_client.list.side_effect = Exception("Connection refused")
        result = await embedder.check_connection()
        assert result is False

    @pytest.mark.asyncio
    async def test_ensure_model_available(self, embedder):
        """Test model availability check when model exists."""
        result = await embedder.ensure_model()
        assert result is True

    @pytest.mark.asyncio
    async def test_ensure_model_pulls_if_missing(self, embedder, mock_ollama_client):
        """Test that missing model is pulled."""
        mock_ollama_client.list.return_value = {"models": []}

        result = await embedder.ensure_model()

        assert result is True
        mock_ollama_client.pull.assert_called_once_with("nomic-embed-text")


class TestRateLimiting:
    """Tests for rate limiting integration."""

    @pytest.mark.asyncio
    async def test_rate_limiter_enabled(self, mock_ollama_client):
        """Test that rate limiter is enabled by default."""
        with patch("mcp_memoria.embeddings.ollama_client.ollama.Client", return_value=mock_ollama_client):
            emb = OllamaEmbedder(enable_rate_limiting=True)
            emb._client = mock_ollama_client

        assert emb._rate_limiter is not None
        assert emb._circuit_breaker is not None

    @pytest.mark.asyncio
    async def test_rate_limiter_disabled(self, mock_ollama_client):
        """Test that rate limiter can be disabled."""
        with patch("mcp_memoria.embeddings.ollama_client.ollama.Client", return_value=mock_ollama_client):
            emb = OllamaEmbedder(enable_rate_limiting=False)

        assert emb._rate_limiter is None
        assert emb._circuit_breaker is None


class TestGetModelInfo:
    """Tests for get_model_info method."""

    def test_get_model_info(self, embedder):
        """Test model info retrieval."""
        info = embedder.get_model_info()

        assert info["model"] == "nomic-embed-text"
        assert info["host"] == "http://localhost:11434"
        assert "dimensions" in info
        assert "query_prefix" in info
