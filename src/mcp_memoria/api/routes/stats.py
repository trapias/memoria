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

    # Get memory stats
    memory_stats = await memory_manager.get_stats()

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

    return {
        "total_memories": memory_stats.get("total", 0),
        "by_type": {
            "episodic": memory_stats.get("episodic", 0),
            "semantic": memory_stats.get("semantic", 0),
            "procedural": memory_stats.get("procedural", 0),
        },
        "total_relations": total_relations,
    }
