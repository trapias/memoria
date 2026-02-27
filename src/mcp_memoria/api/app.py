"""
FastAPI application factory for Memoria REST API.
"""

import os
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .. import __version__
from ..config.settings import Settings
from ..core.memory_manager import MemoryManager
from ..db import ASYNCPG_AVAILABLE
from .routes import memories, graph, stats, backup, data

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler for startup/shutdown."""
    # Initialize settings
    settings = Settings()

    # Initialize memory manager (creates its own QdrantStore internally)
    memory_manager = MemoryManager(settings)

    # Store in app state
    app.state.settings = settings
    app.state.memory_manager = memory_manager
    app.state.qdrant_store = memory_manager.vector_store

    # Initialize GraphManager if PostgreSQL is available
    if ASYNCPG_AVAILABLE and settings.database_url:
        from ..db import Database
        from ..core.graph_manager import GraphManager

        try:
            database = Database(settings.database_url)
            await database.connect(run_migrations=settings.db_migrate)
            graph_manager = GraphManager(database, memory_manager.vector_store)
            app.state.database = database
            app.state.graph_manager = graph_manager
            logger.info("GraphManager initialized with PostgreSQL")
        except Exception as e:
            logger.warning(f"Failed to initialize GraphManager: {e}")
            app.state.database = None
            app.state.graph_manager = None
    else:
        logger.info("PostgreSQL not available, GraphManager disabled")
        app.state.database = None
        app.state.graph_manager = None

    yield

    # Cleanup
    if hasattr(app.state, 'database') and app.state.database:
        await app.state.database.close()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Memoria API",
        description="REST API for Memoria knowledge graph and memory management",
        version="2.0.0",
        lifespan=lifespan,
    )

    # Configure CORS - default allows all origins for local network access
    cors_origins_str = os.environ.get("CORS_ORIGINS", "*")
    cors_origins = (
        ["*"] if cors_origins_str.strip() == "*"
        else [o.strip() for o in cors_origins_str.split(",")]
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(memories.router, prefix="/api/memories", tags=["memories"])
    app.include_router(graph.router, prefix="/api/graph", tags=["graph"])
    app.include_router(stats.router, prefix="/api", tags=["stats"])
    app.include_router(backup.router, prefix="/api/backup", tags=["backup"])
    app.include_router(data.router, prefix="/api/data", tags=["data"])

    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "ok", "version": __version__}

    return app
