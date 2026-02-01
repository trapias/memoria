"""Tests for Knowledge Graph types."""

import pytest
from uuid import uuid4

from mcp_memoria.core.graph_types import (
    RelationType,
    RelationDirection,
    RelationCreator,
    Relation,
    RelationWithContext,
    RelationSuggestion,
    GraphNode,
    GraphEdge,
    GraphPath,
    PathStep,
    Subgraph,
)


class TestRelationType:
    """Tests for RelationType enum."""

    def test_all_relation_types(self):
        """Test all 9 relation types exist."""
        expected = [
            "causes", "fixes", "supports", "opposes",
            "follows", "supersedes", "derives", "part_of", "related"
        ]
        actual = [rt.value for rt in RelationType]
        assert sorted(actual) == sorted(expected)

    def test_relation_type_values(self):
        """Test specific relation type values."""
        assert RelationType.CAUSES.value == "causes"
        assert RelationType.FIXES.value == "fixes"
        assert RelationType.SUPERSEDES.value == "supersedes"


class TestRelationDirection:
    """Tests for RelationDirection enum."""

    def test_direction_values(self):
        """Test direction enum values."""
        assert RelationDirection.OUTGOING.value == "out"
        assert RelationDirection.INCOMING.value == "in"
        assert RelationDirection.BOTH.value == "both"


class TestRelationCreator:
    """Tests for RelationCreator enum."""

    def test_creator_values(self):
        """Test creator enum values."""
        assert RelationCreator.USER.value == "user"
        assert RelationCreator.AUTO.value == "auto"
        assert RelationCreator.SYSTEM.value == "system"
        assert RelationCreator.AI_SUGGESTED.value == "ai_suggested"


class TestRelation:
    """Tests for Relation model."""

    def test_create_relation(self):
        """Test creating a relation."""
        source = uuid4()
        target = uuid4()
        relation = Relation(
            id=uuid4(),
            source_id=source,
            target_id=target,
            relation_type=RelationType.CAUSES,
        )
        assert relation.source_id == source
        assert relation.target_id == target
        assert relation.relation_type == RelationType.CAUSES
        assert relation.weight == 1.0
        assert relation.created_by == RelationCreator.USER

    def test_relation_with_weight(self):
        """Test relation with custom weight."""
        relation = Relation(
            id=uuid4(),
            source_id=uuid4(),
            target_id=uuid4(),
            relation_type=RelationType.SUPPORTS,
            weight=0.8,
        )
        assert relation.weight == 0.8

    def test_relation_with_metadata(self):
        """Test relation with metadata."""
        relation = Relation(
            id=uuid4(),
            source_id=uuid4(),
            target_id=uuid4(),
            relation_type=RelationType.RELATED,
            metadata={"context": "same project", "confidence": 0.95},
        )
        assert relation.metadata["context"] == "same project"
        assert relation.metadata["confidence"] == 0.95

    def test_relation_uuid_from_string(self):
        """Test UUID validation from string."""
        source_str = "12345678-1234-5678-1234-567812345678"
        target_str = "87654321-4321-8765-4321-876543218765"
        relation = Relation(
            source_id=source_str,
            target_id=target_str,
            relation_type=RelationType.FIXES,
        )
        assert str(relation.source_id) == source_str
        assert str(relation.target_id) == target_str

    def test_model_dump_for_api(self):
        """Test API serialization."""
        relation = Relation(
            id=uuid4(),
            source_id=uuid4(),
            target_id=uuid4(),
            relation_type=RelationType.CAUSES,
            weight=0.9,
        )
        data = relation.model_dump_for_api()
        assert "source_id" in data
        assert "target_id" in data
        assert data["type"] == "causes"
        assert data["weight"] == 0.9


class TestRelationWithContext:
    """Tests for RelationWithContext model."""

    def test_relation_with_context(self):
        """Test relation with linked memory context."""
        relation = RelationWithContext(
            source_id=uuid4(),
            target_id=uuid4(),
            relation_type=RelationType.FIXES,
            linked_memory_id="abc-123",
            linked_memory_content="Some content here",
            linked_memory_type="semantic",
            linked_memory_tags=["bug", "fix"],
            linked_memory_importance=0.8,
        )
        assert relation.linked_memory_content == "Some content here"
        assert relation.linked_memory_tags == ["bug", "fix"]


