"""
Memory-related API endpoints.
"""

from typing import Optional, List
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()


class MemoryResponse(BaseModel):
    """Memory response model."""
    id: str
    content: str
    memory_type: str
    tags: List[str]
    importance: float
    created_at: str
    updated_at: str
    has_relations: Optional[bool] = None


class MemoryListResponse(BaseModel):
    """Paginated memory list response."""
    memories: List[MemoryResponse]
    total: int
    offset: int
    limit: int
    has_more: bool


class ConsolidationPreview(BaseModel):
    """Preview of consolidation/forgetting operation."""
    operation: str
    merged_count: int = 0
    forgotten_count: int = 0
    updated_count: int = 0
    total_processed: int = 0
    duration_seconds: float = 0.0
    is_preview: bool = True


class ConsolidationRequest(BaseModel):
    """Request for consolidation operations."""
    operation: str = "consolidate"  # consolidate, forget, decay
    memory_type: str = "semantic"
    similarity_threshold: float = 0.9
    max_age_days: int = 30
    min_importance: float = 0.3
    dry_run: bool = True


@router.get("/list")
async def list_memories(
    request: Request,
    memory_type: Optional[str] = None,
    tags: Optional[str] = None,
    query: Optional[str] = None,
    text_match: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> MemoryListResponse:
    """
    List memories with pagination and filtering.

    Args:
        memory_type: Filter by type (episodic, semantic, procedural)
        tags: Comma-separated list of tags to filter by
        query: Semantic search query (optional)
        text_match: Keyword filter that must appear in content
        limit: Max results per page (default 20)
        offset: Pagination offset
        sort_by: Sort field (created_at, updated_at, importance)
        sort_order: Sort direction (asc, desc)
    """
    qdrant_store = request.app.state.qdrant_store
    memory_manager = request.app.state.memory_manager

    # Determine which collections to search
    collections = ["episodic", "semantic", "procedural"]
    if memory_type:
        collections = [memory_type]

    # Parse tags if provided
    tag_list = None
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    all_memories: List[MemoryResponse] = []

    try:
        # If we have a semantic query, use search
        if query:
            results = await memory_manager.search(
                query=query,
                memory_type=memory_type,
                tags=tag_list,
                limit=limit + offset + 100,  # Get extra for filtering
                text_match=text_match,
            )
            for r in results:
                m = r.memory  # RecallResult contains memory: MemoryItem
                all_memories.append(MemoryResponse(
                    id=m.id,
                    content=m.content,
                    memory_type=m.memory_type.value if hasattr(m.memory_type, 'value') else str(m.memory_type),
                    tags=m.tags,
                    importance=m.importance,
                    created_at=m.created_at.isoformat() if hasattr(m.created_at, 'isoformat') else str(m.created_at),
                    updated_at=m.updated_at.isoformat() if hasattr(m.updated_at, 'isoformat') else str(m.updated_at),
                    has_relations=False,  # Would need separate graph query
                ))
        else:
            # Scroll through collections for list view
            for collection in collections:
                try:
                    scroll_offset = None
                    while True:
                        points, next_offset = await qdrant_store.scroll(
                            collection=collection,
                            limit=500,
                            offset=scroll_offset,
                            with_vectors=False,
                        )

                        for point in points:
                            payload = point.payload
                            # Apply text match filter
                            if text_match and text_match.lower() not in payload.get("content", "").lower():
                                continue
                            # Apply tag filter
                            if tag_list:
                                point_tags = payload.get("tags", [])
                                if not any(t in point_tags for t in tag_list):
                                    continue
                            # Skip chunks, only include main memories
                            if payload.get("chunk_index", 0) > 0:
                                continue

                            all_memories.append(MemoryResponse(
                                id=point.id,
                                content=payload.get("full_content", payload.get("content", "")),
                                memory_type=collection,
                                tags=payload.get("tags", []),
                                importance=payload.get("importance", 0.5),
                                created_at=payload.get("created_at", ""),
                                updated_at=payload.get("updated_at", ""),
                                has_relations=payload.get("has_relations", False),
                            ))

                        if next_offset is None or len(points) == 0:
                            break
                        scroll_offset = next_offset

                except Exception as e:
                    # Collection might not exist
                    continue

        # Sort results
        reverse = sort_order == "desc"
        if sort_by == "importance":
            all_memories.sort(key=lambda m: m.importance, reverse=reverse)
        elif sort_by == "updated_at":
            all_memories.sort(key=lambda m: m.updated_at, reverse=reverse)
        else:  # created_at
            all_memories.sort(key=lambda m: m.created_at, reverse=reverse)

        # Calculate total before pagination
        total = len(all_memories)

        # Apply pagination
        paginated = all_memories[offset:offset + limit]

        return MemoryListResponse(
            memories=paginated,
            total=total,
            offset=offset,
            limit=limit,
            has_more=offset + limit < total,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tags")
async def get_all_tags(request: Request) -> dict:
    """
    Get all unique tags used across memories.
    """
    qdrant_store = request.app.state.qdrant_store
    collections = ["episodic", "semantic", "procedural"]
    all_tags: set = set()

    try:
        for collection in collections:
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
                        tags = point.payload.get("tags", [])
                        all_tags.update(tags)

                    if next_offset is None or len(points) == 0:
                        break
                    offset = next_offset

            except Exception:
                continue

        return {"tags": sorted(list(all_tags))}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{memory_id}")
async def delete_memory(request: Request, memory_id: str) -> dict:
    """
    Delete a memory by ID.

    Args:
        memory_id: The memory UUID
    """
    memory_manager = request.app.state.memory_manager

    try:
        success = await memory_manager.delete(memory_id)
        if success:
            # Also delete graph relations if available
            graph_manager = getattr(request.app.state, "graph_manager", None)
            if graph_manager:
                try:
                    await graph_manager.delete_memory_relations(memory_id)
                except Exception:
                    pass  # Non-critical

            return {"status": "deleted", "id": memory_id}
        else:
            raise HTTPException(status_code=404, detail="Memory not found")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{memory_id}")
async def update_memory(
    request: Request,
    memory_id: str,
    content: Optional[str] = None,
    tags: Optional[List[str]] = None,
    importance: Optional[float] = None,
) -> MemoryResponse:
    """
    Update a memory's content, tags, or importance.

    Args:
        memory_id: The memory UUID
        content: New content (optional)
        tags: New tags list (optional)
        importance: New importance value (optional)
    """
    memory_manager = request.app.state.memory_manager

    try:
        # Get current memory
        result = await memory_manager.search(memory_id=memory_id, limit=1)
        if not result:
            raise HTTPException(status_code=404, detail="Memory not found")

        m = result[0]

        # Build update payload
        updates = {}
        if content is not None:
            updates["content"] = content
        if tags is not None:
            updates["tags"] = tags
        if importance is not None:
            updates["importance"] = importance

        if updates:
            await memory_manager.update(memory_id, **updates)

        # Refetch updated memory
        result = await memory_manager.search(memory_id=memory_id, limit=1)
        m = result[0]

        return MemoryResponse(
            id=m.id,
            content=m.content,
            memory_type=m.memory_type.value if hasattr(m.memory_type, 'value') else str(m.memory_type),
            tags=m.tags,
            importance=m.importance,
            created_at=m.created_at.isoformat() if hasattr(m.created_at, 'isoformat') else str(m.created_at),
            updated_at=m.updated_at.isoformat() if hasattr(m.updated_at, 'isoformat') else str(m.updated_at),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
async def search_memories(
    request: Request,
    query: str,
    memory_type: Optional[str] = None,
    limit: int = 10,
) -> List[MemoryResponse]:
    """
    Search memories semantically.

    Args:
        query: Search query text
        memory_type: Optional filter by memory type (episodic, semantic, procedural)
        limit: Maximum number of results
    """
    memory_manager = request.app.state.memory_manager

    # Convert single memory_type to list for recall
    memory_types = [memory_type] if memory_type else None

    results = await memory_manager.recall(
        query=query,
        memory_types=memory_types,
        limit=limit,
    )

    return [
        MemoryResponse(
            id=r.memory.id,
            content=r.memory.content,
            memory_type=r.memory.memory_type.value if hasattr(r.memory.memory_type, 'value') else str(r.memory.memory_type),
            tags=r.memory.tags,
            importance=r.memory.importance,
            created_at=r.memory.created_at.isoformat() if hasattr(r.memory.created_at, 'isoformat') else str(r.memory.created_at),
            updated_at=r.memory.updated_at.isoformat() if hasattr(r.memory.updated_at, 'isoformat') else str(r.memory.updated_at),
        )
        for r in results
    ]


@router.get("/{memory_id}")
async def get_memory(request: Request, memory_id: str) -> MemoryResponse:
    """
    Get a single memory by ID.

    Args:
        memory_id: The memory UUID
    """
    from mcp_memoria.core.memory_types import MemoryType

    memory_manager = request.app.state.memory_manager

    # Try each memory type until we find it
    for memory_type in MemoryType:
        m = await memory_manager.get(memory_id=memory_id, memory_type=memory_type)
        if m:
            return MemoryResponse(
                id=m.id,
                content=m.content,
                memory_type=m.memory_type.value if hasattr(m.memory_type, 'value') else str(m.memory_type),
                tags=m.tags,
                importance=m.importance,
                created_at=m.created_at.isoformat() if hasattr(m.created_at, 'isoformat') else str(m.created_at),
                updated_at=m.updated_at.isoformat() if hasattr(m.updated_at, 'isoformat') else str(m.updated_at),
            )

    raise HTTPException(status_code=404, detail="Memory not found")


@router.post("/consolidate")
async def consolidate_memories(
    request: Request,
    body: ConsolidationRequest,
) -> ConsolidationPreview:
    """
    Run memory consolidation, forgetting, or decay operations.

    Use dry_run=True to preview what would happen without making changes.

    Args:
        body: Consolidation parameters (operation, dry_run, thresholds)
    """
    memory_manager = request.app.state.memory_manager
    consolidator = memory_manager.consolidator

    try:
        if body.operation == "consolidate":
            result = await consolidator.consolidate(
                collection=body.memory_type,
                similarity_threshold=body.similarity_threshold,
                dry_run=body.dry_run,
            )
            return ConsolidationPreview(
                operation="consolidate",
                merged_count=result.merged_count,
                total_processed=result.total_processed,
                duration_seconds=result.duration_seconds,
                is_preview=body.dry_run,
            )

        elif body.operation == "forget":
            result = await consolidator.apply_forgetting(
                collection=body.memory_type,
                max_age_days=body.max_age_days,
                min_importance=body.min_importance,
                dry_run=body.dry_run,
            )
            return ConsolidationPreview(
                operation="forget",
                forgotten_count=result.forgotten_count,
                total_processed=result.total_processed,
                duration_seconds=result.duration_seconds,
                is_preview=body.dry_run,
            )

        elif body.operation == "decay":
            result = await consolidator.decay_importance(
                collection=body.memory_type,
                dry_run=body.dry_run,
            )
            return ConsolidationPreview(
                operation="decay",
                updated_count=result.updated_count,
                total_processed=result.total_processed,
                duration_seconds=result.duration_seconds,
                is_preview=body.dry_run,
            )

        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown operation: {body.operation}. Use 'consolidate', 'forget', or 'decay'."
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
