"""Embedding generation module."""

from mcp_memoria.embeddings.ollama_client import OllamaEmbedder
from mcp_memoria.embeddings.openai_client import MLXEmbedder
from mcp_memoria.embeddings.factory import CompositeInference, build_embedder
from mcp_memoria.embeddings.embedding_cache import EmbeddingCache
from mcp_memoria.embeddings.chunking import TextChunker, TextChunk

__all__ = [
    "OllamaEmbedder",
    "MLXEmbedder",
    "CompositeInference",
    "build_embedder",
    "EmbeddingCache",
    "TextChunker",
    "TextChunk",
]
