"""
Memory-related API endpoints.
"""

from typing import Optional, List
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

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

    results = await memory_manager.recall(
        query=query,
        memory_type=memory_type,
        limit=limit,
    )

    return [
        MemoryResponse(
            id=m.id,
            content=m.content,
            memory_type=m.memory_type.value if hasattr(m.memory_type, 'value') else str(m.memory_type),
            tags=m.tags,
            importance=m.importance,
            created_at=m.created_at.isoformat() if hasattr(m.created_at, 'isoformat') else str(m.created_at),
            updated_at=m.updated_at.isoformat() if hasattr(m.updated_at, 'isoformat') else str(m.updated_at),
        )
        for m in results
    ]


@router.get("/{memory_id}")
async def get_memory(request: Request, memory_id: str) -> MemoryResponse:
    """
    Get a single memory by ID.

    Args:
        memory_id: The memory UUID
    """
    memory_manager = request.app.state.memory_manager

    # Search for exact match
    results = await memory_manager.search(
        memory_id=memory_id,
        limit=1,
    )

    if not results:
        raise HTTPException(status_code=404, detail="Memory not found")

    m = results[0]
    return MemoryResponse(
        id=m.id,
        content=m.content,
        memory_type=m.memory_type.value if hasattr(m.memory_type, 'value') else str(m.memory_type),
        tags=m.tags,
        importance=m.importance,
        created_at=m.created_at.isoformat() if hasattr(m.created_at, 'isoformat') else str(m.created_at),
        updated_at=m.updated_at.isoformat() if hasattr(m.updated_at, 'isoformat') else str(m.updated_at),
    )
