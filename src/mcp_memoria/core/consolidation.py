"""Memory consolidation and forgetting operations."""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from mcp_memoria.storage.qdrant_store import QdrantStore, SearchResult
from mcp_memoria.utils.datetime_utils import parse_datetime

logger = logging.getLogger(__name__)


@dataclass
class ConsolidationResult:
    """Result of a consolidation operation."""

    merged_count: int
    forgotten_count: int
    updated_count: int
    total_processed: int
    duration_seconds: float
    dry_run: bool


class MemoryConsolidator:
    """Handles memory consolidation and forgetting operations.

    Consolidation merges similar memories to reduce redundancy.
    Forgetting removes old, low-importance memories that haven't been accessed.
    """

    def __init__(self, store: QdrantStore):
        """Initialize consolidator.

        Args:
            store: Qdrant store instance
        """
        self.store = store

    async def consolidate(
        self,
        collection: str,
        similarity_threshold: float = 0.9,
        max_cluster_size: int = 10,
        dry_run: bool = True,
    ) -> ConsolidationResult:
        """Consolidate similar memories in a collection.

        Args:
            collection: Collection name
            similarity_threshold: Minimum similarity for merging
            max_cluster_size: Maximum memories to merge at once
            dry_run: If True, don't actually modify

        Returns:
            ConsolidationResult with operation details
        """
        start_time = datetime.now()
        merged_count = 0
        processed_ids: set[str] = set()

        # Get all memories
        all_memories = []
        offset = None

        while True:
            results, next_offset = await self.store.scroll(
                collection=collection,
                limit=100,
                offset=offset,
                with_vectors=True,
            )
            all_memories.extend(results)
            if not next_offset:
                break
            offset = next_offset

        logger.info(f"Processing {len(all_memories)} memories for consolidation")

        # Find similar groups — only consider representative points
        for memory in all_memories:
            if memory.id in processed_ids:
                continue

            if not memory.vector:
                continue

            # Skip non-representative chunks (only process chunk_index==0 or non-chunked)
            chunk_index = memory.payload.get("chunk_index", 0)
            if chunk_index > 0:
                continue

            parent_id = memory.payload.get("parent_id", memory.id)

            # Find similar memories
            similar = await self.store.search(
                collection=collection,
                vector=memory.vector,
                limit=max_cluster_size + 1,
                score_threshold=similarity_threshold,
            )

            # Filter out: already processed, self, and chunks from the same parent
            similar = [
                s for s in similar
                if s.id not in processed_ids
                and s.id != memory.id
                and s.payload.get("parent_id", s.id) != parent_id
                and s.payload.get("chunk_index", 0) == 0
            ]

            if similar:
                # Merge similar memories
                if not dry_run:
                    await self._merge_memories(collection, memory, similar)

                merged_count += len(similar)
                processed_ids.add(memory.id)
                processed_ids.update(s.id for s in similar)

                logger.debug(f"Merged {len(similar)} memories into {memory.id}")

        duration = (datetime.now() - start_time).total_seconds()

        return ConsolidationResult(
            merged_count=merged_count,
            forgotten_count=0,
            updated_count=0,
            total_processed=len(all_memories),
            duration_seconds=duration,
            dry_run=dry_run,
        )

    async def _merge_memories(
        self,
        collection: str,
        primary: SearchResult,
        duplicates: list[SearchResult],
    ) -> None:
        """Merge duplicate memories into the primary.

        Args:
            collection: Collection name
            primary: Primary memory to keep
            duplicates: Memories to merge into primary
        """
        # Combine information
        all_tags = set(primary.payload.get("tags", []))
        max_importance = primary.payload.get("importance", 0.5)
        total_access = primary.payload.get("access_count", 0)
        merged_content = [primary.payload.get("content", "")]

        for dup in duplicates:
            all_tags.update(dup.payload.get("tags", []))
            max_importance = max(max_importance, dup.payload.get("importance", 0.5))
            total_access += dup.payload.get("access_count", 0)
            merged_content.append(dup.payload.get("content", ""))

        # Update primary
        await self.store.update_payload(
            collection=collection,
            id=primary.id,
            payload={
                "tags": list(all_tags),
                "importance": max_importance,
                "access_count": total_access,
                "merged_from": [d.id for d in duplicates],
                "merged_at": datetime.now().isoformat(),
            },
            merge=True,
        )

        # Delete duplicates
        await self.store.delete(
            collection=collection,
            ids=[d.id for d in duplicates],
        )

    async def apply_forgetting(
        self,
        collection: str,
        max_age_days: int = 30,
        min_importance: float = 0.3,
        min_access_count: int = 1,
        dry_run: bool = True,
    ) -> ConsolidationResult:
        """Apply forgetting curve to remove old, unused memories.

        Args:
            collection: Collection name
            max_age_days: Age threshold for forgetting
            min_importance: Minimum importance to retain
            min_access_count: Minimum accesses to retain
            dry_run: If True, don't actually delete

        Returns:
            ConsolidationResult with operation details
        """
        start_time = datetime.now()
        cutoff_date = datetime.now() - timedelta(days=max_age_days)

        # Find candidates for forgetting
        candidates = []
        offset = None

        while True:
            results, next_offset = await self.store.scroll(
                collection=collection,
                limit=100,
                offset=offset,
            )

            for result in results:
                # Only operate on representative points (chunk_index==0 or non-chunked)
                if result.payload.get("chunk_index", 0) > 0:
                    continue

                # Check if should forget
                accessed_at = result.payload.get("accessed_at")
                if accessed_at:
                    accessed = parse_datetime(accessed_at)
                else:
                    created_at = result.payload.get("created_at")
                    accessed = parse_datetime(created_at)

                importance = result.payload.get("importance", 0.5)
                access_count = result.payload.get("access_count", 0)

                if (
                    accessed < cutoff_date
                    and importance < min_importance
                    and access_count < min_access_count
                ):
                    parent_id = result.payload.get("parent_id", result.id)
                    candidates.append(parent_id)

            if not next_offset:
                break
            offset = next_offset

        logger.info(f"Found {len(candidates)} memories to forget")

        if not dry_run and candidates:
            # Delete all points for each candidate parent_id
            for parent_id in candidates:
                # Delete by parent_id filter to remove all chunks
                await self.store.delete(
                    collection=collection,
                    filter_conditions={"parent_id": parent_id},
                )
                # Also try deleting the direct ID (non-chunked legacy memories)
                try:
                    await self.store.delete(collection=collection, ids=[parent_id])
                except Exception:
                    pass

        duration = (datetime.now() - start_time).total_seconds()

        return ConsolidationResult(
            merged_count=0,
            forgotten_count=len(candidates),
            updated_count=0,
            total_processed=len(candidates),
            duration_seconds=duration,
            dry_run=dry_run,
        )

    async def decay_importance(
        self,
        collection: str,
        decay_rate: float = 0.95,
        min_days_since_access: int = 7,
        dry_run: bool = True,
    ) -> ConsolidationResult:
        """Apply importance decay to old memories.

        Args:
            collection: Collection name
            decay_rate: Decay multiplier per day
            min_days_since_access: Days before decay starts
            dry_run: If True, don't actually update

        Returns:
            ConsolidationResult with operation details
        """
        start_time = datetime.now()
        updated_count = 0
        cutoff = datetime.now() - timedelta(days=min_days_since_access)

        offset = None

        while True:
            results, next_offset = await self.store.scroll(
                collection=collection,
                limit=100,
                offset=offset,
            )

            for result in results:
                accessed_at = result.payload.get("accessed_at")
                if not accessed_at:
                    continue

                accessed = parse_datetime(accessed_at)
                if accessed >= cutoff:
                    continue

                days_since = (datetime.now() - accessed).days
                current_importance = result.payload.get("importance", 0.5)
                new_importance = current_importance * (decay_rate**days_since)

                # Don't decay below minimum
                new_importance = max(0.1, new_importance)

                if not dry_run and abs(new_importance - current_importance) > 0.01:
                    await self.store.update_payload(
                        collection=collection,
                        id=result.id,
                        payload={"importance": new_importance},
                        merge=True,
                    )
                    updated_count += 1

            if not next_offset:
                break
            offset = next_offset

        duration = (datetime.now() - start_time).total_seconds()

        return ConsolidationResult(
            merged_count=0,
            forgotten_count=0,
            updated_count=updated_count,
            total_processed=updated_count,
            duration_seconds=duration,
            dry_run=dry_run,
        )

    async def boost_on_access(
        self,
        collection: str,
        memory_id: str,
        boost_amount: float = 0.1,
        max_importance: float = 1.0,
    ) -> float:
        """Boost memory importance on access.

        Propagates the boost to all chunks of the same parent memory.

        Args:
            collection: Collection name
            memory_id: Memory ID (point ID, may be a chunk)
            boost_amount: Amount to boost importance
            max_importance: Maximum importance value

        Returns:
            New importance value
        """
        results = await self.store.get(collection=collection, ids=[memory_id])
        if not results:
            return 0.0

        current = results[0].payload.get("importance", 0.5)
        new_importance = min(max_importance, current + boost_amount)
        parent_id = results[0].payload.get("parent_id", memory_id)

        boost_payload = {
            "importance": new_importance,
            "access_count": results[0].payload.get("access_count", 0) + 1,
            "accessed_at": datetime.now().isoformat(),
        }

        # Update the accessed point
        await self.store.update_payload(
            collection=collection,
            id=memory_id,
            payload=boost_payload,
            merge=True,
        )

        # Propagate to sibling chunks (if any)
        if results[0].payload.get("is_chunk", False):
            siblings, _ = await self.store.scroll(
                collection=collection,
                limit=1000,
                filter_conditions={"parent_id": parent_id},
            )
            for sibling in siblings:
                if sibling.id != memory_id:
                    await self.store.update_payload(
                        collection=collection,
                        id=sibling.id,
                        payload=boost_payload,
                        merge=True,
                    )

        return new_importance

    async def boost_on_access_batch(
        self,
        items: list[tuple[str, str]],
        boost_amount: float = 0.1,
        max_importance: float = 1.0,
    ) -> None:
        """Boost importance for multiple memories in batch.

        This is more efficient than calling boost_on_access() in a loop,
        as it batches the operations by collection.

        Args:
            items: List of (collection, memory_id) tuples
            boost_amount: Amount to boost importance
            max_importance: Maximum importance value
        """
        if not items:
            return

        # Group by collection for efficiency
        by_collection: dict[str, list[str]] = {}
        for collection, memory_id in items:
            by_collection.setdefault(collection, []).append(memory_id)

        accessed_at = datetime.now().isoformat()

        for collection, memory_ids in by_collection.items():
            # Batch fetch all memories at once
            results = await self.store.get(collection=collection, ids=memory_ids)
            if not results:
                continue

            # Build a map for quick lookup
            results_map = {r.id: r for r in results}

            # Collect all point IDs that need updating (including sibling chunks)
            all_parent_ids: set[str] = set()
            for memory_id in memory_ids:
                if memory_id in results_map:
                    r = results_map[memory_id]
                    parent_id = r.payload.get("parent_id", memory_id)
                    all_parent_ids.add(parent_id)

            # Find all chunks for these parents in one scroll
            if all_parent_ids:
                all_points_to_update: list[tuple[str, float, int]] = []

                for parent_id in all_parent_ids:
                    # Get all chunks for this parent
                    chunks, _ = await self.store.scroll(
                        collection=collection,
                        limit=1000,
                        filter_conditions={"parent_id": parent_id},
                    )

                    if chunks:
                        # Use first chunk's current values
                        current_importance = chunks[0].payload.get("importance", 0.5)
                        current_access = chunks[0].payload.get("access_count", 0)
                        new_importance = min(max_importance, current_importance + boost_amount)

                        for chunk in chunks:
                            all_points_to_update.append(
                                (chunk.id, new_importance, current_access + 1)
                            )
                    else:
                        # Non-chunked memory - update directly by parent_id
                        direct = await self.store.get(collection=collection, ids=[parent_id])
                        if direct:
                            current_importance = direct[0].payload.get("importance", 0.5)
                            current_access = direct[0].payload.get("access_count", 0)
                            new_importance = min(max_importance, current_importance + boost_amount)
                            all_points_to_update.append(
                                (parent_id, new_importance, current_access + 1)
                            )

                # Update all points
                for point_id, new_importance, new_access in all_points_to_update:
                    await self.store.update_payload(
                        collection=collection,
                        id=point_id,
                        payload={
                            "importance": new_importance,
                            "access_count": new_access,
                            "accessed_at": accessed_at,
                        },
                        merge=True,
                    )

        return new_importance
