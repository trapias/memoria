"""Tests for text chunking."""

import pytest

from mcp_memoria.embeddings.chunking import (
    TextChunk,
    TextChunker,
    ChunkingConfig,
    chunk_for_embedding,
)


class TestTextChunk:
    """Tests for TextChunk dataclass."""

    def test_chunk_creation(self):
        """Test creating a text chunk."""
        chunk = TextChunk(
            text="Hello world",
            start_idx=0,
            end_idx=11,
            chunk_index=0,
        )
        assert chunk.text == "Hello world"
        assert chunk.length == 11


class TestTextChunker:
    """Tests for TextChunker."""

    def test_short_text_single_chunk(self):
        """Test that short text returns a single chunk."""
        chunker = TextChunker(ChunkingConfig(chunk_size=500, min_chunk_size=10))
        chunks = chunker.chunk("This is a short text.")

        assert len(chunks) == 1
        assert chunks[0].text == "This is a short text."

    def test_long_text_multiple_chunks(self):
        """Test that long text is split into multiple chunks."""
        config = ChunkingConfig(chunk_size=50, chunk_overlap=10, min_chunk_size=10)
        chunker = TextChunker(config)

        long_text = "This is a longer text. " * 10
        chunks = chunker.chunk(long_text)

        assert len(chunks) > 1

    def test_chunk_indices(self):
        """Test that chunk indices are sequential."""
        config = ChunkingConfig(chunk_size=50, min_chunk_size=10)
        chunker = TextChunker(config)

        text = "First sentence. Second sentence. Third sentence. Fourth sentence."
        chunks = chunker.chunk(text)

        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i

    def test_empty_text(self):
        """Test empty text returns no chunks."""
        chunker = TextChunker()
        chunks = chunker.chunk("")

        assert len(chunks) == 0

    def test_whitespace_normalization(self):
        """Test that whitespace is normalized."""
        chunker = TextChunker(ChunkingConfig(min_chunk_size=10))
        text = "Text   with    extra    spaces"
        chunks = chunker.chunk(text)

        assert "  " not in chunks[0].text

    def test_estimate_chunks(self):
        """Test chunk estimation."""
        config = ChunkingConfig(chunk_size=100, chunk_overlap=10)
        chunker = TextChunker(config)

        short_text = "Short"
        long_text = "x" * 500

        assert chunker.estimate_chunks(short_text) == 1
        assert chunker.estimate_chunks(long_text) > 1


class TestChunkForEmbedding:
    """Tests for convenience chunking function."""

    def test_chunk_for_embedding(self):
        """Test chunking for embedding with context limit."""
        text = "Sample text. " * 100
        chunks = chunk_for_embedding(text, max_context=512)

        # All chunks should be under the context limit
        for chunk in chunks:
            # Rough check - actual token count may vary
            assert len(chunk.text) < 512 * 4  # ~4 chars per token
