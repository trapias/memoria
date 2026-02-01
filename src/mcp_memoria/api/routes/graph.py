"""
Knowledge Graph API endpoints.
"""

from typing import Optional, List
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Response Models
# ─────────────────────────────────────────────────────────────────────────────


class GraphNodeResponse(BaseModel):
    """Graph node for visualization."""

    id: str
    label: str
    type: Optional[str] = None
    importance: float
    tags: List[str]
    isCenter: bool
    depth: Optional[int] = None


class GraphEdgeResponse(BaseModel):
    """Graph edge for visualization."""

    source: str
    target: str
    type: str
    weight: float
    created_by: str


class SubgraphResponse(BaseModel):
    """Subgraph for visualization."""

    nodes: List[GraphNodeResponse]
    edges: List[GraphEdgeResponse]


class RelationResponse(BaseModel):
    """Relation between memories."""

    id: str
    source_id: str
    target_id: str
    type: str
    weight: float
    created_at: str
    created_by: str
    metadata: dict


class RelationSuggestionResponse(BaseModel):
    """AI-suggested relation."""

    target_id: str
    target_content: str
    target_tags: List[str]
    target_type: Optional[str]
    suggested_type: str
    confidence: float
    reason: str


class PathStepResponse(BaseModel):
    """Step in a graph path."""

    memory_id: str
    relation: Optional[str]
    direction: Optional[str]
    content: Optional[str] = None


class GraphPathResponse(BaseModel):
    """Path between two memories."""

    from_id: str = ""
    to_id: str = ""
    found: bool
    length: int
    steps: List[PathStepResponse]
    total_weight: float = 0.0


class CreateRelationRequest(BaseModel):
    """Request to create a relation."""

    source_id: str
    target_id: str
    relation_type: str
    weight: float = 1.0


class AcceptSuggestionRequest(BaseModel):
    """Request to accept a suggestion."""

    target_id: str
    relation_type: str


# ─────────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────────


def get_graph_manager(request: Request):
    """Get graph manager or raise 503 if unavailable."""
    graph_manager = getattr(request.app.state, "graph_manager", None)
    if not graph_manager:
        raise HTTPException(
            status_code=503,
            detail="Knowledge graph not available. PostgreSQL connection required.",
        )
    return graph_manager


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/subgraph/{center_id}")
async def get_subgraph(
    request: Request,
    center_id: str,
    depth: int = 2,
) -> SubgraphResponse:
    """
    Get subgraph centered on a memory for visualization.

    Args:
        center_id: Memory ID to center the graph on
        depth: Traversal depth (1-4)
    """
    graph_manager = get_graph_manager(request)

    try:
        subgraph = await graph_manager.get_subgraph(center_id, depth=depth)

        nodes = [
            GraphNodeResponse(
                id=n.id,
                label=n.label,
                type=n.memory_type,
                importance=n.importance,
                tags=n.tags,
                isCenter=n.is_center,
                depth=n.depth,
            )
            for n in subgraph.nodes
        ]

        edges = [
            GraphEdgeResponse(
                source=e.source,
                target=e.target,
                type=e.relation_type.value,
                weight=e.weight,
                created_by=e.created_by.value,
            )
            for e in subgraph.edges
        ]

        return SubgraphResponse(nodes=nodes, edges=edges)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/neighbors/{memory_id}")
