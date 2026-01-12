"""MCP Server for Memoria - AI Memory System."""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Resource,
    TextContent,
    Tool,
)

from mcp_memoria.config.settings import Settings, get_settings
from mcp_memoria.core.memory_manager import MemoryManager
from mcp_memoria.core.memory_types import MemoryType

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
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
            """Handle tool calls."""
            try:
                result = await self._handle_tool(name, arguments)
                return [TextContent(type="text", text=result)]
            except Exception as e:
                import traceback
                tb = traceback.format_exc()
                logger.error(f"Tool {name} failed: {e}\n{tb}")
                return [TextContent(type="text", text=f"Error: {str(e)}\nTraceback:\n{tb}")]

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

        else:
            return f"Unknown tool: {name}"

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
        """Run the MCP server."""
        # Initialize memory system
        if not await self.initialize():
            logger.error("Failed to initialize memory system")
            return

        logger.info("Starting Memoria MCP server...")

        # Run the server
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options(),
            )


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
