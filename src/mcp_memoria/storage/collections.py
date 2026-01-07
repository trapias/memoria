"""Collection management for memory types."""

import logging
from enum import Enum
from typing import Any

from qdrant_client.models import (
    Distance,
    HnswConfigDiff,
    PayloadSchemaType,
    TextIndexParams,
    TokenizerType,
)

from mcp_memoria.storage.qdrant_store import QdrantStore

logger = logging.getLogger(__name__)


class MemoryCollection(str, Enum):
    """Memory collection types."""

    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"


# Collection configurations
COLLECTION_CONFIGS: dict[MemoryCollection, dict[str, Any]] = {
    MemoryCollection.EPISODIC: {
        "description": "Events, conversations, and time-bound memories",
        "hnsw_config": HnswConfigDiff(
            m=16,
            ef_construct=100,
            full_scan_threshold=10000,
        ),
        "payload_indexes": {
            "timestamp": PayloadSchemaType.DATETIME,
            "tags": PayloadSchemaType.KEYWORD,
            "project": PayloadSchemaType.KEYWORD,
            "importance": PayloadSchemaType.FLOAT,
            "session_id": PayloadSchemaType.KEYWORD,
        },
    },
    MemoryCollection.SEMANTIC: {
        "description": "Facts, concepts, and persistent knowledge",
        "hnsw_config": HnswConfigDiff(
            m=32,  # Higher for better recall on facts
            ef_construct=200,
            full_scan_threshold=10000,
        ),
        "payload_indexes": {
            "domain": PayloadSchemaType.KEYWORD,
            "source": PayloadSchemaType.KEYWORD,
            "confidence": PayloadSchemaType.FLOAT,
            "tags": PayloadSchemaType.KEYWORD,
        },
    },
    MemoryCollection.PROCEDURAL: {
        "description": "Procedures, workflows, and learned skills",
        "hnsw_config": HnswConfigDiff(
            m=16,
            ef_construct=100,
            full_scan_threshold=10000,
        ),
        "payload_indexes": {
            "category": PayloadSchemaType.KEYWORD,
            "success_rate": PayloadSchemaType.FLOAT,
            "frequency": PayloadSchemaType.INTEGER,
            "tags": PayloadSchemaType.KEYWORD,
        },
    },
}


class CollectionManager:
    """Manages memory collections in Qdrant."""

    def __init__(self, store: QdrantStore, vector_size: int = 768):
        """Initialize collection manager.

        Args:
            store: Qdrant store instance
            vector_size: Vector dimensions
        """
        self.store = store
        self.vector_size = vector_size

    async def initialize_collections(self, recreate: bool = False) -> dict[str, bool]:
        """Initialize all memory collections.

        Args:
            recreate: If True, recreate existing collections

        Returns:
            Dict of collection name -> created status
        """
        results = {}

        for collection in MemoryCollection:
            created = await self._create_collection(collection, recreate)
            results[collection.value] = created

        return results

    async def _create_collection(
        self,
        collection: MemoryCollection,
        recreate: bool = False,
    ) -> bool:
        """Create a single collection with configuration.

        Args:
            collection: Collection type
            recreate: If True, recreate if exists

        Returns:
            True if created
        """
        config = COLLECTION_CONFIGS[collection]

        # Create base collection
        created = self.store.create_collection(
            name=collection.value,
            vector_size=self.vector_size,
            distance=Distance.COSINE,
            recreate=recreate,
        )

        if created or recreate:
            # Apply HNSW config
            try:
                self.store.client.update_collection(
                    collection_name=collection.value,
                    hnsw_config=config["hnsw_config"],
                )
            except Exception as e:
                logger.warning(f"Failed to update HNSW config for {collection.value}: {e}")

            # Create payload indexes
            await self._create_payload_indexes(collection)

        return created

    async def _create_payload_indexes(self, collection: MemoryCollection) -> None:
        """Create payload indexes for a collection.

        Args:
            collection: Collection type
        """
        config = COLLECTION_CONFIGS[collection]
        indexes = config.get("payload_indexes", {})

        for field_name, field_type in indexes.items():
            try:
                self.store.client.create_payload_index(
                    collection_name=collection.value,
                    field_name=field_name,
                    field_schema=field_type,
                )
                logger.debug(f"Created index {field_name} on {collection.value}")
            except Exception as e:
                # Index might already exist
                logger.debug(f"Index {field_name} on {collection.value}: {e}")

    async def create_text_index(
        self,
        collection: MemoryCollection,
        field_name: str = "content",
    ) -> bool:
        """Create a full-text index on a field.

        Args:
            collection: Collection type
            field_name: Field to index

        Returns:
            True if created
        """
        try:
            self.store.client.create_payload_index(
                collection_name=collection.value,
                field_name=field_name,
                field_schema=TextIndexParams(
                    type="text",
                    tokenizer=TokenizerType.WORD,
                    min_token_len=2,
                    max_token_len=20,
                    lowercase=True,
                ),
            )
            logger.info(f"Created text index on {collection.value}.{field_name}")
            return True
        except Exception as e:
            logger.warning(f"Failed to create text index: {e}")
            return False

    def get_collection_stats(self) -> dict[str, dict[str, Any]]:
        """Get statistics for all collections.

        Returns:
            Dict of collection name -> stats
        """
        stats = {}

        for collection in MemoryCollection:
            if self.store.collection_exists(collection.value):
                info = self.store.get_collection_info(collection.value)
                config = COLLECTION_CONFIGS[collection]
                stats[collection.value] = {
                    **info,
                    "description": config["description"],
                }
            else:
                stats[collection.value] = {
                    "exists": False,
                    "description": COLLECTION_CONFIGS[collection]["description"],
                }

        return stats

    def collection_exists(self, memory_type: str) -> bool:
        """Check if a collection exists.

        Args:
            memory_type: Memory type name

        Returns:
            True if exists
        """
        try:
            collection = MemoryCollection(memory_type)
            return self.store.collection_exists(collection.value)
        except ValueError:
            return False

    def get_collection_name(self, memory_type: str) -> str:
        """Get collection name for a memory type.

        Args:
            memory_type: Memory type (episodic, semantic, procedural)

        Returns:
            Collection name

        Raises:
            ValueError: If invalid memory type
        """
        try:
            return MemoryCollection(memory_type).value
        except ValueError:
            raise ValueError(
                f"Invalid memory type: {memory_type}. "
                f"Must be one of: {[m.value for m in MemoryCollection]}"
            )
