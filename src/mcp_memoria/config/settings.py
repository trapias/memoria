"""Application settings and configuration."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="MEMORIA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Qdrant settings
    qdrant_path: Path = Field(
        default=Path.home() / ".mcp-memoria" / "qdrant",
        description="Path for Qdrant local storage",
    )
    qdrant_host: str | None = Field(
        default=None,
        description="Qdrant server host (if using server mode)",
    )
    qdrant_port: int = Field(
        default=6333,
        description="Qdrant server port",
    )

    # Ollama settings
    ollama_host: str = Field(
        default="http://localhost:11434",
        description="Ollama server URL",
    )
    embedding_model: str = Field(
        default="nomic-embed-text",
        description="Ollama model for embeddings",
    )
    embedding_dimensions: int = Field(
        default=768,
        description="Embedding vector dimensions",
    )

    # Cache settings
    cache_path: Path = Field(
        default=Path.home() / ".mcp-memoria" / "cache",
        description="Path for embedding cache",
    )
    cache_enabled: bool = Field(
        default=True,
        description="Enable embedding caching",
    )

    # Memory settings
    default_memory_type: Literal["episodic", "semantic", "procedural"] = Field(
        default="episodic",
        description="Default memory type for storage",
    )
    default_recall_limit: int = Field(
        default=5,
        description="Default number of results for recall",
    )
    min_similarity_score: float = Field(
        default=0.5,
        description="Minimum similarity score for recall",
    )

    # Consolidation settings
    consolidation_threshold: float = Field(
        default=0.9,
        description="Similarity threshold for memory consolidation",
    )
    forgetting_days: int = Field(
        default=30,
        description="Days before applying forgetting to unused memories",
    )
    min_importance_threshold: float = Field(
        default=0.3,
        description="Minimum importance to retain during forgetting",
    )

    # Chunking settings
    chunk_size: int = Field(
        default=500,
        description="Default chunk size for text splitting",
    )
    chunk_overlap: int = Field(
        default=50,
        description="Overlap between chunks",
    )

    # Update check
    skip_update_check: bool = Field(
        default=False,
        description="Skip checking for updates at startup",
    )

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        description="Logging level",
    )
    log_file: Path | None = Field(
        default=None,
        description="Log file path (if set, logs are written to file in addition to stderr)",
    )

    # HTTP transport settings
    http_port: int | None = Field(
        default=None,
        description="HTTP port for SSE transport (if set, uses HTTP instead of stdio)",
    )
    http_host: str = Field(
        default="0.0.0.0",
        description="HTTP host to bind to",
    )

    # PostgreSQL settings (optional, enables relational data features)
    database_url: str | None = Field(
        default=None,
        description="PostgreSQL connection URL (e.g., postgresql://user:pass@host:5432/db)",
    )
    db_migrate: bool = Field(
        default=False,
        description="Run database migrations on startup",
    )
    db_pool_min: int = Field(
        default=2,
        description="Minimum database connection pool size",
    )
    db_pool_max: int = Field(
        default=10,
        description="Maximum database connection pool size",
    )

    def ensure_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        self.qdrant_path.mkdir(parents=True, exist_ok=True)
        self.cache_path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    settings = Settings()
    settings.ensure_directories()
    return settings
