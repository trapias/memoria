"""Core memory management module."""

from mcp_memoria.core.memory_types import (
    EpisodicMemory,
    MemoryItem,
    MemoryType,
    ProceduralMemory,
    SemanticMemory,
)
from mcp_memoria.core.memory_manager import MemoryManager
from mcp_memoria.core.working_memory import WorkingMemory
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

__all__ = [
    # Memory types
    "MemoryItem",
    "MemoryType",
    "EpisodicMemory",
    "SemanticMemory",
    "ProceduralMemory",
    # Core managers
    "MemoryManager",
    "WorkingMemory",
    # Graph types
    "GraphEdge",
    "GraphNode",
    "GraphPath",
    "PathStep",
    "Relation",
    "RelationCreator",
    "RelationDirection",
    "RelationSuggestion",
    "RelationType",
    "RelationWithContext",
    "Subgraph",
]

# Conditionally export GraphManager if PostgreSQL is available
try:
    from mcp_memoria.core.graph_manager import GraphManager, GraphManagerError

    __all__.extend(["GraphManager", "GraphManagerError"])
except ImportError:
    pass  # PostgreSQL not available
