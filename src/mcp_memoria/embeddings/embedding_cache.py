"""SQLite-based cache for embeddings."""

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path

import aiosqlite

logger = logging.getLogger(__name__)


class EmbeddingCache:
    """SQLite-based cache for storing computed embeddings."""

    def __init__(self, cache_path: Path):
        """Initialize the embedding cache.

        Args:
            cache_path: Directory path for the cache database
        """
        self.cache_path = cache_path
        self.db_path = cache_path / "embeddings.db"
        self._initialized = False

    async def _ensure_initialized(self) -> None:
        """Ensure the database is initialized."""
        if self._initialized:
            return

        self.cache_path.mkdir(parents=True, exist_ok=True)

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS embeddings (
                    hash TEXT PRIMARY KEY,
                    model TEXT NOT NULL,
                    text_preview TEXT,
                    embedding BLOB NOT NULL,
                    dimensions INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    last_accessed TEXT NOT NULL,
                    access_count INTEGER DEFAULT 1
                )
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_model ON embeddings(model)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_created ON embeddings(created_at)
            """)
            await db.commit()

        self._initialized = True
        logger.info(f"Embedding cache initialized at {self.db_path}")

    @staticmethod
    def _hash_text(text: str, model: str) -> str:
        """Create a hash key for text and model combination.

        Args:
            text: The text that was embedded
            model: The model used for embedding

        Returns:
            SHA-256 hash string
        """
        content = f"{model}:{text}"
        return hashlib.sha256(content.encode()).hexdigest()

    async def get(self, text: str, model: str) -> list[float] | None:
        """Retrieve embedding from cache.

        Args:
            text: The text to look up
            model: The model used for embedding

        Returns:
            Embedding vector if found, None otherwise
        """
        await self._ensure_initialized()

        hash_key = self._hash_text(text, model)

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT embedding FROM embeddings WHERE hash = ?",
                (hash_key,),
            )
            row = await cursor.fetchone()

            if row:
                # Update access stats
                await db.execute(
                    """
                    UPDATE embeddings
                    SET last_accessed = ?, access_count = access_count + 1
                    WHERE hash = ?
                    """,
                    (datetime.now().isoformat(), hash_key),
                )
                await db.commit()

                return json.loads(row[0])

        return None

    async def set(
        self,
        text: str,
        model: str,
        embedding: list[float],
    ) -> None:
        """Store embedding in cache.

        Args:
            text: The text that was embedded
            model: The model used for embedding
            embedding: The embedding vector
        """
        await self._ensure_initialized()

        hash_key = self._hash_text(text, model)
        now = datetime.now().isoformat()
        text_preview = text[:200] if len(text) > 200 else text

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO embeddings
                (hash, model, text_preview, embedding, dimensions, created_at, last_accessed, access_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, COALESCE(
                    (SELECT access_count + 1 FROM embeddings WHERE hash = ?), 1
                ))
                """,
                (
                    hash_key,
                    model,
                    text_preview,
                    json.dumps(embedding),
                    len(embedding),
                    now,
                    now,
                    hash_key,
                ),
            )
            await db.commit()

    async def delete(self, text: str, model: str) -> bool:
        """Delete embedding from cache.

        Args:
            text: The text to delete
            model: The model used for embedding

        Returns:
            True if deleted, False if not found
        """
        await self._ensure_initialized()

        hash_key = self._hash_text(text, model)

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM embeddings WHERE hash = ?",
                (hash_key,),
            )
            await db.commit()
            return cursor.rowcount > 0

    async def clear(self, model: str | None = None) -> int:
        """Clear cache entries.

        Args:
            model: If provided, only clear entries for this model

        Returns:
            Number of entries deleted
        """
        await self._ensure_initialized()

        async with aiosqlite.connect(self.db_path) as db:
            if model:
                cursor = await db.execute(
                    "DELETE FROM embeddings WHERE model = ?",
                    (model,),
                )
            else:
                cursor = await db.execute("DELETE FROM embeddings")

            await db.commit()
            return cursor.rowcount

    async def get_stats(self) -> dict:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        await self._ensure_initialized()

        async with aiosqlite.connect(self.db_path) as db:
            # Total count
            cursor = await db.execute("SELECT COUNT(*) FROM embeddings")
            total_count = (await cursor.fetchone())[0]

            # Count by model
            cursor = await db.execute(
                "SELECT model, COUNT(*) FROM embeddings GROUP BY model"
            )
            by_model = dict(await cursor.fetchall())

            # Total size (approximate)
            cursor = await db.execute(
                "SELECT SUM(LENGTH(embedding)) FROM embeddings"
            )
            total_size = (await cursor.fetchone())[0] or 0

            # Most accessed
            cursor = await db.execute(
                """
                SELECT text_preview, access_count
                FROM embeddings
                ORDER BY access_count DESC
                LIMIT 5
                """
            )
            most_accessed = await cursor.fetchall()

        return {
            "total_entries": total_count,
            "by_model": by_model,
            "total_size_bytes": total_size,
            "most_accessed": [
                {"text": row[0], "count": row[1]} for row in most_accessed
            ],
        }

    async def prune(
        self,
        max_age_days: int = 30,
        max_entries: int | None = None,
    ) -> int:
        """Remove old or excess cache entries.

        Args:
            max_age_days: Remove entries older than this
            max_entries: Keep only this many entries (by last access)

        Returns:
            Number of entries removed
        """
        await self._ensure_initialized()

        removed = 0

        async with aiosqlite.connect(self.db_path) as db:
            # Remove by age
            from datetime import timedelta

            cutoff = (datetime.now() - timedelta(days=max_age_days)).isoformat()
            cursor = await db.execute(
                "DELETE FROM embeddings WHERE last_accessed < ?",
                (cutoff,),
            )
            removed += cursor.rowcount

            # Remove excess entries
            if max_entries:
                cursor = await db.execute("SELECT COUNT(*) FROM embeddings")
                current_count = (await cursor.fetchone())[0]

                if current_count > max_entries:
                    to_remove = current_count - max_entries
                    cursor = await db.execute(
                        """
                        DELETE FROM embeddings WHERE hash IN (
                            SELECT hash FROM embeddings
                            ORDER BY last_accessed ASC
                            LIMIT ?
                        )
                        """,
                        (to_remove,),
                    )
                    removed += cursor.rowcount

            await db.commit()

        logger.info(f"Pruned {removed} cache entries")
        return removed
