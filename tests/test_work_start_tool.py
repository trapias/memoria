"""Verify the MCP start tool's confirmation contract with the real tracker."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from mcp.server import Server
from mcp.types import ListToolsRequest

from mcp_memoria.config.settings import Settings
from mcp_memoria.db.exceptions import RecordNotFoundError
from mcp_memoria.db.models import SessionStatus, WorkSession
from mcp_memoria.server import MemoriaServer
from mcp_memoria.work.work_tracker import WorkTracker


def make_server(existing_count=3):
    server = object.__new__(MemoriaServer)
    tracker = WorkTracker(MagicMock(), settings=Settings(work_max_parallel_sessions=5))
    tracker._sessions = AsyncMock()
    sessions = [
        WorkSession(
            id=uuid4(), description=f"Open task {i}: " + "full description " * 5,
            status=SessionStatus.PAUSED if i == 0 else SessionStatus.ACTIVE,
            start_time=datetime.now(UTC),
        )
        for i in range(existing_count)
    ]
    tracker._sessions.count_active.return_value = existing_count
    tracker._sessions.get_all_active.return_value = sessions
    server._get_work_tracker = AsyncMock(return_value=tracker)
    return server, tracker, sessions


@pytest.mark.asyncio
async def test_mcp_schema_explains_confirmation_and_defaults_to_false():
    server = object.__new__(MemoriaServer)
    server.server = Server("test-memoria")
    server._register_tools()
    response = await server.server.request_handlers[ListToolsRequest](
        ListToolsRequest(method="tools/list"),
    )
    tool = next(t for t in response.root.tools if t.name == "memoria_work_start")
    flag = tool.inputSchema["properties"]["confirm_parallel"]
    assert flag["type"] == "boolean"
    assert flag["default"] is False
    assert "user explicitly confirms" in flag["description"]
    assert "confirm_parallel" not in tool.inputSchema["required"]


@pytest.mark.asyncio
async def test_mcp_confirmation_lists_every_open_session_without_creating_one():
    server, tracker, sessions = make_server()

    result = await server._handle_tool("memoria_work_start", {"description": "New task"})

    assert result.startswith("Confirmation required:")
    assert "No session has been started" in result
    assert "confirm_parallel=true" in result
    for session in sessions:
        assert str(session.id) in result
        assert session.description in result
        assert session.status.value in result
    tracker._sessions.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_mcp_confirmed_retry_starts_one_session():
    server, tracker, sessions = make_server()
    new_session = WorkSession(description="New task", start_time=datetime.now(UTC))
    tracker._sessions.create.return_value = new_session
    tracker._sessions.get_all_active.return_value = sessions + [new_session]

    result = await server._handle_tool(
        "memoria_work_start", {"description": "New task", "confirm_parallel": True},
    )

    assert result.startswith(f"Started work session: {new_session.id}")
    assert "Parallel sessions active: 4" in result
    tracker._sessions.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_mcp_confirmation_does_not_override_maximum():
    server, tracker, _ = make_server(existing_count=5)

    result = await server._handle_tool(
        "memoria_work_start", {"description": "Sixth task", "confirm_parallel": True},
    )

    assert result.startswith("Error: Maximum parallel sessions reached (5)")
    tracker._sessions.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_existing_session_lookup_preserves_database_errors():
    _, tracker, _ = make_server()
    tracker._sessions.get.side_effect = RuntimeError("database unavailable")

    with pytest.raises(RuntimeError, match="database unavailable"):
        await tracker._resolve_session(str(uuid4()), [SessionStatus.ACTIVE])


@pytest.mark.asyncio
async def test_missing_session_is_reported_without_masking_other_errors():
    _, tracker, _ = make_server()
    tracker._sessions.get.side_effect = RecordNotFoundError("work_sessions", "missing")

    result = await tracker._resolve_session(str(uuid4()), [SessionStatus.ACTIVE])

    assert "not found" in result["error"]
