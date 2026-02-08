"""Graph manager for knowledge graph operations.

Manages relations between memories using PostgreSQL for graph storage
and Qdrant for memory content retrieval. Supports efficient traversal
via WITH RECURSIVE queries.
"""

import logging
from typing import Any
from uuid import UUID

from mcp_memoria.core.graph_types import (
    GraphEdge,
    GraphNode,
    GraphPath,
    PathStep,
    Relation,
    RelationCreator,
    RelationDirection,
    RelationSuggestion,
    RelationType,
    RelationWithContext,
    Subgraph,
)
from mcp_memoria.db import ASYNCPG_AVAILABLE
from mcp_memoria.storage.qdrant_store import QdrantStore

if ASYNCPG_AVAILABLE:
    from mcp_memoria.db import Database, MemoryRelationRepository

logger = logging.getLogger(__name__)


class GraphManagerError(Exception):
    """Base exception for graph manager operations."""

    pass


class RelationNotFoundError(GraphManagerError):
    """Raised when a relation is not found."""

    pass


class InvalidRelationError(GraphManagerError):
    """Raised when a relation is invalid."""

    pass


class GraphManager:
    """Manages knowledge graph operations for memory relations.

    Uses PostgreSQL for storing and traversing relations via WITH RECURSIVE,
    and Qdrant for fetching memory content when context is needed.

    Features:
    - CRUD operations for relations
    - Graph traversal (neighbors, paths, subgraphs)
    - AI-powered relation suggestions based on similarity
    - Integration with existing memory storage

    Example:
        graph = GraphManager(database, qdrant_store)

        # Create a relation
        relation = await graph.add_relation(
            source_id="mem-123",
            target_id="mem-456",
            relation_type=RelationType.FIXES
        )

        # Get neighbors
        neighbors = await graph.get_neighbors("mem-123", depth=2)

        # Get suggestions
        suggestions = await graph.suggest_relations("mem-123")
    """

    def __init__(
        self,
        database: "Database",
        qdrant: QdrantStore,
        default_collection: str = "semantic",
    ):
        """Initialize GraphManager.

        Args:
            database: PostgreSQL database instance
            qdrant: Qdrant store for memory content
            default_collection: Default Qdrant collection for memory lookups
        """
        if not ASYNCPG_AVAILABLE:
            raise RuntimeError(
                "PostgreSQL support required for GraphManager. "
                "Install with: pip install mcp-memoria[postgres]"
            )

        self._db = database
        self._qdrant = qdrant
        self._default_collection = default_collection
        self._repo: MemoryRelationRepository | None = None

    @property
    def repo(self) -> "MemoryRelationRepository":
        """Get or create the memory relation repository."""
        if self._repo is None:
            self._repo = MemoryRelationRepository(self._db)
        return self._repo

    # ─────────────────────────────────────────────────────────────────────────
    # CRUD Operations
    # ─────────────────────────────────────────────────────────────────────────

    async def add_relation(
        self,
        source_id: str,
        target_id: str,
        relation_type: RelationType,
        weight: float = 1.0,
        created_by: RelationCreator = RelationCreator.USER,
        metadata: dict[str, Any] | None = None,
    ) -> Relation:
        """Create a relation between two memories.

        Args:
            source_id: ID of the source memory
            target_id: ID of the target memory
            relation_type: Type of relationship
            weight: Strength of the relationship (0-1)
            created_by: Who/what created the relation
            metadata: Optional additional metadata

        Returns:
            Created Relation object

        Raises:
            InvalidRelationError: If source equals target
        """
        if source_id == target_id:
            raise InvalidRelationError("Cannot create self-referential relation")

        try:
            db_relation = await self.repo.create(
                source_id=UUID(source_id),
                target_id=UUID(target_id),
                relation_type=relation_type,
                weight=weight,
                created_by=created_by,
                metadata=metadata or {},
            )

            logger.info(
                f"Created {relation_type.value} relation: {source_id} -> {target_id}"
            )

            # Optionally mark memories as having relations in Qdrant
            await self._mark_has_relations([source_id, target_id])

            return Relation(
                id=db_relation.id,
                source_id=db_relation.source_id,
                target_id=db_relation.target_id,
                relation_type=db_relation.relation_type,
                weight=db_relation.weight,
                created_by=db_relation.created_by,
                created_at=db_relation.created_at,
                metadata=db_relation.metadata,
            )

        except Exception as e:
            logger.error(f"Failed to create relation: {e}")
            raise GraphManagerError(f"Failed to create relation: {e}") from e

    async def remove_relation(
        self,
        source_id: str,
        target_id: str,
        relation_type: RelationType | None = None,
    ) -> int:
        """Remove relation(s) between two memories.

        Args:
            source_id: ID of the source memory
            target_id: ID of the target memory
            relation_type: Specific type to remove (None removes all)

        Returns:
            Number of relations removed
        """
        try:
            # Get matching relations first
            relations = await self.repo.get_for_memory(
                memory_id=UUID(source_id),
                relation_type=relation_type,
                direction="outgoing",
            )

            # Filter to matching target
            matching = [
                r for r in relations if str(r.target_id) == target_id
            ]

            if relation_type:
                matching = [r for r in matching if r.relation_type == relation_type]

            count = 0
            for rel in matching:
                if await self.repo.delete(rel.id):
                    count += 1

            logger.info(
                f"Removed {count} relation(s) between {source_id} and {target_id}"
            )
            return count

        except Exception as e:
            logger.error(f"Failed to remove relation: {e}")
            raise GraphManagerError(f"Failed to remove relation: {e}") from e

    async def get_relations(
        self,
        memory_id: str,
        direction: RelationDirection = RelationDirection.BOTH,
        relation_type: RelationType | None = None,
        include_memory_context: bool = False,
    ) -> list[Relation | RelationWithContext]:
        """Get relations for a memory.

        Args:
            memory_id: ID of the memory
            direction: Which direction to query
            relation_type: Filter by relation type
            include_memory_context: Include linked memory content

        Returns:
            List of relations
        """
        try:
            # Map direction enum to repository format
            direction_map = {
                RelationDirection.OUTGOING: "outgoing",
                RelationDirection.INCOMING: "incoming",
                RelationDirection.BOTH: "both",
            }

            db_relations = await self.repo.get_for_memory(
                memory_id=UUID(memory_id),
                relation_type=relation_type,
                direction=direction_map[direction],
            )

            if include_memory_context:
                return await self._populate_memory_context(memory_id, db_relations)

            return [
                Relation(
                    id=r.id,
                    source_id=r.source_id,
                    target_id=r.target_id,
                    relation_type=r.relation_type,
                    weight=r.weight,
                    created_by=r.created_by,
                    created_at=r.created_at,
                    metadata=r.metadata,
                )
                for r in db_relations
            ]

        except Exception as e:
            logger.error(f"Failed to get relations: {e}")
            raise GraphManagerError(f"Failed to get relations: {e}") from e

    async def update_relation(
        self,
        source_id: str,
        target_id: str,
        relation_type: RelationType,
        weight: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Relation | None:
        """Update an existing relation.

        Args:
            source_id: ID of the source memory
            target_id: ID of the target memory
            relation_type: Type of the relation to update
            weight: New weight value
            metadata: New metadata (merged with existing)

        Returns:
            Updated Relation or None if not found
        """
        try:
            # Find the relation
            relations = await self.repo.get_for_memory(
                memory_id=UUID(source_id),
                relation_type=relation_type,
                direction="outgoing",
            )

            matching = [
                r for r in relations
                if str(r.target_id) == target_id and r.relation_type == relation_type
            ]

            if not matching:
                return None

            rel = matching[0]

            # Update weight if provided
            if weight is not None:
                updated = await self.repo.update_weight(rel.id, weight)
                return Relation(
                    id=updated.id,
                    source_id=updated.source_id,
                    target_id=updated.target_id,
                    relation_type=updated.relation_type,
                    weight=updated.weight,
                    created_by=updated.created_by,
                    created_at=updated.created_at,
                    metadata=updated.metadata,
                )

            return Relation(
                id=rel.id,
                source_id=rel.source_id,
                target_id=rel.target_id,
                relation_type=rel.relation_type,
                weight=rel.weight,
                created_by=rel.created_by,
                created_at=rel.created_at,
                metadata=rel.metadata,
            )

        except Exception as e:
            logger.error(f"Failed to update relation: {e}")
            raise GraphManagerError(f"Failed to update relation: {e}") from e

    # ─────────────────────────────────────────────────────────────────────────
    # Graph Traversal
    # ─────────────────────────────────────────────────────────────────────────

    async def get_neighbors(
        self,
        memory_id: str,
        depth: int = 1,
        relation_types: list[RelationType] | None = None,
        include_content: bool = False,
    ) -> list[dict[str, Any]]:
        """Get neighboring memories up to N hops away.

        Uses PostgreSQL WITH RECURSIVE for efficient BFS traversal,
        plus implicit project-based relations from Qdrant.

        Args:
            memory_id: Center memory ID
            depth: Maximum traversal depth (1-5)
            relation_types: Filter by relation types
            include_content: Include memory content from Qdrant

        Returns:
            List of neighbor info dicts
        """
        depth = min(max(depth, 1), 5)  # Clamp to 1-5

        try:
            db_neighbors = await self.repo.get_neighbors(
                memory_id=UUID(memory_id),
                depth=depth,
                relation_types=relation_types,
            )

            neighbors = [
                {
                    "memory_id": str(n.memory_id),
                    "depth": n.depth,
                    "path": [str(p) for p in n.path],
                    "relation": n.relation.value,
                }
                for n in db_neighbors
            ]

            # Implicit project-based relations: find memories in the same project
            if depth >= 1:
                project_neighbors = await self._get_project_neighbors(
                    memory_id=memory_id,
                    exclude_ids={n["memory_id"] for n in neighbors} | {memory_id},
                    limit=10,
                )
                neighbors.extend(project_neighbors)

            if include_content and neighbors:
                await self._populate_neighbor_content(neighbors)

            return neighbors

        except Exception as e:
            logger.error(f"Failed to get neighbors: {e}")
            raise GraphManagerError(f"Failed to get neighbors: {e}") from e

    async def _get_project_neighbors(
        self,
        memory_id: str,
        exclude_ids: set[str],
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Find memories in the same project as implicit neighbors.

        Searches Qdrant for memories sharing the same project field,
        returning them as depth-1 neighbors with 'same_project' relation.

        Args:
            memory_id: Source memory ID
            exclude_ids: Memory IDs to exclude (already in graph results)
            limit: Maximum implicit neighbors to return

        Returns:
            List of neighbor info dicts with relation='same_project'
        """
        try:
            # Try each collection to find the source memory's project
            project = None
            for collection in ["episodic", "semantic", "procedural"]:
                try:
                    source_results = await self._qdrant.get(
                        collection=collection,
                        ids=[memory_id],
                    )
                    if source_results:
                        project = source_results[0].payload.get("project")
                        break
                except Exception:
                    continue

            if not project:
                return []

            # Search all collections for memories with the same project
            implicit = []
            for collection in ["episodic", "semantic", "procedural"]:
                try:
                    points, _ = await self._qdrant.scroll(
                        collection=collection,
                        filter_conditions={"project": project},
                        limit=limit,
                    )
                    for point in points:
                        pid = str(point.id)
                        if pid not in exclude_ids:
                            implicit.append({
                                "memory_id": pid,
                                "depth": 1,
                                "path": [memory_id, pid],
                                "relation": "same_project",
                                "implicit": True,
                                "project": project,
                            })
                            exclude_ids.add(pid)
                except Exception:
                    continue

            return implicit[:limit]

        except Exception as e:
            logger.debug(f"Could not fetch project neighbors: {e}")
            return []

    async def find_path(
        self,
        from_id: str,
        to_id: str,
        max_depth: int = 5,
    ) -> GraphPath | None:
        """Find shortest path between two memories.

        Uses PostgreSQL WITH RECURSIVE for efficient pathfinding.

        Args:
            from_id: Starting memory ID
            to_id: Target memory ID
            max_depth: Maximum path length

        Returns:
            GraphPath if found, None otherwise
        """
        max_depth = min(max(max_depth, 1), 10)  # Clamp to 1-10

        try:
            db_path = await self.repo.find_path(
                from_id=UUID(from_id),
                to_id=UUID(to_id),
                max_depth=max_depth,
            )

            if not db_path:
                return GraphPath(from_id=from_id, to_id=to_id, steps=[])

            steps = [
                PathStep(
                    memory_id=str(p.memory_id),
                    relation_type=p.relation,
                    direction=p.direction,
                )
                for p in db_path
            ]

            return GraphPath(
                from_id=from_id,
                to_id=to_id,
                steps=steps,
            )

        except Exception as e:
            logger.error(f"Failed to find path: {e}")
            raise GraphManagerError(f"Failed to find path: {e}") from e

    async def get_subgraph(
        self,
        center_id: str,
        depth: int = 2,
        relation_types: list[RelationType] | None = None,
    ) -> Subgraph:
        """Extract subgraph for visualization.

        Combines PostgreSQL (relations) and Qdrant (memory content)
        to build a visualization-ready graph structure.

        Args:
            center_id: Center memory ID
            depth: Depth of subgraph (1-4)
            relation_types: Filter by relation types

        Returns:
            Subgraph with nodes and edges
        """
        depth = min(max(depth, 1), 4)  # Clamp to 1-4

        try:
            # Get all neighbors via WITH RECURSIVE
            neighbors = await self.get_neighbors(
                memory_id=center_id,
                depth=depth,
                relation_types=relation_types,
            )

            # Collect all memory IDs
            memory_ids = [center_id] + [n["memory_id"] for n in neighbors]
            unique_ids = list(set(memory_ids))

            # Fetch memory details from Qdrant
            nodes = await self._build_nodes(
                memory_ids=unique_ids,
                center_id=center_id,
                neighbors=neighbors,
            )

            # Get edges from PostgreSQL
            edges = await self._build_edges(unique_ids)

            return Subgraph(
                center_id=center_id,
                depth=depth,
                nodes=nodes,
                edges=edges,
            )

        except Exception as e:
            logger.error(f"Failed to get subgraph: {e}")
            raise GraphManagerError(f"Failed to get subgraph: {e}") from e

    # ─────────────────────────────────────────────────────────────────────────
    # AI-Powered Suggestions
    # ─────────────────────────────────────────────────────────────────────────

    async def suggest_relations(
        self,
        memory_id: str,
        limit: int = 5,
        min_similarity: float = 0.75,
        collection: str | None = None,
    ) -> list[RelationSuggestion]:
        """Suggest relations based on content similarity and heuristics.

        Uses Qdrant vector search to find similar memories,
        then applies heuristics to infer relation types.

        Args:
            memory_id: Source memory ID
            limit: Maximum suggestions to return
            min_similarity: Minimum similarity score threshold
            collection: Qdrant collection to search

        Returns:
            List of RelationSuggestion objects
        """
        collection = collection or self._default_collection

        try:
            # Get source memory with vector
            source_results = await self._qdrant.get(
                collection=collection,
                ids=[memory_id],
                with_vectors=True,
            )

            if not source_results:
                logger.warning(f"Memory {memory_id} not found in {collection}")
                return []

            source = source_results[0]
            source_vector = source.vector

            if not source_vector:
                logger.warning(f"Memory {memory_id} has no vector")
                return []

            # Get existing relations to exclude
            existing_relations = await self.get_relations(
                memory_id=memory_id,
                direction=RelationDirection.BOTH,
            )
            existing_ids = {str(r.source_id) for r in existing_relations}
            existing_ids.update(str(r.target_id) for r in existing_relations)
            existing_ids.add(memory_id)

            search_limit = limit + len(existing_ids) + 5  # Extra buffer
            all_hits = []

            # Phase 1: Project-scoped search (high priority)
            source_project = source.payload.get("project")
            if source_project:
                project_hits = await self._qdrant.search(
                    collection=collection,
                    vector=source_vector,
                    limit=search_limit,
                    score_threshold=min_similarity,
                    filter_conditions={"project": source_project},
                )
                all_hits.extend(project_hits)

            # Phase 2: Global search (fills remaining slots)
            global_hits = await self._qdrant.search(
                collection=collection,
                vector=source_vector,
                limit=search_limit,
                score_threshold=min_similarity,
            )
            # Deduplicate: skip hits already found in project search
            seen_ids = {hit.id for hit in all_hits}
            for hit in global_hits:
                if hit.id not in seen_ids:
                    all_hits.append(hit)
                    seen_ids.add(hit.id)

            suggestions = []
            for hit in all_hits:
                if hit.id in existing_ids:
                    continue

                # Infer relation type from content
                suggested_type = self._infer_relation_type(
                    source_payload=source.payload,
                    target_payload=hit.payload,
                )

                reason = self._explain_suggestion(
                    source_payload=source.payload,
                    target_payload=hit.payload,
                    relation_type=suggested_type,
                )

                # Calculate composite confidence score
                confidence = self._calculate_confidence(
                    base_score=hit.score,
                    source_payload=source.payload,
                    target_payload=hit.payload,
                    relation_type=suggested_type,
                )

                suggestions.append(
                    RelationSuggestion(
                        target_id=hit.id,
                        target_content=hit.payload.get("content", "")[:500],
                        target_tags=hit.payload.get("tags", []),
                        target_type=hit.payload.get("memory_type"),
                        target_project=hit.payload.get("project"),
                        suggested_type=suggested_type,
                        confidence=confidence,
                        reason=reason,
                    )
                )

            # Sort by confidence and limit
            suggestions.sort(key=lambda s: s.confidence, reverse=True)
            return suggestions[:limit]

        except Exception as e:
            logger.error(f"Failed to suggest relations: {e}")
            raise GraphManagerError(f"Failed to suggest relations: {e}") from e

    def _infer_relation_type(
        self,
        source_payload: dict[str, Any],
        target_payload: dict[str, Any],
    ) -> RelationType:
        """Infer relation type based on content heuristics.

        Analyzes BOTH source and target content, tags, and metadata
        to suggest the most appropriate relation type.

        Args:
            source_payload: Source memory payload
            target_payload: Target memory payload

        Returns:
            Inferred RelationType
        """
        source_tags = set(source_payload.get("tags", []))
        target_tags = set(target_payload.get("tags", []))
        source_content = source_payload.get("content", "").lower()
        target_content = target_payload.get("content", "").lower()

        # Keywords for various patterns
        fix_keywords = [
            "fix", "fixed", "soluzione", "risolto", "resolved", "solved",
            "solution", "workaround", "patch", "corrected", "remedy"
        ]
        problem_keywords = [
            "bug", "errore", "error", "problema", "problem", "issue",
            "crash", "fail", "broken", "not working", "exception", "traceback"
        ]

        # Check for FIXES pattern (bidirectional)
        # Source has fix keywords AND target has problem keywords
        source_has_fix = any(kw in source_content for kw in fix_keywords)
        target_has_problem = any(kw in target_content for kw in problem_keywords)
        if source_has_fix and target_has_problem:
            return RelationType.FIXES

        # Reverse: target has fix, source has problem (swap direction mentally)
        target_has_fix = any(kw in target_content for kw in fix_keywords)
        source_has_problem = any(kw in source_content for kw in problem_keywords)
        if source_has_problem and target_has_fix:
            # This suggests the relation should be reversed, but we can't do that here
            # So mark as FIXES anyway since they're clearly related
            return RelationType.FIXES

        # Check for causal patterns (bidirectional)
        causal_source_keywords = [
            "decision", "decisione", "choose", "decided", "caused", "leads to",
            "results in", "because", "therefore", "consequently", "implemented"
        ]
        result_keywords = [
            "result", "outcome", "consequence", "effect", "impact",
            "resulted", "caused by", "due to"
        ]

        source_has_causal = any(kw in source_content for kw in causal_source_keywords)
        target_has_result = any(kw in target_content for kw in result_keywords)
        if source_has_causal and target_has_result:
            return RelationType.CAUSES
        if source_has_causal:
            return RelationType.CAUSES

        # Check for support/opposition patterns (check both sides)
        oppose_keywords = [
            "however", "but", "although", "instead", "contrary",
            "tuttavia", "invece", "contrario", "wrong", "incorrect",
            "disagree", "conflict", "contradicts"
        ]
        support_keywords = [
            "confirms", "supports", "validates", "correct", "agree",
            "conferma", "supporta", "corretto", "consistent", "aligns with"
        ]

        # Check if source opposes target or target opposes source
        source_opposes = any(kw in source_content for kw in oppose_keywords)
        target_opposes = any(kw in target_content for kw in oppose_keywords)
        if source_opposes or target_opposes:
            return RelationType.OPPOSES

        source_supports = any(kw in source_content for kw in support_keywords)
        target_supports = any(kw in target_content for kw in support_keywords)
        if source_supports or target_supports:
            return RelationType.SUPPORTS

        # Check for temporal/supersedes patterns
        supersede_keywords = [
            "update", "new version", "replace", "deprecated", "obsolete",
            "aggiornamento", "nuova versione", "sostituisce", "superseded",
            "outdated", "old version", "previous version"
        ]
        supersede_source = any(kw in source_content for kw in supersede_keywords)
        supersede_target = any(kw in target_content for kw in supersede_keywords)
        if supersede_source or supersede_target:
            return RelationType.SUPERSEDES

        # Check for structural patterns
        part_of_keywords = ["part of", "parte di", "belongs to", "component of", "section of"]
        derives_keywords = ["derived", "deriva", "based on", "extended from", "consolidated"]

        if any(kw in source_content for kw in part_of_keywords):
            return RelationType.PART_OF
        if any(kw in source_content for kw in derives_keywords):
            return RelationType.DERIVES

        # Check for temporal patterns based on timestamps
        source_time = source_payload.get("created_at")
        target_time = target_payload.get("created_at")
        if source_time and target_time:
            try:
                # Parse timestamps if they're strings
                from datetime import datetime
                if isinstance(source_time, str):
                    source_time = datetime.fromisoformat(source_time.replace("Z", "+00:00"))
                if isinstance(target_time, str):
                    target_time = datetime.fromisoformat(target_time.replace("Z", "+00:00"))

                # Calculate time difference in seconds
                time_diff = abs((source_time - target_time).total_seconds())

                # If within 1 hour and same tags, likely FOLLOWS
                if time_diff < 3600 and source_tags & target_tags:
                    if source_time > target_time:
                        return RelationType.FOLLOWS

                # Even without shared tags, very close timestamps suggest temporal relation
                if time_diff < 1800:  # 30 minutes
                    if source_time > target_time:
                        return RelationType.FOLLOWS
            except (ValueError, TypeError, AttributeError):
                pass  # Couldn't parse timestamps, continue to default

        # Default to generic related
        return RelationType.RELATED

    def _calculate_confidence(
        self,
        base_score: float,
        source_payload: dict[str, Any],
        target_payload: dict[str, Any],
        relation_type: RelationType,
    ) -> float:
        """Calculate composite confidence score with boosts.

        Adjusts the raw vector similarity score based on:
        - Specific relation type (non-generic types get a boost)
        - Shared tags between source and target
        - Same memory type

        Args:
            base_score: Raw vector similarity score (0-1)
            source_payload: Source memory payload
            target_payload: Target memory payload
            relation_type: Inferred relation type

        Returns:
            Adjusted confidence score (0-1)
        """
        confidence = base_score

        # Boost for specific (non-generic) relation types
        # If we identified a specific type, we're more confident
        if relation_type != RelationType.RELATED:
            confidence = min(1.0, confidence * 1.1)  # 10% boost

        # Boost for shared tags
        source_tags = set(source_payload.get("tags", []))
        target_tags = set(target_payload.get("tags", []))
        shared_tags = source_tags & target_tags
        if shared_tags:
            # Each shared tag adds 3% confidence, up to 15%
            tag_boost = min(0.15, len(shared_tags) * 0.03)
            confidence = min(1.0, confidence + tag_boost)

        # Boost for same memory type
        source_type = source_payload.get("memory_type")
        target_type = target_payload.get("memory_type")
        if source_type and target_type and source_type == target_type:
            confidence = min(1.0, confidence + 0.02)  # 2% boost

        # Significant boost for same project
        source_project = source_payload.get("project")
        target_project = target_payload.get("project")
        if source_project and target_project and source_project == target_project:
            confidence = min(1.0, confidence + 0.15)  # 15% boost

        return round(confidence, 3)

    def _explain_suggestion(
        self,
        source_payload: dict[str, Any],
        target_payload: dict[str, Any],
        relation_type: RelationType,
    ) -> str:
        """Generate explanation for a suggestion.

        Args:
            source_payload: Source memory payload
            target_payload: Target memory payload
            relation_type: Inferred relation type

        Returns:
            Human-readable explanation
        """
        shared_tags = set(source_payload.get("tags", [])) & set(
            target_payload.get("tags", [])
        )

        # Check for same project
        source_project = source_payload.get("project")
        target_project = target_payload.get("project")
        same_project = source_project and target_project and source_project == target_project
        project_note = f" (same project: {source_project})" if same_project else ""

        explanations = {
            RelationType.FIXES: "Appears to be a solution to a problem" + project_note,
            RelationType.CAUSES: "Contains a decision or action leading to consequences" + project_note,
            RelationType.FOLLOWS: "Subsequent event in the same context" + project_note,
            RelationType.OPPOSES: "Contains potentially contradicting information" + project_note,
            RelationType.SUPPORTS: "Contains supporting or confirming information" + project_note,
            RelationType.SUPERSEDES: "Appears to be an updated version" + project_note,
            RelationType.DERIVES: "Derived or consolidated content" + project_note,
            RelationType.PART_OF: "Appears to be a component of a larger concept" + project_note,
            RelationType.RELATED: (
                f"Similar content"
                + (f", shared tags: {', '.join(list(shared_tags)[:3])}" if shared_tags else "")
                + project_note
            ),
        }

        return explanations.get(relation_type, "Related content")

    # ─────────────────────────────────────────────────────────────────────────
    # Private Helpers
    # ─────────────────────────────────────────────────────────────────────────

    async def _mark_has_relations(self, memory_ids: list[str]) -> None:
        """Mark memories as having relations in Qdrant for fast filtering.

        Args:
            memory_ids: List of memory IDs to mark
        """
        for mid in memory_ids:
            try:
                await self._qdrant.update_payload(
                    collection=self._default_collection,
                    id=mid,
                    payload={"has_relations": True},
                )
            except Exception as e:
                # Memory might not exist in this collection
                logger.debug(f"Could not mark has_relations for {mid}: {e}")

    async def _populate_memory_context(
        self,
        memory_id: str,
        db_relations: list[Any],
    ) -> list[RelationWithContext]:
        """Populate relation objects with linked memory content.

        Args:
            memory_id: The querying memory ID
            db_relations: Database relation records

        Returns:
            List of RelationWithContext objects
        """
        # Collect all linked memory IDs
        linked_ids = set()
        for rel in db_relations:
            if str(rel.source_id) != memory_id:
                linked_ids.add(str(rel.source_id))
            if str(rel.target_id) != memory_id:
                linked_ids.add(str(rel.target_id))

        if not linked_ids:
            return []

        # Batch fetch from Qdrant
        try:
            results = await self._qdrant.get(
                collection=self._default_collection,
                ids=list(linked_ids),
            )
            point_map = {r.id: r for r in results}
        except Exception as e:
            logger.warning(f"Could not fetch memory context: {e}")
            point_map = {}

        # Build RelationWithContext objects
        relations_with_context = []
        for rel in db_relations:
            # Determine which ID is the linked memory
            linked_id = (
                str(rel.target_id)
                if str(rel.source_id) == memory_id
                else str(rel.source_id)
            )
            point = point_map.get(linked_id)

            rwc = RelationWithContext(
                id=rel.id,
                source_id=rel.source_id,
                target_id=rel.target_id,
                relation_type=rel.relation_type,
                weight=rel.weight,
                created_by=rel.created_by,
                created_at=rel.created_at,
                metadata=rel.metadata,
                linked_memory_id=linked_id,
                linked_memory_content=point.payload.get("content") if point else None,
                linked_memory_type=point.payload.get("memory_type") if point else None,
                linked_memory_tags=point.payload.get("tags", []) if point else [],
                linked_memory_importance=point.payload.get("importance") if point else None,
            )
            relations_with_context.append(rwc)

        return relations_with_context

    async def _populate_neighbor_content(
        self,
        neighbors: list[dict[str, Any]],
    ) -> None:
        """Populate neighbor dicts with memory content.

        Args:
            neighbors: List of neighbor info dicts to populate
        """
        memory_ids = [n["memory_id"] for n in neighbors]

        try:
            results = await self._qdrant.get(
                collection=self._default_collection,
                ids=memory_ids,
            )
            point_map = {r.id: r for r in results}

            for neighbor in neighbors:
                point = point_map.get(neighbor["memory_id"])
                if point:
                    neighbor["content"] = point.payload.get("content", "")[:200]
                    neighbor["tags"] = point.payload.get("tags", [])
                    neighbor["memory_type"] = point.payload.get("memory_type")

        except Exception as e:
            logger.warning(f"Could not fetch neighbor content: {e}")

    async def _build_nodes(
        self,
        memory_ids: list[str],
        center_id: str,
        neighbors: list[dict[str, Any]],
    ) -> list[GraphNode]:
        """Build graph nodes from memory IDs.

        Args:
            memory_ids: List of memory IDs
            center_id: ID of the center node
            neighbors: Neighbor info with depth

        Returns:
            List of GraphNode objects
        """
        # Create depth map
        depth_map = {center_id: 0}
        for n in neighbors:
            depth_map[n["memory_id"]] = n["depth"]

        # Fetch memory details from Qdrant
        try:
            results = await self._qdrant.get(
                collection=self._default_collection,
                ids=memory_ids,
            )
        except Exception as e:
            logger.warning(f"Could not fetch node content: {e}")
            results = []

        nodes = []
        for result in results:
            node = GraphNode(
                id=result.id,
                label=result.payload.get("content", "")[:50],
                memory_type=result.payload.get("memory_type"),
                importance=result.payload.get("importance", 0.5),
                tags=result.payload.get("tags", []),
                is_center=(result.id == center_id),
                depth=depth_map.get(result.id, 0),
            )
            nodes.append(node)

        return nodes

    async def _build_edges(self, memory_ids: list[str]) -> list[GraphEdge]:
        """Build graph edges for the given memory IDs.

        Args:
            memory_ids: List of memory IDs in the subgraph

        Returns:
            List of GraphEdge objects
        """
        memory_id_set = set(memory_ids)
        edges = []

        # Get all relations for these memories
        for mid in memory_ids:
            relations = await self.repo.get_for_memory(
                memory_id=UUID(mid),
                direction="outgoing",
            )

            for rel in relations:
                # Only include edges where both ends are in the subgraph
                if str(rel.target_id) in memory_id_set:
                    edge = GraphEdge(
                        source=str(rel.source_id),
                        target=str(rel.target_id),
                        relation_type=rel.relation_type,
                        weight=rel.weight,
                        created_by=rel.created_by,
                    )
                    edges.append(edge)

        return edges

    # ─────────────────────────────────────────────────────────────────────────
    # Graph Overview
    # ─────────────────────────────────────────────────────────────────────────

    async def get_graph_overview(
        self,
        limit: int = 10,
        depth: int = 2,
    ) -> Subgraph:
        """Get graph overview centered on the most-connected memories.

        Useful for showing an initial graph visualization without requiring
        a search first. Finds memories with the most relations and builds
        a subgraph from them.

        Args:
            limit: Maximum number of "hub" memories to include
            depth: Traversal depth from each hub

        Returns:
            Subgraph containing the most connected memories and their relations
        """
        depth = min(max(depth, 1), 3)  # Clamp to 1-3 for performance

        try:
            # Find memories with the most relations (incoming + outgoing)
            rows = await self._db.fetch(
                """
                SELECT memory_id, SUM(relation_count) as total_count FROM (
                    SELECT source_id AS memory_id, COUNT(*) as relation_count
                    FROM memory_relations
                    GROUP BY source_id
                    UNION ALL
                    SELECT target_id AS memory_id, COUNT(*) as relation_count
                    FROM memory_relations
                    GROUP BY target_id
                ) combined
                GROUP BY memory_id
                ORDER BY total_count DESC
                LIMIT $1
                """,
                limit,
            )

            if not rows:
                # No relations exist yet
                return Subgraph(
                    center_id="",
                    depth=depth,
                    nodes=[],
                    edges=[],
                )

            hub_ids = [str(row["memory_id"]) for row in rows]

            # Collect all memory IDs to include (hubs + their neighbors)
            all_memory_ids: set[str] = set(hub_ids)
            all_neighbors: list[dict[str, Any]] = []

            for hub_id in hub_ids[:5]:  # Limit to top 5 hubs to avoid explosion
                neighbors = await self.get_neighbors(
                    memory_id=hub_id,
                    depth=min(depth, 1),  # Shallow depth per hub
                )
                for n in neighbors:
                    all_memory_ids.add(n["memory_id"])
                    all_neighbors.append(n)

            # Build nodes
            unique_ids = list(all_memory_ids)
            nodes = await self._build_nodes(
                memory_ids=unique_ids,
                center_id=hub_ids[0] if hub_ids else "",
                neighbors=all_neighbors,
            )

            # Mark the top hub as center
            for node in nodes:
                if node.id == hub_ids[0]:
                    node.is_center = True
                    node.depth = 0

            # Build edges between all nodes in the subgraph
            edges = await self._build_edges(unique_ids)

            return Subgraph(
                center_id=hub_ids[0] if hub_ids else "",
                depth=depth,
                nodes=nodes,
                edges=edges,
            )

        except Exception as e:
            logger.error(f"Failed to get graph overview: {e}")
            raise GraphManagerError(f"Failed to get graph overview: {e}") from e

    # ─────────────────────────────────────────────────────────────────────────
    # Statistics and Utilities
    # ─────────────────────────────────────────────────────────────────────────

    async def count_relations(self, memory_id: str) -> dict[str, dict[str, int]]:
        """Count relations by type for a memory.

        Args:
            memory_id: Memory ID

        Returns:
            Dict mapping relation type to incoming/outgoing counts
        """
        try:
            return await self.repo.count_relations(UUID(memory_id))
        except Exception as e:
            logger.error(f"Failed to count relations: {e}")
            raise GraphManagerError(f"Failed to count relations: {e}") from e

    async def delete_memory_relations(self, memory_id: str) -> int:
        """Delete all relations involving a memory.

        Should be called when a memory is deleted.

        Args:
            memory_id: Memory ID

        Returns:
            Number of relations deleted
        """
        try:
            count = await self.repo.delete_for_memory(UUID(memory_id))
            logger.info(f"Deleted {count} relations for memory {memory_id}")
            return count
        except Exception as e:
            logger.error(f"Failed to delete memory relations: {e}")
            raise GraphManagerError(f"Failed to delete memory relations: {e}") from e

    async def has_relations(self, memory_id: str) -> bool:
        """Check if a memory has any relations.

        Args:
            memory_id: Memory ID

        Returns:
            True if memory has relations
        """
        try:
            relations = await self.repo.get_for_memory(
                memory_id=UUID(memory_id),
                direction="both",
            )
            return len(relations) > 0
        except Exception as e:
            logger.error(f"Failed to check relations: {e}")
            return False

    # ─────────────────────────────────────────────────────────────────────────
    # Global Discovery
    # ─────────────────────────────────────────────────────────────────────────

    async def discover_relations_global(
        self,
        limit: int = 50,
        min_confidence: float = 0.70,
        auto_accept_threshold: float = 0.90,
        skip_with_relations: bool = True,
        memory_types: list[str] | None = None,
        rejected_pairs: set[tuple[str, str, str]] | None = None,
    ) -> dict[str, Any]:
        """Discover potential relations across all memories.

        Scans memories and suggests relations based on vector similarity
        and content heuristics. Can auto-accept high-confidence suggestions.

        Args:
            limit: Maximum suggestions to return
            min_confidence: Minimum similarity threshold
            auto_accept_threshold: Auto-accept relations above this confidence
            skip_with_relations: Only scan memories without existing relations
            memory_types: Filter by memory types (episodic, semantic, procedural)
            rejected_pairs: Set of (source_id, target_id, relation_type) to skip

        Returns:
            Dict with suggestions, auto_accepted count, and scan stats
        """
        rejected_pairs = rejected_pairs or set()
        suggestions: list[dict[str, Any]] = []
        auto_accepted = 0
        scanned_count = 0
        total_without_relations = 0

        try:
            # Get all memories from Qdrant
            collections = memory_types or ["semantic", "episodic", "procedural"]
            all_memories: list[tuple[str, dict[str, Any], str]] = []

            for collection in collections:
                try:
                    # Scroll through all points in collection
                    offset = None
                    while True:
                        points, next_offset = await self._qdrant.scroll(
                            collection=collection,
                            limit=500,
                            offset=offset,
                            with_vectors=False,
                        )
                        for point in points:
                            all_memories.append((point.id, point.payload, collection))
                        if next_offset is None or len(points) == 0:
                            break
                        offset = next_offset
                except Exception as e:
                    logger.warning(f"Could not scroll collection {collection}: {e}")
                    continue

            # Track which memories have relations
            memories_with_relations: set[str] = set()
            if skip_with_relations:
                # Query PostgreSQL for all memory IDs with relations
                rows = await self._db.fetch(
                    """
                    SELECT DISTINCT source_id as memory_id FROM memory_relations
                    UNION
                    SELECT DISTINCT target_id as memory_id FROM memory_relations
                    """
                )
                memories_with_relations = {str(row["memory_id"]) for row in rows}

            # Track memories to scan
            memories_to_scan = [
                (mid, payload, collection)
                for mid, payload, collection in all_memories
                if not skip_with_relations or mid not in memories_with_relations
            ]
            total_without_relations = len(memories_to_scan)

            # Deduplicate suggestions (A->B and B->A should count as one)
            seen_pairs: set[tuple[str, str]] = set()

            for memory_id, payload, collection in memories_to_scan:
                if len(suggestions) >= limit * 2:  # Buffer for dedup
                    break

                scanned_count += 1

                try:
                    # Get suggestions for this memory
                    memory_suggestions = await self.suggest_relations(
                        memory_id=memory_id,
                        limit=5,
                        min_similarity=min_confidence,
                        collection=collection,
                    )

                    for suggestion in memory_suggestions:
                        # Skip if rejected
                        reject_key = (memory_id, suggestion.target_id, suggestion.suggested_type.value)
                        if reject_key in rejected_pairs:
                            continue

                        # Skip duplicate pairs
                        pair = tuple(sorted([memory_id, suggestion.target_id]))
                        if pair in seen_pairs:
                            continue
                        seen_pairs.add(pair)

                        # Get shared tags
                        source_tags = set(payload.get("tags", []))
                        target_tags = set(suggestion.target_tags)
                        shared_tags = list(source_tags & target_tags)

                        # Auto-accept high confidence
                        if suggestion.confidence >= auto_accept_threshold:
                            try:
                                await self.add_relation(
                                    source_id=memory_id,
                                    target_id=suggestion.target_id,
                                    relation_type=suggestion.suggested_type,
                                    created_by=RelationCreator.AUTO,
                                )
                                auto_accepted += 1
                                continue
                            except Exception as e:
                                logger.debug(f"Could not auto-accept: {e}")

                        # Add to suggestions
                        suggestions.append({
                            "source_id": memory_id,
                            "source_preview": payload.get("content", "")[:500],
                            "source_type": collection,
                            "source_project": payload.get("project"),
                            "target_id": suggestion.target_id,
                            "target_preview": suggestion.target_content[:500],
                            "target_type": suggestion.target_type,
                            "target_project": suggestion.target_project,
                            "relation_type": suggestion.suggested_type.value,
                            "confidence": suggestion.confidence,
                            "reason": suggestion.reason,
                            "shared_tags": shared_tags,
                        })

                except Exception as e:
                    logger.debug(f"Could not get suggestions for {memory_id}: {e}")
                    continue

            # Sort by confidence and limit
            suggestions.sort(key=lambda x: x["confidence"], reverse=True)
            suggestions = suggestions[:limit]

            return {
                "suggestions": suggestions,
                "auto_accepted": auto_accepted,
                "scanned_count": scanned_count,
                "total_without_relations": total_without_relations,
            }

        except Exception as e:
            logger.error(f"Failed to discover relations: {e}")
            raise GraphManagerError(f"Failed to discover relations: {e}") from e

    async def add_relations_bulk(
        self,
        relations: list[dict[str, str]],
        created_by: RelationCreator = RelationCreator.AUTO,
    ) -> dict[str, int]:
        """Create multiple relations in bulk.

        Args:
            relations: List of dicts with source_id, target_id, relation_type
            created_by: Who/what created these relations

        Returns:
            Dict with created count, duplicates, and errors
        """
        created = 0
        duplicates = 0
        errors = 0

        for rel in relations:
            try:
                await self.add_relation(
                    source_id=rel["source_id"],
                    target_id=rel["target_id"],
                    relation_type=RelationType(rel["relation_type"]),
                    created_by=created_by,
                )
                created += 1
            except Exception as e:
                error_str = str(e).lower()
                if "duplicate" in error_str or "unique" in error_str:
                    duplicates += 1
                else:
                    errors += 1
                    logger.debug(f"Bulk relation error: {e}")

        return {
            "created": created,
            "duplicates": duplicates,
            "errors": errors,
        }
