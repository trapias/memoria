"""
Backup and Restore API endpoints.
"""

import json
import logging
from datetime import datetime
from typing import Optional, List, Any
from io import BytesIO

from fastapi import APIRouter, Request, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter()


class ExportRequest(BaseModel):
    """Request for exporting memories."""

    include_graph: bool = True
    memory_types: List[str] = Field(default=["episodic", "semantic", "procedural"])


class ExportStats(BaseModel):
    """Statistics about an export."""

    memories_count: int
    relations_count: int
    tags_count: int
    exported_at: str


class ImportResult(BaseModel):
    """Result of an import operation."""

    memories_imported: int
    memories_skipped: int
    relations_imported: int
    relations_skipped: int
    errors: List[str]


@router.post("/export")
async def export_memories(
    request: Request,
    body: ExportRequest,
) -> StreamingResponse:
    """
    Export memories and optionally graph relations to a JSON file.

    Args:
        body: Export options (include_graph, memory_types)

    Returns:
        JSON file download with memories and relations
    """
    qdrant_store = request.app.state.qdrant_store
    graph_manager = getattr(request.app.state, "graph_manager", None)
    database = getattr(request.app.state, "database", None)

    export_data: dict[str, Any] = {
        "version": "1.0",
        "exported_at": datetime.utcnow().isoformat(),
        "memories": [],
        "relations": [],
    }

    # Export memories from Qdrant
    for collection in body.memory_types:
        try:
            offset = None
            while True:
                points, next_offset = await qdrant_store.scroll(
                    collection=collection,
                    limit=500,
                    offset=offset,
                    with_vectors=False,
                )

                for point in points:
                    # Skip chunks, only export main memories
                    if point.payload.get("chunk_index", 0) > 0:
                        continue

                    memory_data = {
                        "id": point.id,
                        "memory_type": collection,
                        "content": point.payload.get("full_content", point.payload.get("content", "")),
                        "tags": point.payload.get("tags", []),
                        "importance": point.payload.get("importance", 0.5),
                        "created_at": point.payload.get("created_at"),
                        "updated_at": point.payload.get("updated_at"),
                        "context": point.payload.get("context"),
                        "access_count": point.payload.get("access_count", 0),
                    }
                    export_data["memories"].append(memory_data)

                if next_offset is None or len(points) == 0:
                    break
                offset = next_offset

        except Exception as e:
            logger.warning(f"Could not export collection {collection}: {e}")
            continue

    # Export graph relations if requested
    if body.include_graph and database:
        try:
            rows = await database.fetch(
                """
                SELECT
                    id, source_id, target_id, relation_type,
                    weight, created_by, metadata, created_at
                FROM memory_relations
                ORDER BY created_at
                """
            )

            for row in rows:
                relation_data = {
                    "id": str(row["id"]),
                    "source_id": str(row["source_id"]),
                    "target_id": str(row["target_id"]),
                    "relation_type": row["relation_type"],
                    "weight": row["weight"],
                    "created_by": row["created_by"],
                    "metadata": row["metadata"] if isinstance(row["metadata"], dict) else {},
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                }
                export_data["relations"].append(relation_data)

        except Exception as e:
            logger.warning(f"Could not export relations: {e}")

    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"memoria_backup_{timestamp}.json"

    # Create JSON bytes
    json_bytes = json.dumps(export_data, indent=2, default=str).encode("utf-8")
    buffer = BytesIO(json_bytes)

    return StreamingResponse(
        buffer,
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Content-Length": str(len(json_bytes)),
        },
    )


