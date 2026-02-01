"""
Statistics API endpoints.
"""

from typing import Dict, Any
from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/stats")
async def get_stats(request: Request) -> Dict[str, Any]:
    """
    Get memory and graph statistics.

    Returns total memories by type and total relations.
    """
    memory_manager = request.app.state.memory_manager
    graph_manager = getattr(request.app.state, "graph_manager", None)

    # Get memory stats (sync method)
    memory_stats = memory_manager.get_stats()

    # Get relation count from graph manager (if available)
    total_relations = 0
    if graph_manager:
        try:
            # Count relations in the database
            database = getattr(request.app.state, "database", None)
            if database:
                async with database.pool.acquire() as conn:
                    result = await conn.fetchval(
                        "SELECT COUNT(*) FROM memory_relations"
                    )
                    total_relations = result or 0
        except Exception:
            pass

    # Extract counts from collections dict
    collections = memory_stats.get("collections", {})

    return {
        "total_memories": memory_stats.get("total_memories", 0),
        "by_type": {
            "episodic": collections.get("episodic", {}).get("points_count", 0),
            "semantic": collections.get("semantic", {}).get("points_count", 0),
            "procedural": collections.get("procedural", {}).get("points_count", 0),
        },
        "total_relations": total_relations,
    }
