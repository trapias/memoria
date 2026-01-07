"""Ollama client for generating embeddings."""

import logging
from typing import TYPE_CHECKING

import httpx
import ollama
from pydantic import BaseModel

if TYPE_CHECKING:
    from mcp_memoria.embeddings.embedding_cache import EmbeddingCache

logger = logging.getLogger(__name__)


# Model configurations with prefixes for optimal performance
MODEL_CONFIGS = {
    "nomic-embed-text": {
        "dimensions": 768,
        "max_context": 8192,
        "query_prefix": "search_query: ",
        "document_prefix": "search_document: ",
    },
    "mxbai-embed-large": {
        "dimensions": 1024,
        "max_context": 512,
        "query_prefix": "Represent this sentence for searching relevant passages: ",
        "document_prefix": "",
    },
    "all-minilm": {
        "dimensions": 384,
        "max_context": 256,
        "query_prefix": "",
        "document_prefix": "",
    },
    "bge-m3": {
        "dimensions": 1024,
        "max_context": 8192,
        "query_prefix": "",
        "document_prefix": "",
    },
    "bge-large": {
        "dimensions": 1024,
        "max_context": 512,
        "query_prefix": "Represent this query for retrieving relevant documents: ",
        "document_prefix": "",
    },
    "snowflake-arctic-embed": {
        "dimensions": 1024,
        "max_context": 512,
        "query_prefix": "",
        "document_prefix": "",
    },
}


class EmbeddingResult(BaseModel):
    """Result of an embedding operation."""

    embedding: list[float]
    model: str
    dimensions: int
    cached: bool = False


class OllamaEmbedder:
    """Client for generating embeddings using Ollama."""

    def __init__(
        self,
        host: str = "http://localhost:11434",
        model: str = "nomic-embed-text",
        cache: "EmbeddingCache | None" = None,
        timeout: float = 30.0,
    ):
        """Initialize the Ollama embedder.

        Args:
            host: Ollama server URL
            model: Model name for embeddings
            cache: Optional embedding cache
            timeout: Request timeout in seconds
        """
        self.host = host
        self.model = model
        self.cache = cache
        self.timeout = timeout

        # Get model config or use defaults
        self.config = MODEL_CONFIGS.get(
            model,
            {
                "dimensions": 768,
                "max_context": 512,
                "query_prefix": "",
                "document_prefix": "",
            },
        )

        # Configure ollama client
        self._client = ollama.Client(host=host, timeout=httpx.Timeout(timeout))

    @property
    def dimensions(self) -> int:
        """Get embedding dimensions for the current model."""
        return self.config["dimensions"]

    def _apply_prefix(self, text: str, text_type: str = "document") -> str:
        """Apply model-specific prefix to text.

        Args:
            text: Input text
            text_type: Either 'query' or 'document'

        Returns:
            Text with appropriate prefix
        """
        prefix_key = f"{text_type}_prefix"
        prefix = self.config.get(prefix_key, "")
        return f"{prefix}{text}"

    async def embed(
        self,
        text: str,
        text_type: str = "document",
        use_cache: bool = True,
    ) -> EmbeddingResult:
        """Generate embedding for a single text.

        Args:
            text: Text to embed
            text_type: Either 'query' or 'document' (affects prefix)
            use_cache: Whether to use cache

        Returns:
            EmbeddingResult with the embedding vector
        """
        # Apply prefix for optimal model performance
        prefixed_text = self._apply_prefix(text, text_type)

        # Check cache first
        if use_cache and self.cache:
            cached = await self.cache.get(prefixed_text, self.model)
            if cached is not None:
                logger.debug(f"Cache hit for embedding: {text[:50]}...")
                return EmbeddingResult(
                    embedding=cached,
                    model=self.model,
                    dimensions=len(cached),
                    cached=True,
                )

        # Generate embedding
        try:
            response = self._client.embeddings(model=self.model, prompt=prefixed_text)
            embedding = response["embedding"]

            # Store in cache
            if use_cache and self.cache:
                await self.cache.set(prefixed_text, self.model, embedding)

            logger.debug(f"Generated embedding for: {text[:50]}...")
            return EmbeddingResult(
                embedding=embedding,
                model=self.model,
                dimensions=len(embedding),
                cached=False,
            )

        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise RuntimeError(f"Failed to generate embedding: {e}") from e

    async def embed_batch(
        self,
        texts: list[str],
        text_type: str = "document",
        use_cache: bool = True,
    ) -> list[EmbeddingResult]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed
            text_type: Either 'query' or 'document'
            use_cache: Whether to use cache

        Returns:
            List of EmbeddingResults
        """
        results = []
        for text in texts:
            result = await self.embed(text, text_type=text_type, use_cache=use_cache)
            results.append(result)
        return results

    async def check_connection(self) -> bool:
        """Check if Ollama server is accessible.

        Returns:
            True if connection is successful
        """
        try:
            self._client.list()
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Ollama: {e}")
            return False

    async def ensure_model(self) -> bool:
        """Ensure the embedding model is available.

        Returns:
            True if model is available or was pulled successfully
        """
        try:
            # Check if model exists
            models = self._client.list()
            # Handle both dict and object responses from ollama library
            model_list = models.get("models", []) if isinstance(models, dict) else getattr(models, "models", [])
            model_names = []
            for m in model_list:
                name = m["name"] if isinstance(m, dict) else getattr(m, "name", "")
                model_names.append(name.split(":")[0])

            if self.model in model_names or f"{self.model}:latest" in model_names:
                logger.info(f"Model {self.model} is available")
                return True

            # Try to pull the model
            logger.info(f"Pulling model {self.model}...")
            self._client.pull(self.model)
            logger.info(f"Model {self.model} pulled successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to ensure model {self.model}: {e}")
            return False

    def get_model_info(self) -> dict:
        """Get information about the current model.

        Returns:
            Dictionary with model configuration
        """
        return {
            "model": self.model,
            "host": self.host,
            **self.config,
        }