@router.post("/import")
async def import_memories(
    request: Request,
    file: UploadFile = File(...),
    skip_existing: bool = True,
) -> ImportResult:
    """
    Import memories and graph relations from a JSON backup file.

    Args:
        file: JSON backup file to import
        skip_existing: If True, skip memories that already exist

    Returns:
        Import statistics and errors
    """
    memory_manager = request.app.state.memory_manager
    graph_manager = getattr(request.app.state, "graph_manager", None)
    database = getattr(request.app.state, "database", None)

    # Read and parse the file
    try:
        content = await file.read()
        data = json.loads(content.decode("utf-8"))
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON file: {e}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read file: {e}")

    # Validate format
    if "memories" not in data:
        raise HTTPException(status_code=400, detail="Invalid backup format: missing 'memories' key")

    result = ImportResult(
        memories_imported=0,
        memories_skipped=0,
        relations_imported=0,
        relations_skipped=0,
        errors=[],
    )

    # Import memories
    for memory_data in data.get("memories", []):
        try:
            memory_id = memory_data.get("id")
            memory_type = memory_data.get("memory_type", "semantic")
            content = memory_data.get("content", "")
            tags = memory_data.get("tags", [])
            importance = memory_data.get("importance", 0.5)
            context = memory_data.get("context")

            if not content:
                continue

            # Check if memory exists
            if skip_existing and memory_id:
                try:
                    existing = await memory_manager.vector_store.get(
                        collection=memory_type,
                        ids=[memory_id],
                    )
                    if existing:
                        result.memories_skipped += 1
                        continue
                except Exception:
                    pass  # Memory doesn't exist, proceed to import

            # Store the memory
            await memory_manager.store(
                content=content,
                memory_type=memory_type,
                tags=tags,
                importance=importance,
                context=context,
            )
            result.memories_imported += 1

        except Exception as e:
            result.errors.append(f"Memory import error: {str(e)[:100]}")

    # Import relations
    if graph_manager and database and "relations" in data:
        for relation_data in data.get("relations", []):
            try:
                source_id = relation_data.get("source_id")
                target_id = relation_data.get("target_id")
                relation_type = relation_data.get("relation_type")
                weight = relation_data.get("weight", 1.0)
                created_by = relation_data.get("created_by", "system")

                if not all([source_id, target_id, relation_type]):
                    continue

                # Check if relation exists
                if skip_existing:
                    try:
                        existing = await database.fetchrow(
                            """
                            SELECT id FROM memory_relations
                            WHERE source_id = $1::uuid AND target_id = $2::uuid AND relation_type = $3
                            """,
                            source_id,
                            target_id,
                            relation_type,
                        )
                        if existing:
                            result.relations_skipped += 1
                            continue
                    except Exception:
                        pass

                # Import relation
                from ...core.graph_types import RelationType, RelationCreator

                await graph_manager.add_relation(
                    source_id=source_id,
                    target_id=target_id,
                    relation_type=RelationType(relation_type),
                    weight=weight,
                    created_by=RelationCreator(created_by) if created_by in ["user", "auto", "system"] else RelationCreator.SYSTEM,
                )
                result.relations_imported += 1

            except Exception as e:
                result.errors.append(f"Relation import error: {str(e)[:100]}")

    return result


@router.get("/stats")
async def get_backup_stats(request: Request) -> ExportStats:
    """
    Get statistics about what would be exported.

    Returns:
        Counts of memories, relations, and unique tags
    """
    qdrant_store = request.app.state.qdrant_store
    database = getattr(request.app.state, "database", None)

    memories_count = 0
    all_tags: set = set()
    relations_count = 0

    # Count memories
    for collection in ["episodic", "semantic", "procedural"]:
        try:
            count = await qdrant_store.count(collection=collection)
            memories_count += count

            # Get tags
            offset = None
            while True:
                points, next_offset = await qdrant_store.scroll(
                    collection=collection,
                    limit=500,
                    offset=offset,
                    with_vectors=False,
                )

                for point in points:
                    if point.payload.get("chunk_index", 0) == 0:
                        all_tags.update(point.payload.get("tags", []))

                if next_offset is None or len(points) == 0:
                    break
                offset = next_offset

        except Exception:
            continue

    # Count relations
    if database:
        try:
            row = await database.fetchrow("SELECT COUNT(*) as count FROM memory_relations")
            relations_count = row["count"] if row else 0
        except Exception:
            pass

    return ExportStats(
        memories_count=memories_count,
        relations_count=relations_count,
        tags_count=len(all_tags),
        exported_at=datetime.utcnow().isoformat(),
    )
