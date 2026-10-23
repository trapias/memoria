"""Chunked memories stay whole through consolidate, get, update, delete and stats.

A long memory is stored as chunk points sharing a ``parent_id``; there is no point with the
logical ID. Losing chunk 0 makes the memory unreadable by ID while search still returns it,
so every operation here must treat the whole group as one unit.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from mcp_memoria.core.memory_manager import MemoryManager, _chunk_id
from tests.test_chunking_integration import initialized_manager, manager  # noqa: F401

SENTENCE = "Questa frase serve a produrre una memoria abbastanza lunga da essere divisa in chunk. "


async def scroll_points(mgr, collection, filter_conditions):
    """Every point matching a filter, via the raw store (independent of the code under test)."""
    points, offset = [], None
    while True:
        batch, offset = await mgr.vector_store.scroll(
            collection=collection, limit=50, offset=offset, filter_conditions=filter_conditions
        )
        points.extend(batch)
        if not offset:
            return points


async def group_points(mgr, collection, parent_id):
    """All points of a logical memory, ordered by chunk index."""
    points = await scroll_points(mgr, collection, {"parent_id": parent_id})
    return sorted(points, key=lambda p: p.payload.get("chunk_index", 0))


class TestConsolidateKeepsGroupsWhole:
    @pytest.mark.asyncio
    async def test_identical_duplicate_is_deleted_with_all_its_chunks(self, initialized_manager):
        mgr = initialized_manager
        content = SENTENCE * 8
        first = await mgr.store(content=content, memory_type="semantic", tags=["a"])
        second = await mgr.store(content=content, memory_type="semantic", tags=["b"])
        assert len(await group_points(mgr, "semantic", first.id)) > 1

        result = await mgr.consolidator.consolidate(
            collection="semantic", similarity_threshold=0.99, dry_run=False
        )

        assert result.merged_count == 1
        survivors = {first.id, second.id}
        remaining = {
            p.payload["parent_id"] for p in await scroll_points(mgr, "semantic", {"is_chunk": True})
        }
        # exactly one logical memory is left, and it is complete (indices 0..n-1)
        assert len(remaining) == 1 and remaining < survivors
        parent = remaining.pop()
        points = await group_points(mgr, "semantic", parent)
        assert [p.payload["chunk_index"] for p in points] == list(range(len(points)))
        assert {p.payload["chunk_count"] for p in points} == {len(points)}
        # tags were merged and provenance records the LOGICAL id of the deleted memory
        deleted = (survivors - {parent}).pop()
        assert {"a", "b"} <= set(points[0].payload["tags"])
        assert deleted in points[0].payload["merged_from"]
        # the survivor is still readable by its logical id
        assert await mgr.get(parent, "semantic") is not None

    @pytest.mark.asyncio
    async def test_similar_but_different_text_is_not_merged(self, initialized_manager):
        mgr = initialized_manager
        # same opening (so chunk 0 is identical), different ending
        shared = SENTENCE * 3
        first = await mgr.store(content=shared + "Finale uno. " * 15, memory_type="semantic")
        second = await mgr.store(content=shared + "Conclusione diversa. " * 15, memory_type="semantic")
        before = {
            first.id: len(await group_points(mgr, "semantic", first.id)),
            second.id: len(await group_points(mgr, "semantic", second.id)),
        }

        result = await mgr.consolidator.consolidate(
            collection="semantic", similarity_threshold=0.99, dry_run=False
        )

        assert result.merged_count == 0
        for parent_id, count in before.items():
            assert len(await group_points(mgr, "semantic", parent_id)) == count
            assert await mgr.get(parent_id, "semantic") is not None


class TestGetWithoutChunkZero:
    @pytest.mark.asyncio
    async def test_get_serves_group_whose_chunk_zero_is_missing(self, initialized_manager):
        mgr = initialized_manager
        content = SENTENCE * 8
        memory = await mgr.store(content=content, memory_type="procedural")
        await mgr.vector_store.delete(
            collection="procedural", ids=[_chunk_id(memory.id, 0)]
        )
        mgr.working_memory.invalidate_cache(memory.id)

        found = await mgr.get(memory.id, "procedural")

        assert found is not None
        assert found.id == memory.id
        assert found.content == content


class TestDeleteResolvesParent:
    @pytest.mark.asyncio
    async def test_physical_chunk_id_deletes_the_whole_group(self, initialized_manager):
        mgr = initialized_manager
        memory = await mgr.store(content=SENTENCE * 8, memory_type="episodic")
        total = len(await group_points(mgr, "episodic", memory.id))
        assert total > 2

        deleted = await mgr._delete_memory_points(_chunk_id(memory.id, 1), "episodic")

        assert deleted == total
        assert await group_points(mgr, "episodic", memory.id) == []

    @pytest.mark.asyncio
    async def test_scroll_all_follows_every_page(self):
        pages = [
            ([MagicMock(id=f"p{i}") for i in range(256)], "next1"),
            ([MagicMock(id=f"q{i}") for i in range(256)], "next2"),
            ([MagicMock(id=f"r{i}") for i in range(88)], None),
        ]
        mgr = MemoryManager.__new__(MemoryManager)
        mgr.vector_store = MagicMock()
        mgr.vector_store.scroll = AsyncMock(side_effect=pages)

        results = await mgr._scroll_all("semantic", {"parent_id": "x"})

        assert len(results) == 600


class TestUpdateGenerations:
    @pytest.mark.asyncio
    async def test_embedding_failure_keeps_the_old_memory(self, initialized_manager):
        mgr = initialized_manager
        original = SENTENCE * 8
        memory = await mgr.store(content=original, memory_type="semantic")
        before = len(await group_points(mgr, "semantic", memory.id))
        mgr.embedder.embed = AsyncMock(side_effect=RuntimeError("embedder down"))

        with pytest.raises(RuntimeError):
            await mgr.update(memory.id, "semantic", content=SENTENCE * 6 + "Nuovo finale.")

        assert len(await group_points(mgr, "semantic", memory.id)) == before
        mgr.working_memory.invalidate_cache(memory.id)
        assert (await mgr.get(memory.id, "semantic")).content == original

    @pytest.mark.asyncio
    async def test_shorter_update_drops_stale_chunks(self, initialized_manager):
        mgr = initialized_manager
        memory = await mgr.store(content=SENTENCE * 12, memory_type="semantic")
        before = len(await group_points(mgr, "semantic", memory.id))
        new_content = SENTENCE * 3

        updated = await mgr.update(memory.id, "semantic", content=new_content)

        points = await group_points(mgr, "semantic", memory.id)
        assert updated is not None and updated.id == memory.id
        assert len(points) < before
        assert [p.payload["chunk_index"] for p in points] == list(range(len(points)))
        assert {p.payload["chunk_count"] for p in points} == {len(points)}
        assert {p.payload["full_content"] for p in points} == {new_content}

    @pytest.mark.asyncio
    async def test_long_to_short_update_leaves_a_single_point(self, initialized_manager):
        mgr = initialized_manager
        memory = await mgr.store(content=SENTENCE * 8, memory_type="semantic")

        await mgr.update(memory.id, "semantic", content="Ora e' breve.")

        points = await group_points(mgr, "semantic", memory.id)
        assert [p.id for p in points] == [memory.id]
        assert points[0].payload["is_chunk"] is False
        assert (await mgr.get(memory.id, "semantic")).content == "Ora e' breve."


class TestLogicalCounts:
    @pytest.mark.asyncio
    async def test_counts_separate_points_memories_and_incomplete_groups(self, initialized_manager):
        mgr = initialized_manager
        whole = await mgr.store(content=SENTENCE * 8, memory_type="semantic")
        damaged = await mgr.store(content=SENTENCE * 8, memory_type="semantic")
        await mgr.store(content="Breve.", memory_type="semantic")
        await mgr.vector_store.delete(collection="semantic", ids=[_chunk_id(damaged.id, 0)])
        whole_points = len(await group_points(mgr, "semantic", whole.id))
        damaged_points = len(await group_points(mgr, "semantic", damaged.id))

        counts = (await mgr.get_logical_counts())["semantic"]

        assert counts["memories"] == 3
        assert counts["points"] == whole_points + damaged_points + 1
        assert counts["incomplete_groups"] == 1