class TestRelationSuggestion:
    """Tests for RelationSuggestion model."""

    def test_create_suggestion(self):
        """Test creating a relation suggestion."""
        suggestion = RelationSuggestion(
            target_id="mem-123",
            target_content="Related memory content",
            suggested_type=RelationType.RELATED,
            confidence=0.85,
            reason="High semantic similarity",
        )
        assert suggestion.confidence == 0.85
        assert suggestion.reason == "High semantic similarity"

    def test_suggestion_api_serialization(self):
        """Test suggestion API serialization truncates long content."""
        long_content = "x" * 300
        suggestion = RelationSuggestion(
            target_id="mem-123",
            target_content=long_content,
            suggested_type=RelationType.SUPPORTS,
            confidence=0.7,
        )
        data = suggestion.model_dump_for_api()
        assert len(data["target_content"]) == 203  # 200 + "..."


class TestGraphNode:
    """Tests for GraphNode model."""

    def test_create_node(self):
        """Test creating a graph node."""
        node = GraphNode(
            id="mem-123",
            label="Test memory",
            memory_type="semantic",
            importance=0.8,
            tags=["test", "example"],
        )
        assert node.id == "mem-123"
        assert node.importance == 0.8
        assert node.is_center is False

    def test_center_node(self):
        """Test center node flag."""
        node = GraphNode(
            id="mem-center",
            label="Center",
            is_center=True,
            depth=0,
        )
        assert node.is_center is True
        assert node.depth == 0


class TestGraphEdge:
    """Tests for GraphEdge model."""

    def test_create_edge(self):
        """Test creating a graph edge."""
        edge = GraphEdge(
            source="mem-1",
            target="mem-2",
            relation_type=RelationType.CAUSES,
            weight=1.0,
        )
        assert edge.source == "mem-1"
        assert edge.target == "mem-2"
        assert edge.relation_type == RelationType.CAUSES


class TestPathStep:
    """Tests for PathStep model."""

    def test_create_step(self):
        """Test creating a path step."""
        step = PathStep(
            memory_id="mem-123",
            relation_type=RelationType.FOLLOWS,
            direction="out",
            memory_content="Step content",
        )
        assert step.memory_id == "mem-123"
        assert step.direction == "out"


class TestGraphPath:
    """Tests for GraphPath model."""

    def test_create_path(self):
        """Test creating a graph path."""
        path = GraphPath(
            from_id="mem-start",
            to_id="mem-end",
            steps=[
                PathStep(memory_id="mem-start"),
                PathStep(memory_id="mem-mid", relation_type=RelationType.CAUSES, direction="out"),
                PathStep(memory_id="mem-end", relation_type=RelationType.FIXES, direction="out"),
            ],
            total_weight=1.8,
        )
        assert path.from_id == "mem-start"
        assert path.to_id == "mem-end"
        assert path.length == 2
        assert path.found is True

    def test_empty_path(self):
        """Test empty path (no connection found)."""
        path = GraphPath(
            from_id="mem-a",
            to_id="mem-b",
            steps=[],
        )
        assert path.found is False
        assert path.length == 0


class TestSubgraph:
    """Tests for Subgraph model."""

    def test_create_subgraph(self):
        """Test creating a subgraph."""
        subgraph = Subgraph(
            center_id="mem-center",
            depth=2,
            nodes=[
                GraphNode(id="mem-center", label="Center", is_center=True),
                GraphNode(id="mem-1", label="Node 1", depth=1),
                GraphNode(id="mem-2", label="Node 2", depth=1),
            ],
            edges=[
                GraphEdge(source="mem-center", target="mem-1", relation_type=RelationType.CAUSES),
                GraphEdge(source="mem-center", target="mem-2", relation_type=RelationType.RELATED),
            ],
        )
        assert subgraph.node_count == 3
        assert subgraph.edge_count == 2
        assert subgraph.depth == 2
