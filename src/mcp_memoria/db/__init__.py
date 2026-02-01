"""PostgreSQL database module for relational data storage.

This module provides async PostgreSQL connectivity for storing
relational data (clients, projects, work sessions, memory relations)
that complements Qdrant's vector storage.

Note: Requires the 'postgres' optional dependency:
    pip install mcp-memoria[postgres]
"""

from __future__ import annotations

import logging

from mcp_memoria.db.exceptions import (
    ConnectionError,
    DatabaseError,
    MigrationError,
    PoolExhaustedError,
    QueryError,
    RecordNotFoundError,
    TransactionError,
)
from mcp_memoria.db.models import (
    Client,
    DailyTotal,
    GraphNeighbor,
    GraphPath,
    MemoryRelation,
    MonthlySummary,
    PauseEntry,
    Project,
    RelationCreator,
    RelationType,
    SessionCategory,
    SessionStatus,
    UserSetting,
    WorkSession,
)

logger = logging.getLogger(__name__)

# Check if asyncpg is available
try:
    import asyncpg  # noqa: F401

    ASYNCPG_AVAILABLE = True
except ImportError:
    ASYNCPG_AVAILABLE = False
    logger.debug("asyncpg not installed - PostgreSQL features disabled")

__all__ = [
    # Availability flag
    "ASYNCPG_AVAILABLE",
    # Exceptions
    "DatabaseError",
    "ConnectionError",
    "MigrationError",
    "QueryError",
    "TransactionError",
    "PoolExhaustedError",
    "RecordNotFoundError",
    # Models
    "Client",
    "Project",
    "WorkSession",
    "MemoryRelation",
    "UserSetting",
    "PauseEntry",
    "GraphNeighbor",
    "GraphPath",
    "MonthlySummary",
    "DailyTotal",
    # Enums
    "SessionCategory",
    "SessionStatus",
    "RelationType",
    "RelationCreator",
]

# Only export Database and repositories if asyncpg is available
if ASYNCPG_AVAILABLE:
    from mcp_memoria.db.database import (
        Database as Database,
    )
    from mcp_memoria.db.database import (
        create_database_from_settings as create_database_from_settings,
    )
    from mcp_memoria.db.repositories import (
        ClientRepository as ClientRepository,
    )
    from mcp_memoria.db.repositories import (
        MemoryRelationRepository as MemoryRelationRepository,
    )
    from mcp_memoria.db.repositories import (
        ProjectRepository as ProjectRepository,
    )
    from mcp_memoria.db.repositories import (
        ReportRepository as ReportRepository,
    )
    from mcp_memoria.db.repositories import (
        UserSettingRepository as UserSettingRepository,
    )
    from mcp_memoria.db.repositories import (
        WorkSessionRepository as WorkSessionRepository,
    )

    __all__.extend([
        # Core
        "Database",
        "create_database_from_settings",
        # Repositories
        "ClientRepository",
        "ProjectRepository",
        "WorkSessionRepository",
        "MemoryRelationRepository",
        "UserSettingRepository",
        "ReportRepository",
    ])
