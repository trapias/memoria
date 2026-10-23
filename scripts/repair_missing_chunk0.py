#!/usr/bin/env python3
"""Recreate the missing chunk 0 of chunked memories.

Background: ``MemoryConsolidator`` used to delete only the representative point (chunk 0)
of a merged duplicate, leaving chunks 1..N behind. Those groups still show up in search
(every chunk carries ``full_content``) but ``get`` / ``update`` by logical ID return
"not found", because the only physical ID derived from the logical one is chunk 0's.

This script adds back ONLY the missing chunk 0. It never rewrites or deletes a surviving
point. A group is repaired only when it can be reproduced exactly:

* every surviving chunk carries the same ``full_content`` and ``chunk_count``;
* re-chunking ``full_content`` with the current chunker settings yields ``chunk_count``
  chunks, and the text of each surviving chunk equals the re-chunked text at its index.

Anything else is reported and left untouched. The vector is recomputed from the chunk 0
text with ``text_type="document"``, exactly as ``MemoryManager.store`` does.

Run it inside the container, where the real chunker/embedder settings are in the
environment. It is a dry run unless ``--apply`` is given::

    docker cp scripts/repair_missing_chunk0.py memoria-team-server:/tmp/
    docker exec memoria-team-server python /tmp/repair_missing_chunk0.py
    docker exec memoria-team-server python /tmp/repair_missing_chunk0.py --apply
"""

import argparse
import asyncio
from collections import defaultdict
from datetime import datetime
from typing import Any

from mcp_memoria.config.settings import get_settings
from mcp_memoria.core.memory_manager import MemoryManager, _chunk_id

COLLECTIONS = ("procedural", "semantic", "episodic")


def normalise(text: str) -> str:
    return " ".join(text.split())


async def scroll_all(mgr: MemoryManager, collection: str) -> list[Any]:
    points: list[Any] = []
    offset = None
    while True:
        batch, offset = await mgr.vector_store.scroll(
            collection=collection, limit=256, offset=offset
        )
        points.extend(batch)
        if not offset:
            return points


def plan_group(mgr: MemoryManager, parent_id: str, survivors: list[Any]) -> tuple[str, Any]:
    """Return ``(status, chunk0_text)``; status is ``"ok"`` or the reason to skip."""
    fulls = {s.payload.get("full_content") for s in survivors}
    counts = {s.payload.get("chunk_count") for s in survivors}
    if len(fulls) != 1 or None in fulls:
        return "full_content assente o discordante", None
    if len(counts) != 1 or None in counts:
        return "chunk_count assente o discordante", None
    full = fulls.pop()
    chunk_count = counts.pop()

    chunks = mgr.chunker.chunk(full)
    if len(chunks) != chunk_count:
        return f"re-chunking dà {len(chunks)} chunk, attesi {chunk_count}", None
    for s in survivors:
        index = s.payload.get("chunk_index")
        if not isinstance(index, int) or not 0 < index < chunk_count:
            return f"chunk_index anomalo ({index})", None
        if chunks[index].text != s.payload.get("content"):
            return f"il chunk {index} non coincide con il re-chunking", None
    if len({s.payload["chunk_index"] for s in survivors}) != len(survivors):
        return "indici duplicati", None
    return "ok", chunks[0].text


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--apply", action="store_true", help="write the repaired chunk 0")
    parser.add_argument("--collection", choices=COLLECTIONS, help="limit to one collection")
    args = parser.parse_args()

    mgr = MemoryManager(get_settings())
    await mgr.initialize()

    # Logical IDs that are alive somewhere (chunk 0 or a non-chunked point). A damaged group
    # whose ID is alive in ANOTHER collection is a stale leftover of an older version of the
    # same memory: repairing it would resurrect superseded text next to the live one.
    alive: dict[str, set[str]] = defaultdict(set)
    for collection in COLLECTIONS:
        for p in await scroll_all(mgr, collection):
            if p.payload.get("chunk_index", 0) == 0:
                alive[p.payload.get("parent_id", p.id)].add(collection)

    repaired = skipped = 0
    for collection in args.collection and [args.collection] or COLLECTIONS:
        points = await scroll_all(mgr, collection)
        groups: dict[str, list[Any]] = defaultdict(list)
        for p in points:
            if p.payload.get("is_chunk"):
                groups[p.payload["parent_id"]].append(p)

        # logical memories whose complete text is identical to another one, for triage
        by_text: dict[str, list[str]] = defaultdict(list)
        for parent_id, pts in groups.items():
            by_text[normalise(pts[0].payload.get("full_content", ""))].append(parent_id)

        for parent_id, pts in sorted(groups.items()):
            if any(p.payload.get("chunk_index") == 0 for p in pts):
                continue
            status, chunk0_text = plan_group(mgr, parent_id, pts)
            elsewhere = alive.get(parent_id, set()) - {collection}
            if elsewhere:
                status = f"ID vivo in {', '.join(sorted(elsewhere))}: residuo di una versione precedente"
            twins = [g for g in by_text[normalise(pts[0].payload.get("full_content", ""))] if g != parent_id]
            note = f" [testo identico a {twins[0][:8]}]" if twins else ""
            title = (pts[0].payload.get("full_content") or "")[:60].replace("\n", " ")
            if status != "ok":
                skipped += 1
                print(f"SKIP   {collection:<10} {parent_id[:8]} {status} | {title!r}")
                continue

            new_id = _chunk_id(parent_id, 0)
            if await mgr.vector_store.get(collection=collection, ids=[new_id]):
                skipped += 1
                print(f"SKIP   {collection:<10} {parent_id[:8]} il chunk 0 esiste già")
                continue

            if args.apply:
                emb = await mgr.embedder.embed(chunk0_text, text_type="document")
                template = min(pts, key=lambda p: p.payload["chunk_index"]).payload
                payload = {
                    **template,
                    "content": chunk0_text,
                    "chunk_index": 0,
                    "repaired_chunk0_at": datetime.now().isoformat(),
                }
                await mgr.vector_store.upsert(
                    collection=collection, vector=emb.embedding, payload=payload, id=new_id
                )
                mgr.working_memory.invalidate_cache(parent_id)
                found = await mgr.get(parent_id, collection)
                if found is None or found.content != template["full_content"]:
                    print(f"ERRORE {collection:<10} {parent_id[:8]} verifica fallita dopo la scrittura")
                    return 1
            repaired += 1
            verb = "REPAIR" if args.apply else "WOULD "
            print(f"{verb} {collection:<10} {parent_id[:8]} {len(pts)}/{pts[0].payload['chunk_count']} chunk{note} | {title!r}")

    print(f"\n{'riparati' if args.apply else 'riparabili'}: {repaired} | saltati: {skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
