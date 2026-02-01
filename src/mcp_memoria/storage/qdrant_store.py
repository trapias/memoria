"""Qdrant vector store implementation with async support."""

import logging
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel
from qdrant_client import AsyncQdrantClient, QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchAny,
    MatchText,
    MatchValue,
    PointStruct,
    Range,
    ScoredPoint,
    VectorParams,
)

from mcp_memoria.core.rate_limiter import CircuitBreaker, QDRANT_CIRCUIT_CONFIG

logger = logging.getLogger(__name__)


class SearchResult(BaseModel):
    """Result from a vector search."""

    id: str
    score: float
    payload: dict[str, Any]
    vector: list[float] | None = None


class QdrantStore:
    """Qdrant vector store for memory storage.

    Uses AsyncQdrantClient for true async I/O when connected to a server.
    Falls back to sync client for local/in-memory mode (wrapped in async).
    """

    def __init__(
        self,
        path: Path | None = None,
        host: str | None = None,
        port: int = 6333,
        vector_size: int = 768,
        distance: Distance = Distance.COSINE,
        enable_circuit_breaker: bool = True,
    ):
        """Initialize Qdrant store.

        Args:
            path: Local storage path (for local mode)
            host: Qdrant server host (for server mode)
            port: Qdrant server port
            vector_size: Dimension of vectors
            distance: Distance metric
            enable_circuit_breaker: Enable circuit breaker for remote connections
        """
        self.vector_size = vector_size
        self.distance = distance
        self._is_async = False
        self._circuit_breaker: CircuitBreaker | None = None

        # Store for sync operations (collection management)
        self._sync_client: QdrantClient | None = None
        # Store for async operations (data operations)
        self._async_client: AsyncQdrantClient | None = None

        if path:
            # Local mode with persistence - use sync client
            path.mkdir(parents=True, exist_ok=True)
            self._sync_client = QdrantClient(path=str(path))
            self.client = self._sync_client  # For backward compat
            logger.info(f"Qdrant initialized in local mode at {path}")
        elif host:
            # Server mode - use async client
            self._async_client = AsyncQdrantClient(host=host, port=port)
            self._sync_client = QdrantClient(host=host, port=port)
            self.client = self._sync_client  # For sync operations like collection_exists
            self._is_async = True
            if enable_circuit_breaker:
                self._circuit_breaker = CircuitBreaker("qdrant", QDRANT_CIRCUIT_CONFIG)
            logger.info(f"Qdrant connected to {host}:{port} (async mode)")
        else:
            # In-memory mode - use sync client
            self._sync_client = QdrantClient(":memory:")
            self.client = self._sync_client
            logger.info("Qdrant initialized in memory mode")

    async def close(self) -> None:
        """Close async client connection."""
        if self._async_client:
            await self._async_client.close()

    def create_collection(
        self,
        name: str,
        vector_size: int | None = None,
        distance: Distance | None = None,
        recreate: bool = False,
    ) -> bool:
        """Create a collection.

        Args:
            name: Collection name
            vector_size: Vector dimensions (uses default if not provided)
            distance: Distance metric (uses default if not provided)
            recreate: If True, recreate if exists

        Returns:
            True if created, False if already exists
        """
        if self.client.collection_exists(name):
            if recreate:
                self.client.delete_collection(name)
                logger.info(f"Deleted existing collection: {name}")
            else:
                logger.debug(f"Collection {name} already exists")
                return False

        self.client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(
                size=vector_size or self.vector_size,
                distance=distance or self.distance,
            ),
        )
        logger.info(f"Created collection: {name}")
        return True

    def delete_collection(self, name: str) -> bool:
        """Delete a collection.

        Args:
            name: Collection name

        Returns:
            True if deleted, False if not found
        """
        if not self.client.collection_exists(name):
            return False

        self.client.delete_collection(name)
        logger.info(f"Deleted collection: {name}")
        return True

    def collection_exists(self, name: str) -> bool:
        """Check if collection exists.

        Args:
            name: Collection name

        Returns:
            True if exists
        """
        return self.client.collection_exists(name)

    def get_collection_info(self, name: str) -> dict[str, Any]:
        """Get collection information.

        Args:
            name: Collection name

        Returns:
            Collection info dict
        """
        info = self.client.get_collection(name)
        return {
            "name": name,
            "points_count": info.points_count,
            "indexed_vectors_count": info.indexed_vectors_count,
            "status": info.status.value,
        }

    async def upsert(
        self,
        collection: str,
        vector: list[float],
        payload: dict[str, Any],
        id: str | None = None,
    ) -> str:
        """Insert or update a point.

        Args:
            collection: Collection name
            vector: Vector embedding
            payload: Metadata payload
            id: Optional point ID (generated if not provided)

        Returns:
            Point ID
        """
        point_id = id or str(uuid4())
        point = PointStruct(id=point_id, vector=vector, payload=payload)

        if self._is_async and self._async_client:
            async def _do_upsert():
                await self._async_client.upsert(
                    collection_name=collection,
                    points=[point],
                )

            if self._circuit_breaker:
                await self._circuit_breaker.call(_do_upsert)
            else:
                await _do_upsert()
        else:
            self.client.upsert(collection_name=collection, points=[point])

        logger.debug(f"Upserted point {point_id} to {collection}")
        return point_id

    async def upsert_batch(
        self,
        collection: str,
        points: list[tuple[list[float], dict[str, Any], str | None]],
    ) -> list[str]:
        """Insert or update multiple points.

        Args:
            collection: Collection name
            points: List of (vector, payload, optional_id) tuples

        Returns:
            List of point IDs
        """
        point_structs = []
        ids = []

        for vector, payload, point_id in points:
            pid = point_id or str(uuid4())
            ids.append(pid)
            point_structs.append(PointStruct(id=pid, vector=vector, payload=payload))

        if self._is_async and self._async_client:
            async def _do_upsert():
                await self._async_client.upsert(
                    collection_name=collection,
                    points=point_structs,
                )

            if self._circuit_breaker:
                await self._circuit_breaker.call(_do_upsert)
            else:
                await _do_upsert()
        else:
            self.client.upsert(collection_name=collection, points=point_structs)

        logger.debug(f"Upserted {len(points)} points to {collection}")
        return ids

    async def search(
        self,
        collection: str,
        vector: list[float],
        limit: int = 5,
        score_threshold: float | None = None,
        filter_conditions: dict[str, Any] | None = None,
        with_vectors: bool = False,
    ) -> list[SearchResult]:
        """Search for similar vectors.

        Args:
            collection: Collection name
            vector: Query vector
            limit: Maximum results
            score_threshold: Minimum similarity score
            filter_conditions: Payload filter conditions
            with_vectors: Include vectors in results

        Returns:
            List of SearchResults
        """
        qdrant_filter = self._build_filter(filter_conditions) if filter_conditions else None

        if self._is_async and self._async_client:
            async def _do_search():
                return await self._async_client.query_points(
                    collection_name=collection,
                    query=vector,
                    limit=limit,
                    score_threshold=score_threshold,
                    query_filter=qdrant_filter,
                    with_vectors=with_vectors,
                )

            if self._circuit_breaker:
                response = await self._circuit_breaker.call(_do_search)
            else:
                response = await _do_search()
        else:
            response = self.client.query_points(
                collection_name=collection,
                query=vector,
                limit=limit,
                score_threshold=score_threshold,
                query_filter=qdrant_filter,
                with_vectors=with_vectors,
            )

        return [self._scored_point_to_result(r) for r in response.points]

    async def get(
        self,
        collection: str,
        ids: list[str],
        with_vectors: bool = False,
    ) -> list[SearchResult]:
        """Get points by IDs.

        Args:
            collection: Collection name
            ids: Point IDs
            with_vectors: Include vectors

        Returns:
            List of SearchResults
        """
        if self._is_async and self._async_client:
            points = await self._async_client.retrieve(
                collection_name=collection,
                ids=ids,
                with_vectors=with_vectors,
            )
        else:
            points = self.client.retrieve(
                collection_name=collection,
                ids=ids,
                with_vectors=with_vectors,
            )

        return [
            SearchResult(
                id=str(p.id),
                score=1.0,
                payload=p.payload or {},
                vector=p.vector if with_vectors else None,
            )
            for p in points
        ]

    async def delete(
        self,
        collection: str,
        ids: list[str] | None = None,
        filter_conditions: dict[str, Any] | None = None,
    ) -> int:
        """Delete points.

        Args:
            collection: Collection name
            ids: Point IDs to delete
            filter_conditions: Delete by filter

        Returns:
            Number of points deleted (approximate)
        """
        if ids:
            if self._is_async and self._async_client:
                await self._async_client.delete(
                    collection_name=collection,
                    points_selector=ids,
                )
            else:
                self.client.delete(
                    collection_name=collection,
                    points_selector=ids,
                )
            logger.debug(f"Deleted {len(ids)} points from {collection}")
            return len(ids)

        if filter_conditions:
            qdrant_filter = self._build_filter(filter_conditions)

            if self._is_async and self._async_client:
                count_result = await self._async_client.count(
                    collection_name=collection,
                    count_filter=qdrant_filter,
                    exact=True,
                )
                count_before = count_result.count
                await self._async_client.delete(
                    collection_name=collection,
                    points_selector=qdrant_filter,
                )
            else:
                count_before = self.client.count(
                    collection_name=collection,
                    count_filter=qdrant_filter,
                    exact=True,
                ).count
                self.client.delete(
                    collection_name=collection,
                    points_selector=qdrant_filter,
                )

            logger.debug(f"Deleted ~{count_before} points from {collection} by filter")
            return count_before

        return 0

    async def update_payload(
        self,
        collection: str,
        id: str,
        payload: dict[str, Any],
        merge: bool = True,
    ) -> bool:
        """Update point payload.

        Args:
            collection: Collection name
            id: Point ID
            payload: New payload data
            merge: If True, merge with existing; if False, overwrite

        Returns:
            True if successful
        """
        if self._is_async and self._async_client:
            if merge:
                await self._async_client.set_payload(
                    collection_name=collection,
                    payload=payload,
                    points=[id],
                )
            else:
                await self._async_client.overwrite_payload(
                    collection_name=collection,
                    payload=payload,
                    points=[id],
                )
        else:
            if merge:
                self.client.set_payload(
                    collection_name=collection,
                    payload=payload,
                    points=[id],
                )
            else:
                self.client.overwrite_payload(
                    collection_name=collection,
                    payload=payload,
                    points=[id],
                )

        logger.debug(f"Updated payload for {id} in {collection}")
        return True

    async def scroll(
        self,
        collection: str,
        limit: int = 100,
        offset: str | None = None,
        filter_conditions: dict[str, Any] | None = None,
        with_vectors: bool = False,
    ) -> tuple[list[SearchResult], str | None]:
        """Scroll through all points.

        Args:
            collection: Collection name
            limit: Batch size
            offset: Offset from previous scroll
            filter_conditions: Filter conditions
            with_vectors: Include vectors

        Returns:
            Tuple of (results, next_offset)
        """
        qdrant_filter = self._build_filter(filter_conditions) if filter_conditions else None

        if self._is_async and self._async_client:
            points, next_offset = await self._async_client.scroll(
                collection_name=collection,
                limit=limit,
                offset=offset,
                scroll_filter=qdrant_filter,
                with_vectors=with_vectors,
            )
        else:
            points, next_offset = self.client.scroll(
                collection_name=collection,
                limit=limit,
                offset=offset,
                scroll_filter=qdrant_filter,
                with_vectors=with_vectors,
            )

        results = [
            SearchResult(
                id=str(p.id),
                score=1.0,
                payload=p.payload or {},
                vector=p.vector if with_vectors else None,
            )
            for p in points
        ]

        return results, next_offset

    async def count(
        self,
        collection: str,
        filter_conditions: dict[str, Any] | None = None,
        exact: bool = True,
    ) -> int:
        """Count points in collection.

        Args:
            collection: Collection name
            filter_conditions: Optional filter
            exact: Use exact count

        Returns:
            Number of points
        """
        qdrant_filter = self._build_filter(filter_conditions) if filter_conditions else None

        if self._is_async and self._async_client:
            result = await self._async_client.count(
                collection_name=collection,
                count_filter=qdrant_filter,
                exact=exact,
            )
        else:
            result = self.client.count(
                collection_name=collection,
                count_filter=qdrant_filter,
                exact=exact,
            )

        return result.count

    def _build_filter(self, conditions: dict[str, Any]) -> Filter:
        """Build Qdrant filter from conditions dict.

        Args:
            conditions: Filter conditions

        Returns:
            Qdrant Filter object
        """
        must_conditions = []

        for key, value in conditions.items():
            if key == "__text_match":
                # Split into words and create AND conditions for each word
                # This ensures all words must be present (AND logic)
                words = value.split()
                for word in words:
                    word = word.strip()
                    if word:
                        must_conditions.append(
                            FieldCondition(key="content", match=MatchText(text=word))
                        )
            elif isinstance(value, dict):
                if "gte" in value or "lte" in value or "gt" in value or "lt" in value:
                    must_conditions.append(
                        FieldCondition(
                            key=key,
                            range=Range(
                                gte=value.get("gte"),
                                lte=value.get("lte"),
                                gt=value.get("gt"),
                                lt=value.get("lt"),
                            ),
                        )
                    )
            elif isinstance(value, list):
                must_conditions.append(
                    FieldCondition(key=key, match=MatchAny(any=value))
                )
            else:
                must_conditions.append(
                    FieldCondition(key=key, match=MatchValue(value=value))
                )

        return Filter(must=must_conditions)

    def _scored_point_to_result(self, point: ScoredPoint) -> SearchResult:
        """Convert ScoredPoint to SearchResult.

        Args:
            point: Qdrant ScoredPoint

        Returns:
            SearchResult
        """
        return SearchResult(
            id=str(point.id),
            score=point.score,
            payload=point.payload or {},
            vector=point.vector if hasattr(point, "vector") else None,
        )
