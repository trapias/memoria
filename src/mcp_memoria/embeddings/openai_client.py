"""OpenAI-compatible client for embeddings and chat (MLX / omlx backend).

This backend talks to any OpenAI-compatible local inference server — primarily
`omlx` / `mlx_lm.server` running on Apple Silicon — using plain HTTP. It does
NOT import the `mlx` libraries, so the package stays importable on Linux/Windows;
the backend is only exercised when explicitly selected via settings.

It mirrors the public surface of :class:`OllamaEmbedder` so it can be used
interchangeably (embed / embed_batch / generate / check_connection /
ensure_model / dimensions / get_model_info).
"""

import logging

import httpx

from mcp_memoria.core.rate_limiter import (
    OLLAMA_CIRCUIT_CONFIG,
    OLLAMA_RATE_CONFIG,
    CircuitBreaker,
    RateLimiter,
)
from mcp_memoria.embeddings.embedding_cache import EmbeddingCache
from mcp_memoria.embeddings.ollama_client import MODEL_CONFIGS, EmbeddingResult

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG = {
    "dimensions": 768,
    "max_context": 512,
    "query_prefix": "",
    "document_prefix": "",
}


class MLXEmbedder:
    """OpenAI-compatible embedding + chat client (MLX/omlx local server).

    Drop-in alternative to :class:`OllamaEmbedder`, talking to an
    OpenAI-compatible HTTP API (``/v1/embeddings`` and ``/v1/chat/completions``).
    """

    def __init__(
        self,
        host: str = "http://127.0.0.1:8000/v1",
        model: str = "multilingual-e5-base-mlx",
        cache: EmbeddingCache | None = None,
        timeout: float = 120.0,
        enable_rate_limiting: bool = True,
        llm_model: str = "mlx-community--Llama-3.2-3B-Instruct-4bit",
        api_key: str = "",
        dimensions: int | None = None,
    ):
        """Initialize the OpenAI-compatible embedder.

        Args:
            host: Base URL of the OpenAI-compatible server (must end with /v1).
            model: Embedding model id as exposed by the server.
            cache: Optional embedding cache.
            timeout: Request timeout in seconds (MLX cold-loads can be slow).
            enable_rate_limiting: Enable rate limiting and circuit breaker.
            llm_model: Default chat model for text generation (reflect/observe).
            api_key: Bearer token for the server (omlx requires one).
            dimensions: Override embedding dimensions (else taken from MODEL_CONFIGS).
        """
        self.host = host.rstrip("/")
        self.model = model
        self.cache = cache
        self.timeout = timeout
        self.llm_model = llm_model
        self.api_key = api_key

        # Resolve model config (prefixes + dimensions); allow explicit override
        base_config = MODEL_CONFIGS.get(model, _DEFAULT_CONFIG)
        self.config = dict(base_config)
        if dimensions is not None:
            self.config["dimensions"] = dimensions

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._client = httpx.AsyncClient(
            base_url=self.host,
            timeout=httpx.Timeout(timeout),
            headers=headers,
        )

        self._rate_limiter = RateLimiter(OLLAMA_RATE_CONFIG) if enable_rate_limiting else None
        self._circuit_breaker = (
            CircuitBreaker("mlx", OLLAMA_CIRCUIT_CONFIG) if enable_rate_limiting else None
        )

    @property
    def dimensions(self) -> int:
        """Get embedding dimensions for the current model."""
        return self.config["dimensions"]

    def _apply_prefix(self, text: str, text_type: str = "document") -> str:
        """Apply model-specific prefix (e.g. e5 'query:' / 'passage:')."""
        prefix = self.config.get(f"{text_type}_prefix", "")
        return f"{prefix}{text}"

    async def _embed_raw(self, inputs: list[str]) -> list[list[float]]:
        """POST a batch of (already-prefixed) texts to /embeddings."""
        if self._rate_limiter:
            await self._rate_limiter.acquire()

        async def _do():
            resp = await self._client.post(
                "/embeddings", json={"model": self.model, "input": inputs}
            )
            resp.raise_for_status()
            data = resp.json()["data"]
            # Preserve request order regardless of server ordering
            data.sort(key=lambda d: d.get("index", 0))
            return [d["embedding"] for d in data]

        if self._circuit_breaker:
            return await self._circuit_breaker.call(_do)
        return await _do()

    async def embed(
        self,
        text: str,
        text_type: str = "document",
        use_cache: bool = True,
    ) -> EmbeddingResult:
        """Generate an embedding for a single text."""
        prefixed = self._apply_prefix(text, text_type)

        if use_cache and self.cache:
            cached = await self.cache.get(prefixed, self.model)
            if cached is not None:
                logger.debug(f"Cache hit for embedding: {text[:50]}...")
                return EmbeddingResult(
                    embedding=cached, model=self.model, dimensions=len(cached), cached=True
                )

        try:
            embedding = (await self._embed_raw([prefixed]))[0]
        except Exception as e:
            logger.error(f"Error generating embedding (mlx): {e}")
            raise RuntimeError(f"Failed to generate embedding: {e}") from e

        if use_cache and self.cache:
            await self.cache.set(prefixed, self.model, embedding)

        return EmbeddingResult(
            embedding=embedding, model=self.model, dimensions=len(embedding), cached=False
        )

    async def embed_batch(
        self,
        texts: list[str],
        text_type: str = "document",
        use_cache: bool = True,
    ) -> list[EmbeddingResult]:
        """Generate embeddings for multiple texts in a single batched request.

        Cache hits are served locally; only the misses are sent to the server,
        then folded back into their original positions.
        """
        results: list[EmbeddingResult | None] = [None] * len(texts)
        misses: list[str] = []
        miss_idx: list[int] = []

        for i, text in enumerate(texts):
            prefixed = self._apply_prefix(text, text_type)
            if use_cache and self.cache:
                cached = await self.cache.get(prefixed, self.model)
                if cached is not None:
                    results[i] = EmbeddingResult(
                        embedding=cached, model=self.model, dimensions=len(cached), cached=True
                    )
                    continue
            misses.append(prefixed)
            miss_idx.append(i)

        if misses:
            try:
                embeddings = await self._embed_raw(misses)
            except Exception as e:
                logger.error(f"Error generating batch embeddings (mlx): {e}")
                raise RuntimeError(f"Failed to generate embeddings: {e}") from e
            for j, embedding in enumerate(embeddings):
                i = miss_idx[j]
                results[i] = EmbeddingResult(
                    embedding=embedding, model=self.model, dimensions=len(embedding), cached=False
                )
                if use_cache and self.cache:
                    await self.cache.set(misses[j], self.model, embedding)

        return [r for r in results if r is not None]

    async def check_connection(self) -> bool:
        """Check if the OpenAI-compatible server is reachable."""
        try:
            resp = await self._client.get("/models")
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Failed to connect to MLX server at {self.host}: {e}")
            return False

    async def ensure_model(self) -> bool:
        """Verify the embedding model is available (no auto-pull for MLX)."""
        try:
            resp = await self._client.get("/models")
            resp.raise_for_status()
            ids = {m["id"] for m in resp.json().get("data", [])}
            if self.model in ids:
                logger.info(f"MLX model {self.model} is available")
                return True
            logger.error(
                f"MLX model '{self.model}' not found on server. Available: {sorted(ids)}"
            )
            return False
        except Exception as e:
            logger.error(f"Failed to verify MLX model {self.model}: {e}")
            return False

    async def generate(
        self,
        prompt: str,
        model: str | None = None,
        system: str | None = None,
        temperature: float = 0.3,
    ) -> str:
        """Generate a chat completion via /chat/completions."""
        chat_model = model or self.llm_model

        if self._rate_limiter:
            await self._rate_limiter.acquire()

        async def _do():
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            resp = await self._client.post(
                "/chat/completions",
                json={"model": chat_model, "messages": messages, "temperature": temperature},
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]

        try:
            if self._circuit_breaker:
                return await self._circuit_breaker.call(_do)
            return await _do()
        except Exception as e:
            logger.error(f"Error generating text (mlx): {e}")
            raise RuntimeError(f"Failed to generate text: {e}") from e

    def get_model_info(self) -> dict:
        """Get information about the current model configuration."""
        return {
            "backend": "mlx",
            "model": self.model,
            "llm_model": self.llm_model,
            "host": self.host,
            **self.config,
        }
