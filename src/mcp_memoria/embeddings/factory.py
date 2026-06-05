"""Inference backend factory and router.

Builds the embedding/LLM client(s) from settings, supporting independent
selection of the embedding backend and the chat (LLM) backend. When both
capabilities use the same backend a single client is returned; when they
differ, a :class:`CompositeInference` routes ``embed*`` to the embedding
backend and ``generate`` to the LLM backend, preserving the public surface
that the rest of the codebase expects from ``OllamaEmbedder``.
"""

import logging
from typing import TYPE_CHECKING, Any

from mcp_memoria.embeddings.ollama_client import OllamaEmbedder
from mcp_memoria.embeddings.openai_client import MLXEmbedder

if TYPE_CHECKING:
    from mcp_memoria.config.settings import Settings
    from mcp_memoria.embeddings.embedding_cache import EmbeddingCache
    from mcp_memoria.embeddings.ollama_client import EmbeddingResult

logger = logging.getLogger(__name__)


def _make_backend(backend: str, settings: "Settings", cache: "EmbeddingCache | None") -> Any:
    """Construct a single backend instance configured for its own models."""
    if backend == "mlx":
        return MLXEmbedder(
            host=settings.mlx_host,
            model=settings.mlx_embedding_model,
            cache=cache,
            llm_model=settings.mlx_llm_model,
            api_key=settings.mlx_api_key,
            dimensions=settings.mlx_embedding_dimensions,
        )
    if backend == "ollama":
        return OllamaEmbedder(
            host=settings.ollama_host,
            model=settings.embedding_model,
            cache=cache,
            llm_model=settings.llm_model,
        )
    raise ValueError(f"Unknown inference backend: {backend!r}")


class CompositeInference:
    """Routes embeddings to one backend and chat generation to another.

    Delegates the embedder-shaped surface (embed/embed_batch/check_connection/
    ensure_model/dimensions/model/host) to the embedding backend, and
    ``generate``/``llm_model`` to the LLM backend.
    """

    def __init__(self, embed_backend: Any, llm_backend: Any):
        self._embed = embed_backend
        self._llm = llm_backend

    # --- embedding surface -> embedding backend ---
    @property
    def model(self) -> str:
        return self._embed.model

    @property
    def host(self) -> str:
        return self._embed.host

    @property
    def dimensions(self) -> int:
        return self._embed.dimensions

    @property
    def config(self) -> dict:
        return self._embed.config

    async def embed(self, *args, **kwargs) -> "EmbeddingResult":
        return await self._embed.embed(*args, **kwargs)

    async def embed_batch(self, *args, **kwargs) -> "list[EmbeddingResult]":
        return await self._embed.embed_batch(*args, **kwargs)

    async def check_connection(self) -> bool:
        return await self._embed.check_connection()

    async def ensure_model(self) -> bool:
        return await self._embed.ensure_model()

    # --- chat surface -> llm backend ---
    @property
    def llm_model(self) -> str:
        return self._llm.llm_model

    async def generate(self, *args, **kwargs) -> str:
        return await self._llm.generate(*args, **kwargs)

    def get_model_info(self) -> dict:
        return {
            "embedding": self._embed.get_model_info(),
            "llm": self._llm.get_model_info(),
        }


def build_embedder(settings: "Settings", cache: "EmbeddingCache | None") -> Any:
    """Build the inference client from settings.

    Returns a single backend when embedding and LLM share it, otherwise a
    :class:`CompositeInference` routing each capability to its backend.
    """
    embed_backend = _make_backend(settings.embedding_backend, settings, cache)

    if settings.llm_backend == settings.embedding_backend:
        logger.info("Inference backend: %s (embeddings + chat)", settings.embedding_backend)
        return embed_backend

    # Different backends: build the LLM backend (no embedding cache needed) and route.
    llm_backend = _make_backend(settings.llm_backend, settings, cache=None)
    logger.info(
        "Inference backends: embeddings=%s, chat=%s",
        settings.embedding_backend,
        settings.llm_backend,
    )
    return CompositeInference(embed_backend, llm_backend)
