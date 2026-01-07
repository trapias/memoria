"""Text chunking utilities for processing documents."""

import re
from dataclasses import dataclass, field
from typing import Iterator

from pydantic import BaseModel


@dataclass
class TextChunk:
    """Represents a chunk of text with metadata."""

    text: str
    start_idx: int
    end_idx: int
    chunk_index: int = 0
    metadata: dict = field(default_factory=dict)

    @property
    def length(self) -> int:
        """Get the length of the chunk text."""
        return len(self.text)


class ChunkingConfig(BaseModel):
    """Configuration for text chunking."""

    chunk_size: int = 500
    chunk_overlap: int = 50
    separators: list[str] = ["\n\n", "\n", ". ", "! ", "? ", "; ", ", ", " "]
    min_chunk_size: int = 50
    preserve_sentences: bool = True


class TextChunker:
    """Intelligent text chunker with configurable strategies."""

    def __init__(self, config: ChunkingConfig | None = None):
        """Initialize the chunker.

        Args:
            config: Chunking configuration
        """
        self.config = config or ChunkingConfig()

    def chunk(self, text: str, metadata: dict | None = None) -> list[TextChunk]:
        """Split text into chunks.

        Args:
            text: Text to split
            metadata: Optional metadata to attach to all chunks

        Returns:
            List of TextChunk objects
        """
        if not text or not text.strip():
            return []

        text = self._normalize_whitespace(text)
        chunks = list(self._recursive_chunk(text, metadata or {}))

        # Assign chunk indices
        for i, chunk in enumerate(chunks):
            chunk.chunk_index = i

        return chunks

    def _normalize_whitespace(self, text: str) -> str:
        """Normalize whitespace in text.

        Args:
            text: Input text

        Returns:
            Text with normalized whitespace
        """
        # Replace multiple spaces with single space
        text = re.sub(r" +", " ", text)
        # Replace multiple newlines with double newline
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _recursive_chunk(
        self,
        text: str,
        metadata: dict,
        start_offset: int = 0,
    ) -> Iterator[TextChunk]:
        """Recursively split text using separators.

        Args:
            text: Text to split
            metadata: Metadata for chunks
            start_offset: Starting offset for indices

        Yields:
            TextChunk objects
        """
        if len(text) <= self.config.chunk_size:
            if len(text) >= self.config.min_chunk_size:
                yield TextChunk(
                    text=text.strip(),
                    start_idx=start_offset,
                    end_idx=start_offset + len(text),
                    metadata=metadata.copy(),
                )
            return

        # Try each separator
        for separator in self.config.separators:
            if separator in text:
                chunks = self._split_by_separator(text, separator, metadata, start_offset)
                if chunks:
                    yield from chunks
                    return

        # Fallback: hard split at chunk_size
        yield from self._hard_split(text, metadata, start_offset)

    def _split_by_separator(
        self,
        text: str,
        separator: str,
        metadata: dict,
        start_offset: int,
    ) -> list[TextChunk] | None:
        """Split text by a separator, merging small pieces.

        Args:
            text: Text to split
            separator: Separator to use
            metadata: Metadata for chunks
            start_offset: Starting offset

        Returns:
            List of chunks or None if split is not effective
        """
        parts = text.split(separator)
        if len(parts) <= 1:
            return None

        chunks = []
        current_chunk = ""
        current_start = start_offset

        for i, part in enumerate(parts):
            # Add separator back (except for last part)
            part_with_sep = part + separator if i < len(parts) - 1 else part

            if not current_chunk:
                current_chunk = part_with_sep
            elif len(current_chunk) + len(part_with_sep) <= self.config.chunk_size:
                current_chunk += part_with_sep
            else:
                # Save current chunk
                if len(current_chunk.strip()) >= self.config.min_chunk_size:
                    chunks.append(
                        TextChunk(
                            text=current_chunk.strip(),
                            start_idx=current_start,
                            end_idx=current_start + len(current_chunk),
                            metadata=metadata.copy(),
                        )
                    )

                # Start new chunk with overlap
                overlap_text = self._get_overlap(current_chunk)
                current_start = current_start + len(current_chunk) - len(overlap_text)
                current_chunk = overlap_text + part_with_sep

        # Don't forget the last chunk
        if current_chunk.strip() and len(current_chunk.strip()) >= self.config.min_chunk_size:
            chunks.append(
                TextChunk(
                    text=current_chunk.strip(),
                    start_idx=current_start,
                    end_idx=current_start + len(current_chunk),
                    metadata=metadata.copy(),
                )
            )

        return chunks if chunks else None

    def _hard_split(
        self,
        text: str,
        metadata: dict,
        start_offset: int,
    ) -> Iterator[TextChunk]:
        """Hard split text at chunk_size boundaries.

        Args:
            text: Text to split
            metadata: Metadata for chunks
            start_offset: Starting offset

        Yields:
            TextChunk objects
        """
        start = 0
        while start < len(text):
            end = min(start + self.config.chunk_size, len(text))
            chunk_text = text[start:end]

            if len(chunk_text.strip()) >= self.config.min_chunk_size:
                yield TextChunk(
                    text=chunk_text.strip(),
                    start_idx=start_offset + start,
                    end_idx=start_offset + end,
                    metadata=metadata.copy(),
                )

            start = end - self.config.chunk_overlap

    def _get_overlap(self, text: str) -> str:
        """Get the overlap portion from the end of text.

        Args:
            text: Source text

        Returns:
            Overlap text
        """
        if len(text) <= self.config.chunk_overlap:
            return ""

        overlap = text[-self.config.chunk_overlap:]

        # Try to start at a word boundary
        if self.config.preserve_sentences:
            space_idx = overlap.find(" ")
            if space_idx > 0:
                overlap = overlap[space_idx + 1:]

        return overlap

    def estimate_chunks(self, text: str) -> int:
        """Estimate the number of chunks for a text.

        Args:
            text: Text to estimate

        Returns:
            Estimated number of chunks
        """
        if not text:
            return 0

        text_len = len(text)
        if text_len <= self.config.chunk_size:
            return 1

        effective_chunk_size = self.config.chunk_size - self.config.chunk_overlap
        return max(1, (text_len + effective_chunk_size - 1) // effective_chunk_size)


def chunk_for_embedding(
    text: str,
    max_context: int = 512,
    overlap: int = 50,
) -> list[TextChunk]:
    """Convenience function to chunk text for embedding.

    Args:
        text: Text to chunk
        max_context: Maximum context size for embedding model
        overlap: Overlap between chunks

    Returns:
        List of TextChunk objects
    """
    # Leave some room for prefixes
    chunk_size = int(max_context * 0.9 * 4)  # ~4 chars per token, 90% of context

    config = ChunkingConfig(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
    )
    chunker = TextChunker(config)
    return chunker.chunk(text)
