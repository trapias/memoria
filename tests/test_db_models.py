"""Tests for PostgreSQL database models."""

import pytest
from datetime import datetime, timezone
from uuid import uuid4

from mcp_memoria.db.models import (
    Client,
    Project,
    WorkSession,
    MemoryRelation,
    UserSetting,
    PauseEntry,
    SessionCategory,
    SessionStatus,
    RelationType,
    RelationCreator,
)


class TestClient:
    """Tests for Client model."""

    def test_create_client(self):
        """Test creating a client with required fields."""
        client = Client(
            id=uuid4(),
            name="Test Client",
        )
        assert client.name == "Test Client"
        assert client.metadata == {}

    def test_client_with_metadata(self):
        """Test client with custom metadata."""
        client = Client(
            id=uuid4(),
            name="Client",
            metadata={"industry": "tech", "size": "enterprise"},
        )
        assert client.metadata["industry"] == "tech"
        assert client.metadata["size"] == "enterprise"


class TestProject:
    """Tests for Project model."""

    def test_create_project(self):
        """Test creating a project."""
        project = Project(
            id=uuid4(),
            name="Test Project",
        )
        assert project.name == "Test Project"
        assert project.client_id is None
        assert project.repo is None

    def test_project_with_repo(self):
        """Test project with GitHub repo."""
        project = Project(
            id=uuid4(),
            name="Memoria",
            repo="owner/memoria",
        )
        assert project.repo == "owner/memoria"


class TestWorkSession:
    """Tests for WorkSession model."""

    def test_create_session(self):
        """Test creating a work session."""
        session = WorkSession(
            id=uuid4(),
            description="Working on feature X",
            category=SessionCategory.CODING,
        )
        assert session.description == "Working on feature X"
        assert session.category == SessionCategory.CODING
        assert session.status == SessionStatus.ACTIVE

    def test_session_categories(self):
        """Test all session categories."""
        categories = [
            SessionCategory.CODING,
            SessionCategory.REVIEW,
            SessionCategory.MEETING,
            SessionCategory.SUPPORT,
            SessionCategory.RESEARCH,
            SessionCategory.DOCUMENTATION,
            SessionCategory.DEVOPS,
            SessionCategory.OTHER,
        ]
        for cat in categories:
            session = WorkSession(
                id=uuid4(),
                description="Test",
                category=cat,
            )
            assert session.category == cat

    def test_session_with_github_context(self):
        """Test session with GitHub issue/PR."""
        session = WorkSession(
            id=uuid4(),
            description="Fix bug",
            category=SessionCategory.CODING,
            issue_number=123,
            pr_number=456,
            branch="fix/bug-123",
        )
        assert session.issue_number == 123
        assert session.pr_number == 456
        assert session.branch == "fix/bug-123"


class TestPauseEntry:
    """Tests for PauseEntry model."""

    def test_create_pause(self):
        """Test creating a pause entry."""
        now = datetime.now(timezone.utc)
        pause = PauseEntry(
            start=now,
            reason="Lunch break",
        )
        assert pause.start == now
        assert pause.end is None
        assert pause.reason == "Lunch break"

    def test_pause_with_end(self):
        """Test completed pause."""
        start = datetime.now(timezone.utc)
        end = datetime.now(timezone.utc)
        pause = PauseEntry(start=start, end=end, reason="Coffee")
        assert pause.end == end


class TestMemoryRelation:
    """Tests for MemoryRelation model."""

    def test_create_relation(self):
        """Test creating a memory relation."""
        source = uuid4()
        target = uuid4()
        relation = MemoryRelation(
            id=uuid4(),
            source_id=source,
            target_id=target,
            relation_type=RelationType.CAUSES,
        )
        assert relation.source_id == source
        assert relation.target_id == target
        assert relation.relation_type == RelationType.CAUSES
        assert relation.weight == 1.0

    def test_relation_types(self):
        """Test all relation types."""
        types = [
            RelationType.CAUSES,
            RelationType.FIXES,
            RelationType.SUPPORTS,
            RelationType.OPPOSES,
            RelationType.FOLLOWS,
            RelationType.SUPERSEDES,
            RelationType.DERIVES,
            RelationType.PART_OF,
            RelationType.RELATED,
        ]
        for rtype in types:
            relation = MemoryRelation(
                id=uuid4(),
                source_id=uuid4(),
                target_id=uuid4(),
                relation_type=rtype,
            )
            assert relation.relation_type == rtype

    def test_relation_creators(self):
        """Test relation creator types."""
        creators = [
            RelationCreator.USER,
            RelationCreator.AUTO,
            RelationCreator.SYSTEM,
        ]
        for creator in creators:
            relation = MemoryRelation(
                id=uuid4(),
                source_id=uuid4(),
                target_id=uuid4(),
                relation_type=RelationType.RELATED,
                created_by=creator,
            )
            assert relation.created_by == creator


class TestUserSetting:
    """Tests for UserSetting model."""

    def test_create_setting(self):
        """Test creating a user setting."""
        setting = UserSetting(key="theme", value="dark")
        assert setting.key == "theme"
        assert setting.value == "dark"

    def test_setting_with_complex_value(self):
        """Test setting with dict value."""
        setting = UserSetting(
            key="preferences",
            value={"notifications": True, "language": "en"},
        )
        assert setting.value["notifications"] is True
