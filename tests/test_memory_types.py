"""Tests for memory types."""

import pytest
from datetime import datetime

from mcp_memoria.core.memory_types import (
    MemoryItem,
    MemoryType,
    EpisodicMemory,
    SemanticMemory,
    ProceduralMemory,
    create_memory,
)


class TestMemoryItem:
    """Tests for base MemoryItem."""

    def test_create_memory_item(self):
        """Test creating a basic memory item."""
        memory = MemoryItem(
            content="Test content",
            memory_type=MemoryType.EPISODIC,
        )
        assert memory.content == "Test content"
        assert memory.memory_type == MemoryType.EPISODIC
        assert memory.importance == 0.5
        assert memory.tags == []
        assert memory.id is not None

    def test_to_payload(self):
        """Test converting to Qdrant payload."""
        memory = MemoryItem(
            content="Test content",
            memory_type=MemoryType.SEMANTIC,
            tags=["test", "example"],
            importance=0.8,
        )
        payload = memory.to_payload()

        assert payload["content"] == "Test content"
        assert payload["memory_type"] == "semantic"
        assert payload["tags"] == ["test", "example"]
        assert payload["importance"] == 0.8
        assert "created_at" in payload

    def test_from_payload(self):
        """Test creating from Qdrant payload."""
        payload = {
            "content": "Loaded content",
            "memory_type": "procedural",
            "tags": ["loaded"],
            "importance": 0.7,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "accessed_at": datetime.now().isoformat(),
            "access_count": 5,
        }
        memory = MemoryItem.from_payload("test-id", payload)

        assert memory.id == "test-id"
        assert memory.content == "Loaded content"
        assert memory.memory_type == MemoryType.PROCEDURAL
        assert memory.access_count == 5

    def test_touch(self):
        """Test touch updates access stats."""
        memory = MemoryItem(
            content="Test",
            memory_type=MemoryType.EPISODIC,
        )
        original_count = memory.access_count

        memory.touch()

        assert memory.access_count == original_count + 1


class TestEpisodicMemory:
    """Tests for EpisodicMemory."""

    def test_episodic_memory(self):
        """Test episodic memory creation."""
        memory = EpisodicMemory(
            content="Meeting notes",
            session_id="session-123",
            project="my-project",
        )

        assert memory.memory_type == MemoryType.EPISODIC
        assert memory.session_id == "session-123"
        assert memory.project == "my-project"

    def test_episodic_payload(self):
        """Test episodic memory payload includes extra fields."""
        memory = EpisodicMemory(
            content="Test",
            session_id="sess-1",
            project="proj-1",
            user_action="created file",
        )
        payload = memory.to_payload()

        assert payload["session_id"] == "sess-1"
        assert payload["project"] == "proj-1"
        assert payload["user_action"] == "created file"


class TestSemanticMemory:
    """Tests for SemanticMemory."""

    def test_semantic_memory(self):
        """Test semantic memory creation."""
        memory = SemanticMemory(
            content="Python is a programming language",
            domain="programming",
            source="documentation",
            confidence=0.95,
        )

        assert memory.memory_type == MemoryType.SEMANTIC
        assert memory.domain == "programming"
        assert memory.confidence == 0.95

    def test_semantic_payload(self):
        """Test semantic memory payload."""
        memory = SemanticMemory(
            content="Fact",
            domain="science",
            confidence=0.9,
        )
        payload = memory.to_payload()

        assert payload["domain"] == "science"
        assert payload["confidence"] == 0.9


class TestProceduralMemory:
    """Tests for ProceduralMemory."""

    def test_procedural_memory(self):
        """Test procedural memory creation."""
        memory = ProceduralMemory(
            content="Deploy procedure",
            category="deployment",
            steps=["git push", "run tests", "deploy"],
        )

        assert memory.memory_type == MemoryType.PROCEDURAL
        assert memory.category == "deployment"
        assert len(memory.steps) == 3

    def test_record_execution(self):
        """Test recording procedure execution."""
        memory = ProceduralMemory(
            content="Test procedure",
            success_rate=1.0,
        )

        memory.record_execution(success=True)
        assert memory.execution_count == 1
        assert memory.success_rate > 0.9

        memory.record_execution(success=False)
        assert memory.execution_count == 2
        assert memory.success_rate < 1.0


class TestCreateMemory:
    """Tests for create_memory factory."""

    def test_create_episodic(self):
        """Test creating episodic memory via factory."""
        memory = create_memory("Event", "episodic")
        assert isinstance(memory, EpisodicMemory)

    def test_create_semantic(self):
        """Test creating semantic memory via factory."""
        memory = create_memory("Fact", MemoryType.SEMANTIC)
        assert isinstance(memory, SemanticMemory)

    def test_create_procedural(self):
        """Test creating procedural memory via factory."""
        memory = create_memory("Procedure", "procedural")
        assert isinstance(memory, ProceduralMemory)
