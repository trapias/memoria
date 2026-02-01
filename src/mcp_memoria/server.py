"""MCP Server for Memoria - AI Memory System."""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.server.sse import SseServerTransport
from mcp.types import (
    Resource,
    TextContent,
    Tool,
)
from starlette.applications import Starlette
from starlette.responses import Response
from starlette.routing import Mount, Route

from mcp_memoria.config.settings import Settings, get_settings
from mcp_memoria.core.memory_manager import MemoryManager
from mcp_memoria.core.memory_types import MemoryType
from mcp_memoria.core.graph_types import RelationType, RelationDirection

# Check PostgreSQL availability for graph and work tracking features
try:
    from mcp_memoria.db import ASYNCPG_AVAILABLE, Database
    from mcp_memoria.core.graph_manager import GraphManager
    from mcp_memoria.work import WorkTracker
except ImportError:
    ASYNCPG_AVAILABLE = False
    Database = None
    GraphManager = None
    WorkTracker = None

logger = logging.getLogger(__name__)


class MemoriaServer:
    """MCP Server providing AI memory capabilities."""

    def __init__(self, settings: Settings | None = None):
        """Initialize the Memoria server.

        Args:
            settings: Application settings
        """
        self.settings = settings or get_settings()
        self.memory_manager = MemoryManager(self.settings)
        self.server = Server("memoria")

        # Initialize GraphManager and WorkTracker if PostgreSQL is available
        self.graph_manager: GraphManager | None = None
        self._work_tracker: "WorkTracker | None" = None
        self._db: Database | None = None
        if ASYNCPG_AVAILABLE and self.settings.database_url:
            logger.info("PostgreSQL available, graph and work tracking features enabled")
        else:
            logger.debug("PostgreSQL not configured, graph and work tracking features disabled")

        # Register handlers
        self._register_tools()
        self._register_resources()

    def _register_tools(self) -> None:
        """Register MCP tools."""

        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            """List available tools."""
            return [
                Tool(
                    name="memoria_store",
                    description="Store information in persistent memory. Use for facts, events, procedures, or any information worth remembering.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "content": {
                                "type": "string",
                                "description": "Content to memorize",
                            },
                            "memory_type": {
                                "type": "string",
                                "enum": ["episodic", "semantic", "procedural"],
                                "default": "episodic",
                                "description": "Type of memory: episodic (events/conversations), semantic (facts/knowledge), procedural (procedures/workflows)",
                            },
                            "tags": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Tags for categorization",
                            },
                            "importance": {
                                "type": "number",
                                "minimum": 0,
                                "maximum": 1,
                                "default": 0.5,
                                "description": "Importance score (0-1)",
                            },
                            "project": {
                                "type": "string",
                                "description": "Associated project name",
                            },
                        },
                        "required": ["content"],
                    },
                ),
                Tool(
                    name="memoria_recall",
                    description="Recall memories similar to a query. Use to retrieve relevant past information, decisions, or context.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "What to search for",
                            },
                            "memory_types": {
                                "type": "array",
                                "items": {
                                    "type": "string",
                                    "enum": ["episodic", "semantic", "procedural"],
                                },
                                "description": "Types to search (all if omitted)",
                            },
                            "limit": {
                                "type": "integer",
                                "default": 5,
                                "description": "Maximum results",
                            },
                            "min_score": {
                                "type": "number",
                                "default": 0.5,
                                "description": "Minimum similarity score",
                            },
                            "text_match": {
                                "type": "string",
                                "description": "Optional keyword that must appear in the memory content (full-text match)",
                            },
                        },
                        "required": ["query"],
                    },
                ),
                Tool(
                    name="memoria_search",
                    description="Advanced memory search with filters. Use for specific queries by tags, date, importance, or project.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Semantic search query (optional)",
                            },
                            "memory_type": {
                                "type": "string",
                                "enum": ["episodic", "semantic", "procedural"],
                                "description": "Filter by memory type",
                            },
                            "tags": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Filter by tags",
                            },
                            "project": {
                                "type": "string",
                                "description": "Filter by project",
                            },
                            "importance_min": {
                                "type": "number",
                                "description": "Minimum importance",
                            },
                            "limit": {
                                "type": "integer",
                                "default": 10,
                            },
                            "sort_by": {
                                "type": "string",
                                "enum": ["relevance", "date", "importance", "access_count"],
                                "default": "relevance",
                            },
                            "text_match": {
                                "type": "string",
                                "description": "Optional keyword that must appear in the memory content (full-text match)",
                            },
                        },
                    },
                ),
                Tool(
                    name="memoria_update",
                    description="Update an existing memory. Use to correct or enhance stored information.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "memory_id": {
                                "type": "string",
                                "description": "ID of memory to update",
                            },
                            "memory_type": {
                                "type": "string",
                                "enum": ["episodic", "semantic", "procedural"],
                                "description": "Memory type",
                            },
                            "content": {
                                "type": "string",
                                "description": "New content",
                            },
                            "tags": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "importance": {
                                "type": "number",
                            },
                        },
                        "required": ["memory_id", "memory_type"],
                    },
                ),
                Tool(
                    name="memoria_delete",
                    description="Delete memories by ID or filter. Use carefully.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "memory_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "IDs to delete",
                            },
                            "memory_type": {
                                "type": "string",
                                "enum": ["episodic", "semantic", "procedural"],
                            },
                            "filter_tags": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Delete memories with these tags",
                            },
                        },
                    },
                ),
                Tool(
                    name="memoria_consolidate",
                    description="Consolidate memories by merging similar ones and forgetting old unused ones.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "similarity_threshold": {
                                "type": "number",
                                "default": 0.9,
                                "description": "Threshold for merging similar memories",
                            },
                            "forget_days": {
                                "type": "integer",
                                "default": 30,
                                "description": "Days before forgetting unused memories",
                            },
                            "dry_run": {
                                "type": "boolean",
                                "default": True,
                                "description": "Preview without making changes",
                            },
                        },
                    },
                ),
                Tool(
                    name="memoria_export",
                    description="Export memories to a file for backup or sharing.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "output_path": {
                                "type": "string",
                                "description": "Output file path",
                            },
                            "format": {
                                "type": "string",
                                "enum": ["json", "jsonl"],
                                "default": "json",
                            },
                            "memory_types": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Types to export (all if omitted)",
                            },
                            "include_vectors": {
                                "type": "boolean",
                                "default": False,
                            },
                        },
                        "required": ["output_path"],
                    },
                ),
                Tool(
                    name="memoria_import",
                    description="Import memories from a backup file.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "input_path": {
                                "type": "string",
                                "description": "Input file path",
                            },
                            "merge": {
                                "type": "boolean",
                                "default": True,
                                "description": "Merge with existing (false to replace)",
                            },
                        },
                        "required": ["input_path"],
                    },
                ),
                Tool(
                    name="memoria_stats",
                    description="Get memory system statistics.",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                    },
                ),
                Tool(
                    name="memoria_set_context",
                    description="Set current context (project, file, etc.) for better memory organization.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project": {
                                "type": "string",
                                "description": "Current project name",
                            },
                            "file": {
                                "type": "string",
                                "description": "Current file path",
                            },
                        },
                    },
                ),
                # Graph tools (require PostgreSQL)
                Tool(
                    name="memoria_link",
                    description="Create a relationship between two memories. Use to connect related info, mark cause-effect, or link problems to solutions. Requires PostgreSQL.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "source_id": {
                                "type": "string",
                                "description": "ID of the source memory",
                            },
                            "target_id": {
                                "type": "string",
                                "description": "ID of the target memory",
                            },
                            "relation_type": {
                                "type": "string",
                                "enum": ["causes", "fixes", "supports", "opposes", "follows", "supersedes", "derives", "part_of", "related"],
                                "description": "Type of relationship",
                            },
                            "weight": {
                                "type": "number",
                                "minimum": 0,
                                "maximum": 1,
                                "default": 1.0,
                                "description": "Strength of relationship (0-1)",
                            },
                        },
                        "required": ["source_id", "target_id", "relation_type"],
                    },
                ),
                Tool(
                    name="memoria_unlink",
                    description="Remove a relationship between two memories. Requires PostgreSQL.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "source_id": {
                                "type": "string",
                                "description": "ID of the source memory",
                            },
                            "target_id": {
                                "type": "string",
                                "description": "ID of the target memory",
                            },
                            "relation_type": {
                                "type": "string",
                                "enum": ["causes", "fixes", "supports", "opposes", "follows", "supersedes", "derives", "part_of", "related"],
                                "description": "Type to remove (removes all if omitted)",
                            },
                        },
                        "required": ["source_id", "target_id"],
                    },
                ),
                Tool(
                    name="memoria_related",
                    description="Find memories related to a given memory through the knowledge graph. Requires PostgreSQL.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "memory_id": {
                                "type": "string",
                                "description": "ID of the memory to find relations for",
                            },
                            "depth": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 5,
                                "default": 1,
                                "description": "How many hops to traverse",
                            },
                            "relation_types": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Filter by relation types",
                            },
                            "direction": {
                                "type": "string",
                                "enum": ["out", "in", "both"],
                                "default": "both",
                                "description": "Direction to traverse",
                            },
                        },
                        "required": ["memory_id"],
                    },
                ),
                Tool(
                    name="memoria_path",
                    description="Find the shortest path between two memories in the knowledge graph. Requires PostgreSQL.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "from_id": {
                                "type": "string",
                                "description": "Starting memory ID",
                            },
                            "to_id": {
                                "type": "string",
                                "description": "Target memory ID",
                            },
                            "max_depth": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 10,
                                "default": 5,
                                "description": "Maximum path length",
                            },
                        },
                        "required": ["from_id", "to_id"],
                    },
                ),
                Tool(
                    name="memoria_suggest_links",
                    description="Get AI-powered suggestions for relationships based on content similarity. Requires PostgreSQL.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "memory_id": {
                                "type": "string",
                                "description": "Memory to find suggestions for",
                            },
                            "limit": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 20,
                                "default": 5,
                                "description": "Maximum suggestions to return",
                            },
                        },
                        "required": ["memory_id"],
                    },
                ),
                # Work tracking tools
                Tool(
                    name="memoria_work_start",
                    description="Start tracking a work session. Use to log time spent on tasks, issues, or projects. Requires PostgreSQL.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "description": {
                                "type": "string",
                                "description": "What you're working on",
                            },
                            "category": {
                                "type": "string",
                                "enum": ["coding", "review", "meeting", "support", "research", "documentation", "devops", "other"],
                                "default": "coding",
                                "description": "Type of work",
                            },
                            "client": {
                                "type": "string",
                                "description": "Client name (optional)",
                            },
                            "project": {
                                "type": "string",
                                "description": "Project name (optional)",
                            },
                            "issue": {
                                "type": "integer",
                                "description": "GitHub issue number (optional)",
                            },
                            "pr": {
                                "type": "integer",
                                "description": "GitHub PR number (optional)",
                            },
                            "branch": {
                                "type": "string",
                                "description": "Git branch name (optional)",
                            },
                        },
                        "required": ["description"],
                    },
                ),
                Tool(
                    name="memoria_work_stop",
                    description="Stop the active work session. Returns duration and session summary. Requires PostgreSQL.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "session_id": {
                                "type": "string",
                                "description": "Session ID to stop (defaults to active session)",
                            },
                            "notes": {
                                "type": "string",
                                "description": "Notes about what was accomplished",
                            },
                        },
                    },
                ),
                Tool(
                    name="memoria_work_status",
                    description="Check if a work session is active and get its details. Requires PostgreSQL.",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                    },
                ),
                Tool(
                    name="memoria_work_pause",
                    description="Pause the active work session (e.g., for lunch break). Requires PostgreSQL.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "reason": {
                                "type": "string",
                                "description": "Reason for pausing (optional)",
                            },
                        },
                    },
                ),
                Tool(
                    name="memoria_work_resume",
                    description="Resume a paused work session. Requires PostgreSQL.",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                    },
                ),
                Tool(
                    name="memoria_work_note",
                    description="Add a note to the active work session. Requires PostgreSQL.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "note": {
                                "type": "string",
                                "description": "Note to add",
                            },
                            "session_id": {
                                "type": "string",
                                "description": "Session ID (defaults to active session)",
                            },
                        },
                        "required": ["note"],
                    },
                ),
                Tool(
                    name="memoria_work_report",
                    description="Generate a time tracking report. Group by client, project, or category. Requires PostgreSQL.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "period": {
                                "type": "string",
                                "enum": ["today", "week", "month", "year", "all"],
                                "default": "month",
                                "description": "Time period for report",
                            },
                            "start_date": {
                                "type": "string",
                                "description": "Custom start date (ISO format)",
                            },
                            "end_date": {
                                "type": "string",
                                "description": "Custom end date (ISO format)",
                            },
                            "group_by": {
                                "type": "string",
                                "enum": ["client", "project", "category"],
                                "description": "Group results by",
                            },
                            "client": {
                                "type": "string",
                                "description": "Filter by client name",
                            },
                            "project": {
                                "type": "string",
                                "description": "Filter by project name",
                            },
                            "category": {
                                "type": "string",
                                "enum": ["coding", "review", "meeting", "support", "research", "documentation", "devops", "other"],
                                "description": "Filter by category",
                            },
                        },
                    },
                ),
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
            """Handle tool calls."""
            try:
                result = await self._handle_tool(name, arguments)
                return [TextContent(type="text", text=result)]
            except Exception as e:
                # Log full traceback for debugging, but only return safe error message
                import traceback
                logger.error(f"Tool {name} failed: {e}\n{traceback.format_exc()}")
                # Return user-friendly error without exposing internal details
                return [TextContent(type="text", text=f"Error: {str(e)}")]

    async def _handle_tool(self, name: str, args: dict[str, Any]) -> str:
        """Handle individual tool calls.

        Args:
            name: Tool name
            args: Tool arguments

        Returns:
            Result string
        """
        if name == "memoria_store":
            memory = await self.memory_manager.store(
                content=args["content"],
                memory_type=args.get("memory_type", "episodic"),
                tags=args.get("tags"),
                importance=args.get("importance", 0.5),
                metadata={"project": args.get("project")} if args.get("project") else None,
            )
            return f"Stored memory: {memory.id} ({memory.memory_type.value})"

        elif name == "memoria_recall":
            results = await self.memory_manager.recall(
                query=args["query"],
                memory_types=args.get("memory_types"),
                limit=args.get("limit", 5),
                min_score=args.get("min_score", 0.5),
                text_match=args.get("text_match"),
            )

            if not results:
                return "No memories found matching your query."

            output = [f"Found {len(results)} memories:\n"]
            for i, r in enumerate(results, 1):
                output.append(
                    f"{i}. [{r.memory.memory_type.value}] (score: {r.score:.2f})\n"
                    f"   ID: {r.memory.id}\n"
                    f"   Content: {r.memory.content[:200]}{'...' if len(r.memory.content) > 200 else ''}\n"
                    f"   Tags: {', '.join(r.memory.tags) if r.memory.tags else 'none'}\n"
                )
            return "\n".join(output)

        elif name == "memoria_search":
            results = await self.memory_manager.search(
                query=args.get("query"),
                memory_type=args.get("memory_type"),
                tags=args.get("tags"),
                importance_min=args.get("importance_min"),
                project=args.get("project"),
                limit=args.get("limit", 10),
                sort_by=args.get("sort_by", "relevance"),
                text_match=args.get("text_match"),
            )

            if not results:
                return "No memories found matching your criteria."

            output = [f"Found {len(results)} memories:\n"]
            for i, r in enumerate(results, 1):
                output.append(
                    f"{i}. [{r.memory.memory_type.value}] importance: {r.memory.importance:.2f}\n"
                    f"   ID: {r.memory.id}\n"
                    f"   Content: {r.memory.content[:150]}...\n"
                )
            return "\n".join(output)

        elif name == "memoria_update":
            memory = await self.memory_manager.update(
                memory_id=args["memory_id"],
                memory_type=args["memory_type"],
                content=args.get("content"),
                tags=args.get("tags"),
                importance=args.get("importance"),
            )
            if memory:
                return f"Updated memory: {memory.id}"
            return "Memory not found."

        elif name == "memoria_delete":
            if args.get("memory_ids"):
                count = await self.memory_manager.delete(
                    memory_ids=args["memory_ids"],
                    memory_type=args.get("memory_type"),
                )
            elif args.get("filter_tags"):
                count = await self.memory_manager.delete(
                    memory_type=args.get("memory_type"),
                    filters={"tags": args["filter_tags"]},
                )
            else:
                return "Specify memory_ids or filter_tags to delete."
            return f"Deleted {count} memories."

        elif name == "memoria_consolidate":
            results = await self.memory_manager.consolidate(
                similarity_threshold=args.get("similarity_threshold"),
                forget_days=args.get("forget_days"),
                min_importance=args.get("min_importance"),
                dry_run=args.get("dry_run", True),
            )

            output = ["Consolidation results:\n"]
            for collection, result in results.items():
                output.append(
                    f"  {collection}:\n"
                    f"    - Merged: {result.merged_count}\n"
                    f"    - Forgotten: {result.forgotten_count}\n"
                    f"    - Duration: {result.duration_seconds:.2f}s\n"
                )
            if args.get("dry_run", True):
                output.append("\n(Dry run - no changes made)")
            return "\n".join(output)

        elif name == "memoria_export":
            result = await self.memory_manager.export(
                output_path=Path(args["output_path"]),
                format=args.get("format", "json"),
                memory_types=args.get("memory_types"),
                include_vectors=args.get("include_vectors", False),
            )
            return f"Exported {result['total_memories']} memories to {result['output_path']}"

        elif name == "memoria_import":
            result = await self.memory_manager.import_memories(
                input_path=Path(args["input_path"]),
                merge=args.get("merge", True),
            )
            return f"Imported {result['total_imported']} memories from {result['source_file']}"

        elif name == "memoria_stats":
            stats = self.memory_manager.get_stats()

            output = [
                f"Total memories: {stats['total_memories']}\n",
                "\nCollections:",
            ]
            for name, info in stats["collections"].items():
                if isinstance(info, dict) and "points_count" in info:
                    output.append(f"  - {name}: {info['points_count']} memories")
                else:
                    output.append(f"  - {name}: not initialized")

            output.append(f"\nEmbedding model: {stats['embedding_model']['model']}")
            output.append(f"Working memory items: {stats['working_memory']['cached_memories']}")

            return "\n".join(output)

        elif name == "memoria_set_context":
            if args.get("project"):
                self.memory_manager.working_memory.set_current_project(args["project"])
            if args.get("file"):
                self.memory_manager.working_memory.set_current_file(args["file"])
            return "Context updated."

        # Graph tools
        elif name == "memoria_link":
            gm = await self._get_graph_manager()
            if not gm:
                return "Error: Graph features require PostgreSQL. Set MEMORIA_DATABASE_URL."
            relation = await gm.add_relation(
                source_id=args["source_id"],
                target_id=args["target_id"],
                relation_type=RelationType(args["relation_type"]),
                weight=args.get("weight", 1.0),
            )
            return f"Created {args['relation_type']} relation: {args['source_id']} → {args['target_id']}"

        elif name == "memoria_unlink":
            gm = await self._get_graph_manager()
            if not gm:
                return "Error: Graph features require PostgreSQL. Set MEMORIA_DATABASE_URL."
            count = await gm.remove_relation(
                source_id=args["source_id"],
                target_id=args["target_id"],
                relation_type=RelationType(args["relation_type"]) if args.get("relation_type") else None,
            )
            return f"Removed {count} relation(s): {args['source_id']} → {args['target_id']}"

        elif name == "memoria_related":
            gm = await self._get_graph_manager()
            if not gm:
                return "Error: Graph features require PostgreSQL. Set MEMORIA_DATABASE_URL."
            neighbors = await gm.get_neighbors(
                memory_id=args["memory_id"],
                depth=args.get("depth", 1),
                relation_types=[RelationType(t) for t in args.get("relation_types", [])] if args.get("relation_types") else None,
            )
            if not neighbors:
                return f"No related memories found for {args['memory_id']}"

            output = [f"Found {len(neighbors)} related memories:\n"]
            for n in neighbors:
                output.append(
                    f"  - {n['memory_id']} ({n['relation_type']}, depth={n['depth']})"
                )
            return "\n".join(output)

        elif name == "memoria_path":
            gm = await self._get_graph_manager()
            if not gm:
                return "Error: Graph features require PostgreSQL. Set MEMORIA_DATABASE_URL."
            path = await gm.find_path(
                from_id=args["from_id"],
                to_id=args["to_id"],
                max_depth=args.get("max_depth", 5),
            )
            if path is None:
                return f"No path found between {args['from_id']} and {args['to_id']}"

            output = [f"Path found ({len(path.steps)} steps):\n"]
            for step in path.steps:
                output.append(f"  {step.memory_id} --[{step.relation_type}]--> ")
            return "\n".join(output)

        elif name == "memoria_suggest_links":
            gm = await self._get_graph_manager()
            if not gm:
                return "Error: Graph features require PostgreSQL. Set MEMORIA_DATABASE_URL."
            suggestions = await gm.suggest_relations(
                memory_id=args["memory_id"],
                limit=args.get("limit", 5),
            )
            if not suggestions:
                return f"No relation suggestions found for {args['memory_id']}"

            import json
            return json.dumps([s.model_dump_for_api() for s in suggestions], indent=2)

        # Work tracking tools
        elif name == "memoria_work_start":
            wt = await self._get_work_tracker()
            if not wt:
                return "Error: Work tracking requires PostgreSQL. Set MEMORIA_DATABASE_URL."
            result = await wt.start(
                description=args["description"],
                category=args.get("category", "coding"),
                client=args.get("client"),
                project=args.get("project"),
                issue_number=args.get("issue"),
                pr_number=args.get("pr"),
                branch=args.get("branch"),
            )
            if "error" in result:
                return f"Error: {result['error']}"
            return (
                f"Started work session: {result['session_id']}\n"
                f"  Description: {result['description']}\n"
                f"  Category: {result['category']}\n"
                f"  Started at: {result['started_at']}"
            )

        elif name == "memoria_work_stop":
            wt = await self._get_work_tracker()
            if not wt:
                return "Error: Work tracking requires PostgreSQL. Set MEMORIA_DATABASE_URL."
            result = await wt.stop(
                session_id=args.get("session_id"),
                notes=args.get("notes"),
            )
            if "error" in result:
                return f"Error: {result['error']}"
            return (
                f"Stopped work session: {result['session_id']}\n"
                f"  Description: {result['description']}\n"
                f"  Duration: {result['duration_formatted']} ({result['duration_minutes']} minutes)\n"
                f"  Started: {result['started_at']}\n"
                f"  Ended: {result['ended_at']}"
            )

        elif name == "memoria_work_status":
            wt = await self._get_work_tracker()
            if not wt:
                return "Error: Work tracking requires PostgreSQL. Set MEMORIA_DATABASE_URL."
            result = await wt.status()
            if not result.get("active") and not result.get("paused"):
                return "No active work session."
            status = "paused" if result.get("paused") else "active"
            output = [
                f"Work session ({status}): {result['session_id']}",
                f"  Description: {result['description']}",
                f"  Elapsed: {result.get('elapsed_formatted', f'{result['elapsed_minutes']}m')}",
            ]
            if result.get("client"):
                output.append(f"  Client: {result['client']}")
            if result.get("project"):
                output.append(f"  Project: {result['project']}")
            if result.get("category"):
                output.append(f"  Category: {result['category']}")
            return "\n".join(output)

        elif name == "memoria_work_pause":
            wt = await self._get_work_tracker()
            if not wt:
                return "Error: Work tracking requires PostgreSQL. Set MEMORIA_DATABASE_URL."
            result = await wt.pause(reason=args.get("reason"))
            if "error" in result:
                return f"Error: {result['error']}"
            return f"Paused work session: {result['session_id']}\n  Elapsed: {result['elapsed_minutes']}m"

        elif name == "memoria_work_resume":
            wt = await self._get_work_tracker()
            if not wt:
                return "Error: Work tracking requires PostgreSQL. Set MEMORIA_DATABASE_URL."
            result = await wt.resume()
            if "error" in result:
                return f"Error: {result['error']}"
            return f"Resumed work session: {result['session_id']}\n  Total pause time: {result['total_pause_minutes']}m"

        elif name == "memoria_work_note":
            wt = await self._get_work_tracker()
            if not wt:
                return "Error: Work tracking requires PostgreSQL. Set MEMORIA_DATABASE_URL."
            result = await wt.add_note(
                note=args["note"],
                session_id=args.get("session_id"),
            )
            if "error" in result:
                return f"Error: {result['error']}"
            return f"Added note to session {result['session_id']} ({result['total_notes']} notes total)"

        elif name == "memoria_work_report":
            wt = await self._get_work_tracker()
            if not wt:
                return "Error: Work tracking requires PostgreSQL. Set MEMORIA_DATABASE_URL."
            result = await wt.report(
                period=args.get("period", "month"),
                start_date=args.get("start_date"),
                end_date=args.get("end_date"),
                group_by=args.get("group_by"),
                client=args.get("client"),
                project=args.get("project"),
                category=args.get("category"),
            )
            output = [
                f"Work Report ({result['period']})",
                f"  Total: {result['total_hours']} hours ({result['total_sessions']} sessions)",
            ]
            if result.get("breakdown"):
                output.append("\n  Breakdown:")
                for item in result["breakdown"]:
                    output.append(f"    {item['group']}: {item['hours']}h ({item['percentage']}%)")
            if result.get("recent_sessions"):
                output.append("\n  Recent sessions:")
                for s in result["recent_sessions"][:5]:
                    output.append(f"    [{s['date']}] {s['description'][:40]}... ({s['duration_minutes']}m)")
            return "\n".join(output)

        else:
            return f"Unknown tool: {name}"

    async def _get_graph_manager(self) -> "GraphManager | None":
        """Get or initialize the GraphManager.

        Returns:
            GraphManager if PostgreSQL is available, None otherwise
        """
        if not ASYNCPG_AVAILABLE or not self.settings.database_url:
            return None

        if self.graph_manager is None:
            # Lazy initialization
            self._db = Database(self.settings.database_url)
            await self._db.connect(run_migrations=self.settings.db_migrate)
            self.graph_manager = GraphManager(
                db=self._db,
                qdrant_store=self.memory_manager.vector_store,
            )

        return self.graph_manager

    async def _get_work_tracker(self) -> "WorkTracker | None":
        """Get or initialize the WorkTracker.

        Returns:
            WorkTracker if PostgreSQL is available, None otherwise
        """
        if not ASYNCPG_AVAILABLE or not self.settings.database_url:
            return None

        # Ensure database is connected
        if self._db is None:
            self._db = Database(self.settings.database_url)
            await self._db.connect(run_migrations=self.settings.db_migrate)

        if self._work_tracker is None:
            from mcp_memoria.work import WorkTracker
            self._work_tracker = WorkTracker(self._db)

        return self._work_tracker

    def _register_resources(self) -> None:
        """Register MCP resources."""

        @self.server.list_resources()
        async def list_resources() -> list[Resource]:
            """List available resources."""
            return [
                Resource(
                    uri="memoria://stats",
                    name="Memory Statistics",
                    description="Current memory system statistics",
                    mimeType="application/json",
                ),
                Resource(
                    uri="memoria://episodic",
                    name="Episodic Memories",
                    description="Recent episodic memories (events, conversations)",
                    mimeType="application/json",
                ),
                Resource(
                    uri="memoria://semantic",
                    name="Semantic Memories",
                    description="Semantic memories (facts, knowledge)",
                    mimeType="application/json",
                ),
                Resource(
                    uri="memoria://procedural",
                    name="Procedural Memories",
                    description="Procedural memories (procedures, workflows)",
                    mimeType="application/json",
                ),
                Resource(
                    uri="memoria://context",
                    name="Current Context",
                    description="Current working memory context",
                    mimeType="application/json",
                ),
            ]

        @self.server.read_resource()
        async def read_resource(uri: str) -> str:
            """Read a resource."""
            import json

            if uri == "memoria://stats":
                stats = self.memory_manager.get_stats()
                return json.dumps(stats, indent=2, default=str)

            elif uri == "memoria://context":
                context = self.memory_manager.working_memory.get_all_context()
                return json.dumps(context, indent=2, default=str)

            elif uri in ["memoria://episodic", "memoria://semantic", "memoria://procedural"]:
                memory_type = uri.split("://")[1]
                results = await self.memory_manager.search(
                    memory_type=memory_type,
                    limit=20,
                    sort_by="date",
                )
                memories = [
                    {
                        "id": r.memory.id,
                        "content": r.memory.content[:200],
                        "tags": r.memory.tags,
                        "importance": r.memory.importance,
                        "created_at": r.memory.created_at.isoformat(),
                    }
                    for r in results
                ]
                return json.dumps(memories, indent=2)

            return f"Unknown resource: {uri}"

    async def initialize(self) -> bool:
        """Initialize the server.

        Returns:
            True if successful
        """
        return await self.memory_manager.initialize()

    async def run(self) -> None:
        """Run the MCP server with stdio transport."""
        # Initialize memory system
        if not await self.initialize():
            logger.error("Failed to initialize memory system")
            return

        logger.info("Starting Memoria MCP server (stdio mode)...")

        # Run the server
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options(),
            )

    async def run_http(self, port: int, host: str = "0.0.0.0") -> None:
        """Run the MCP server with HTTP/SSE transport.

        Args:
            port: HTTP port to listen on
            host: Host to bind to (default: 0.0.0.0)
        """
        import uvicorn

        # Initialize memory system
        if not await self.initialize():
            logger.error("Failed to initialize memory system")
            return

        logger.info(f"Starting Memoria MCP server (HTTP mode on {host}:{port})...")

        # Create SSE transport
        sse = SseServerTransport("/messages/")

        async def handle_sse(request):  # type: ignore[no-untyped-def]
            """Handle SSE connection requests."""
            async with sse.connect_sse(
                request.scope, request.receive, request._send
            ) as streams:
                await self.server.run(
                    streams[0],
                    streams[1],
                    self.server.create_initialization_options(),
                )
            return Response()

        async def handle_health(request):  # type: ignore[no-untyped-def]
            """Health check endpoint."""
            return Response(content="OK", media_type="text/plain")

        # Create Starlette app
        app = Starlette(
            debug=False,
            routes=[
                Route("/health", endpoint=handle_health),
                Route("/sse", endpoint=handle_sse),
                Mount("/messages/", app=sse.handle_post_message),
            ],
        )

        # Run with uvicorn
        config = uvicorn.Config(
            app,
            host=host,
            port=port,
            log_level="info",
        )
        server = uvicorn.Server(config)
        await server.serve()


async def main() -> None:
    """Main entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    server = MemoriaServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
