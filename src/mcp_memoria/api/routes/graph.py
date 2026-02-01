"""
Knowledge Graph API endpoints.
"""

from typing import Optional, List, Any
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field

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


class DiscoverRelationsRequest(BaseModel):
    """Request to discover relations globally."""

    limit: int = Field(default=50, ge=1, le=200)
    min_confidence: float = Field(default=0.70, ge=0.0, le=1.0)
    auto_accept_threshold: float = Field(default=0.90, ge=0.0, le=1.0)
    skip_with_relations: bool = True
    memory_types: Optional[List[str]] = None


class DiscoverySuggestion(BaseModel):
    """A suggestion from global discovery."""

    source_id: str
    source_preview: str
    source_type: Optional[str]
    target_id: str
    target_preview: str
    target_type: Optional[str]
    relation_type: str
    confidence: float
    reason: str
    shared_tags: List[str]


class DiscoverRelationsResponse(BaseModel):
    """Response from global discovery."""

    suggestions: List[DiscoverySuggestion]
    auto_accepted: int
    scanned_count: int
    total_without_relations: int


class BulkRelationItem(BaseModel):
    """Single relation for bulk creation."""

    source_id: str
    target_id: str
    relation_type: str


class BulkRelationsRequest(BaseModel):
    """Request to create relations in bulk."""

    relations: List[BulkRelationItem]
    created_by: str = "auto"  # "user" or "auto"


class BulkRelationsResponse(BaseModel):
    """Response from bulk relation creation."""

    created: int
    duplicates: int
    errors: int


class RejectSuggestionRequest(BaseModel):
    """Request to reject a suggestion."""

    source_id: str
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


@router.get("/overview")
async def get_graph_overview(
    request: Request,
    limit: int = 10,
    depth: int = 2,
) -> SubgraphResponse:
    """
    Get a graph overview showing the most connected memories.

    Returns a subgraph centered on memories with the most relations,
    useful for showing an initial visualization without requiring a search.

    Args:
        limit: Maximum number of hub memories to include (1-20)
        depth: Traversal depth from each hub (1-3)
    """
    graph_manager = get_graph_manager(request)

    # Clamp parameters
    limit = max(1, min(limit, 20))
    depth = max(1, min(depth, 3))

    try:
        subgraph = await graph_manager.get_graph_overview(limit=limit, depth=depth)

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


# ─────────────────────────────────────────────────────────────────────────────
# Global Discovery Endpoints
# ─────────────────────────────────────────────────────────────────────────────


@router.post("/discover")
async def discover_relations(
    request: Request,
    body: DiscoverRelationsRequest,
) -> DiscoverRelationsResponse:
    """
    Discover potential relations across all memories.

    Scans memories and suggests relations based on vector similarity
    and content heuristics. Can auto-accept high-confidence suggestions.

    Args:
        body: Discovery parameters (limit, confidence thresholds, filters)
    """
    graph_manager = get_graph_manager(request)

    # Get rejected suggestions to exclude
    rejected_pairs: set[tuple[str, str, str]] = set()
    database = getattr(request.app.state, "database", None)
    if database:
        try:
            from ...db.repositories import RejectedSuggestionRepository
            rejected_repo = RejectedSuggestionRepository(database)
            rejected = await rejected_repo.get_all()
            rejected_pairs = {
                (str(r["source_id"]), str(r["target_id"]), r["relation_type"])
                for r in rejected
            }
        except Exception:
            pass  # Repository may not exist yet

    try:
        result = await graph_manager.discover_relations_global(
            limit=body.limit,
            min_confidence=body.min_confidence,
            auto_accept_threshold=body.auto_accept_threshold,
            skip_with_relations=body.skip_with_relations,
            memory_types=body.memory_types,
            rejected_pairs=rejected_pairs,
        )

        suggestions = [
            DiscoverySuggestion(
                source_id=s["source_id"],
                source_preview=s["source_preview"],
                source_type=s.get("source_type"),
                target_id=s["target_id"],
                target_preview=s["target_preview"],
                target_type=s.get("target_type"),
                relation_type=s["relation_type"],
                confidence=s["confidence"],
                reason=s["reason"],
                shared_tags=s.get("shared_tags", []),
            )
            for s in result["suggestions"]
        ]

        return DiscoverRelationsResponse(
            suggestions=suggestions,
            auto_accepted=result["auto_accepted"],
            scanned_count=result["scanned_count"],
            total_without_relations=result["total_without_relations"],
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/relations/bulk")
async def create_relations_bulk(
    request: Request,
    body: BulkRelationsRequest,
) -> BulkRelationsResponse:
    """
    Create multiple relations in bulk.

    Args:
        body: List of relations to create
    """
    graph_manager = get_graph_manager(request)

    from ...core.graph_types import RelationCreator

    creator = RelationCreator.AUTO if body.created_by == "auto" else RelationCreator.USER

    try:
        result = await graph_manager.add_relations_bulk(
            relations=[r.model_dump() for r in body.relations],
            created_by=creator,
        )

        return BulkRelationsResponse(
            created=result["created"],
            duplicates=result["duplicates"],
            errors=result["errors"],
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/suggestions/reject")
async def reject_suggestion(
    request: Request,
    body: RejectSuggestionRequest,
) -> dict:
    """
    Reject a suggestion to prevent it from being suggested again.

    Args:
        body: Suggestion details (source_id, target_id, relation_type)
    """
    database = getattr(request.app.state, "database", None)
    if not database:
        raise HTTPException(
            status_code=503,
            detail="Database not available for storing rejected suggestions",
        )

    try:
        from ...db.repositories import RejectedSuggestionRepository
        repo = RejectedSuggestionRepository(database)
        await repo.create(
            source_id=body.source_id,
            target_id=body.target_id,
            relation_type=body.relation_type,
        )
        return {"status": "rejected"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