async def get_neighbors(
    request: Request,
    memory_id: str,
    depth: int = 1,
    relation_types: Optional[str] = None,
    direction: str = "both",
) -> dict:
    """
    Get neighboring memories up to N hops away.

    Args:
        memory_id: Center memory ID
        depth: Maximum traversal depth (1-5)
        relation_types: Comma-separated relation types to filter
        direction: Traversal direction (outgoing, incoming, both)
    """
    graph_manager = get_graph_manager(request)

    # Parse relation types
    rel_types = None
    if relation_types:
        from ...core.graph_types import RelationType

        rel_types = [RelationType(t.strip()) for t in relation_types.split(",")]

    try:
        neighbors = await graph_manager.get_neighbors(
            memory_id,
            depth=depth,
            relation_types=rel_types,
            include_content=True,
        )

        # Convert to response format
        neighbor_nodes = [
            GraphNodeResponse(
                id=n["memory_id"],
                label=n.get("content", "")[:50] if n.get("content") else n["memory_id"][:8],
                type=n.get("memory_type"),
                importance=0.5,
                tags=n.get("tags", []),
                isCenter=False,
                depth=n["depth"],
            )
            for n in neighbors
        ]

        return {
            "center": memory_id,
            "depth": depth,
            "neighbors": [n.model_dump() for n in neighbor_nodes],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/path")
async def find_path(
    request: Request,
    from_id: str,
    to_id: str,
    max_depth: int = 5,
) -> GraphPathResponse:
    """
    Find shortest path between two memories.

    Args:
        from_id: Starting memory ID
        to_id: Target memory ID
        max_depth: Maximum path length
    """
    graph_manager = get_graph_manager(request)

    try:
        path = await graph_manager.find_path(from_id, to_id, max_depth=max_depth)

        if not path or not path.steps:
            return GraphPathResponse(
                from_id=from_id,
                to_id=to_id,
                found=False,
                length=0,
                steps=[],
                total_weight=0,
            )

        steps = [
            PathStepResponse(
                memory_id=s.memory_id,
                relation=s.relation_type.value if s.relation_type else None,
                direction=s.direction,
            )
            for s in path.steps
        ]

        return GraphPathResponse(
            from_id=from_id,
            to_id=to_id,
            found=True,
            length=len(steps),
            steps=steps,
            total_weight=sum(1.0 for _ in steps),  # Simplified
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/memories/{memory_id}/relations")
async def get_relations(
    request: Request,
    memory_id: str,
    direction: str = "both",
    relation_type: Optional[str] = None,
) -> dict:
    """
    Get all relations for a memory.

    Args:
        memory_id: Memory ID
        direction: Filter by direction (outgoing, incoming, both)
        relation_type: Filter by relation type
    """
    graph_manager = get_graph_manager(request)

    from ...core.graph_types import RelationDirection, RelationType

    # Map direction
    dir_map = {
        "outgoing": RelationDirection.OUTGOING,
        "incoming": RelationDirection.INCOMING,
        "both": RelationDirection.BOTH,
    }
    rel_dir = dir_map.get(direction, RelationDirection.BOTH)

    # Parse relation type
    rel_type = RelationType(relation_type) if relation_type else None

    try:
        relations = await graph_manager.get_relations(
            memory_id,
            direction=rel_dir,
            relation_type=rel_type,
        )

        return {
            "memory_id": memory_id,
            "relations": [
                RelationResponse(
                    id=str(r.id),
                    source_id=str(r.source_id),
                    target_id=str(r.target_id),
                    type=r.relation_type.value,
                    weight=r.weight,
                    created_at=r.created_at.isoformat(),
                    created_by=r.created_by.value,
                    metadata=r.metadata or {},
                ).model_dump()
                for r in relations
            ],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/relations")
async def create_relation(
    request: Request,
    body: CreateRelationRequest,
) -> dict:
    """
    Create a relation between two memories.

    Args:
        body: Relation details (source_id, target_id, relation_type, weight)
    """
    graph_manager = get_graph_manager(request)

    from ...core.graph_types import RelationType

    try:
        relation = await graph_manager.add_relation(
            source_id=body.source_id,
            target_id=body.target_id,
            relation_type=RelationType(body.relation_type),
            weight=body.weight,
        )

        return {
            "status": "created",
            "relation": RelationResponse(
                id=str(relation.id),
                source_id=str(relation.source_id),
                target_id=str(relation.target_id),
                type=relation.relation_type.value,
                weight=relation.weight,
                created_at=relation.created_at.isoformat(),
                created_by=relation.created_by.value,
                metadata=relation.metadata or {},
            ).model_dump(),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/relations")
async def delete_relation(
    request: Request,
    source_id: str,
    target_id: str,
    relation_type: Optional[str] = None,
) -> dict:
    """
    Delete relation(s) between two memories.

    Args:
        source_id: Source memory ID
        target_id: Target memory ID
        relation_type: Specific type to delete (None removes all)
    """
    graph_manager = get_graph_manager(request)

    from ...core.graph_types import RelationType

    rel_type = RelationType(relation_type) if relation_type else None

    try:
        count = await graph_manager.remove_relation(
            source_id=source_id,
            target_id=target_id,
            relation_type=rel_type,
        )

        return {"status": "deleted", "count": count}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/suggestions/{memory_id}")
async def get_suggestions(
    request: Request,
    memory_id: str,
    limit: int = 5,
) -> dict:
    """
    Get AI-powered relation suggestions for a memory.

    Args:
        memory_id: Memory to get suggestions for
        limit: Maximum number of suggestions
    """
    graph_manager = get_graph_manager(request)

    try:
        suggestions = await graph_manager.suggest_relations(memory_id, limit=limit)

        return {
            "memory_id": memory_id,
            "suggestions": [
                RelationSuggestionResponse(
                    target_id=s.target_id,
                    target_content=s.target_content,
                    target_tags=s.target_tags,
                    target_type=s.target_type,
                    suggested_type=s.suggested_type.value,
                    confidence=s.confidence,
                    reason=s.reason,
                ).model_dump()
                for s in suggestions
            ],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/suggestions/{memory_id}/accept")
async def accept_suggestion(
    request: Request,
    memory_id: str,
    body: AcceptSuggestionRequest,
) -> dict:
    """
    Accept a suggested relation.

    Args:
        memory_id: Source memory ID
        body: Suggestion to accept (target_id, relation_type)
    """
    graph_manager = get_graph_manager(request)

    from ...core.graph_types import RelationType

    try:
        relation = await graph_manager.add_relation(
            source_id=memory_id,
            target_id=body.target_id,
            relation_type=RelationType(body.relation_type),
        )

        return {
            "status": "accepted",
            "relation": RelationResponse(
                id=str(relation.id),
                source_id=str(relation.source_id),
                target_id=str(relation.target_id),
                type=relation.relation_type.value,
                weight=relation.weight,
                created_at=relation.created_at.isoformat(),
                created_by=relation.created_by.value,
                metadata=relation.metadata or {},
            ).model_dump(),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
