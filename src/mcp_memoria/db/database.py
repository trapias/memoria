"""Async PostgreSQL database connection pool and operations.

Provides a Database class with lifecycle management, connection pooling,
and auto-migration support for the MCP Memoria relational data layer.
"""

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, TypeVar

import asyncpg
from asyncpg import Connection, Pool, Record

from mcp_memoria.db.exceptions import (
    ConnectionError,
    PoolExhaustedError,
    QueryError,
    TransactionError,
)
from mcp_memoria.db.migrations import MigrationRunner

logger = logging.getLogger(__name__)

T = TypeVar("T")


class Database:
    """Async PostgreSQL database with connection pooling.

    Features:
    - Async connection pool with configurable size
    - Auto-migration support on startup
    - Transaction context manager
    - Prepared statement support
    - Comprehensive error handling

    Usage:
        db = Database(database_url)
        await db.connect()

        # Simple query
        rows = await db.fetch("SELECT * FROM clients WHERE name = $1", name)

        # Transaction
        async with db.transaction() as conn:
            await conn.execute("INSERT INTO clients (name) VALUES ($1)", name)
            await conn.execute("INSERT INTO projects (client_id, name) VALUES ($1, $2)", client_id, project)

        await db.close()
    """

    def __init__(
        self,
        database_url: str,
        min_pool_size: int = 2,
        max_pool_size: int = 10,
        command_timeout: float = 60.0,
        statement_cache_size: int = 100,
    ):
        """Initialize database configuration.

        Args:
            database_url: PostgreSQL connection URL
            min_pool_size: Minimum connections to maintain
            max_pool_size: Maximum connections allowed
            command_timeout: Default query timeout in seconds
            statement_cache_size: Number of prepared statements to cache
        """
        self._database_url = database_url
        self._min_pool_size = min_pool_size
        self._max_pool_size = max_pool_size
        self._command_timeout = command_timeout
        self._statement_cache_size = statement_cache_size

        self._pool: Pool | None = None
        self._connected = False
        self._connect_lock = asyncio.Lock()

    @property
    def is_connected(self) -> bool:
        """Check if database is connected."""
        return self._connected and self._pool is not None

    @property
    def pool_size(self) -> int:
        """Get current pool size."""
        if self._pool:
            return self._pool.get_size()
        return 0

    @property
    def pool_free_size(self) -> int:
        """Get number of free connections in pool."""
        if self._pool:
            return self._pool.get_idle_size()
        return 0

    async def connect(self, run_migrations: bool = False) -> None:
        """Connect to database and optionally run migrations.

        Args:
            run_migrations: If True, run pending migrations after connecting

        Raises:
            ConnectionError: If connection fails
        """
        async with self._connect_lock:
            if self._connected:
                logger.debug("Database already connected")
                return

            try:
                logger.info("Connecting to PostgreSQL...")

                self._pool = await asyncpg.create_pool(
                    self._database_url,
                    min_size=self._min_pool_size,
                    max_size=self._max_pool_size,
                    command_timeout=self._command_timeout,
                    statement_cache_size=self._statement_cache_size,
                    setup=self._setup_connection,
                )

                self._connected = True
                logger.info(
                    f"PostgreSQL connected (pool: {self._min_pool_size}-{self._max_pool_size})"
                )

                if run_migrations:
                    await self.run_migrations()

            except asyncpg.PostgresError as e:
                raise ConnectionError("Failed to connect to PostgreSQL", cause=e) from e
            except Exception as e:
                raise ConnectionError(f"Unexpected error connecting: {e}", cause=e) from e

    async def _setup_connection(self, conn: Connection) -> None:
        """Setup callback for new connections.

        Registers custom type codecs for JSONB, UUID arrays, etc.
        """
        # Enable JSONB codec
        await conn.set_type_codec(
            "jsonb",
            encoder=lambda v: v,
            decoder=lambda v: v,
            schema="pg_catalog",
            format="text",
        )

    async def close(self) -> None:
        """Close database connection pool.

        Waits for all connections to be released before closing.
        """
        async with self._connect_lock:
            if self._pool:
                logger.info("Closing PostgreSQL connection pool...")
                await self._pool.close()
                self._pool = None
                self._connected = False
                logger.info("PostgreSQL connection closed")

    async def run_migrations(self) -> int:
        """Run pending database migrations.

        Returns:
            Number of migrations applied

        Raises:
            MigrationError: If migration fails
        """
        if not self._pool:
            raise ConnectionError("Database not connected")

        migrations_dir = Path(__file__).parent / "migrations"
        runner = MigrationRunner(self._pool, migrations_dir)
        return await runner.run()

    def _ensure_connected(self) -> Pool:
        """Ensure database is connected and return pool.

        Returns:
            Connection pool

        Raises:
            ConnectionError: If not connected
        """
        if not self._connected or not self._pool:
            raise ConnectionError("Database not connected. Call connect() first.")
        return self._pool

    @asynccontextmanager
    async def acquire(
        self,
        timeout: float | None = None,
    ) -> AsyncGenerator[Connection, None]:
        """Acquire a connection from the pool.

        Args:
            timeout: Optional timeout for acquiring connection

        Yields:
            Database connection

        Raises:
            PoolExhaustedError: If pool is exhausted and timeout expires
        """
        pool = self._ensure_connected()

        try:
            async with pool.acquire(timeout=timeout) as conn:
                yield conn
        except TimeoutError as e:
            raise PoolExhaustedError(timeout) from e
        except asyncpg.PostgresError as e:
            raise ConnectionError("Failed to acquire connection", cause=e) from e

    @asynccontextmanager
    async def transaction(
        self,
        isolation: str = "read_committed",
        readonly: bool = False,
    ) -> AsyncGenerator[Connection, None]:
        """Execute operations within a transaction.

        Args:
            isolation: Transaction isolation level
            readonly: If True, transaction is read-only

        Yields:
            Database connection within transaction

        Example:
            async with db.transaction() as conn:
                await conn.execute("INSERT INTO ...")
                await conn.execute("UPDATE ...")
        """
        async with self.acquire() as conn:
            try:
                async with conn.transaction(
                    isolation=isolation,
                    readonly=readonly,
                ):
                    yield conn
            except asyncpg.PostgresError as e:
                raise TransactionError("Transaction failed", cause=e) from e

    async def execute(
        self,
        query: str,
        *args: Any,
        timeout: float | None = None,
    ) -> str:
        """Execute a query without returning results.

        Args:
            query: SQL query
            *args: Query parameters
            timeout: Optional query timeout

        Returns:
            Command status string (e.g., "INSERT 0 1")

        Raises:
            QueryError: If query fails
        """
        async with self.acquire() as conn:
            try:
                return await conn.execute(query, *args, timeout=timeout)
            except asyncpg.PostgresError as e:
                raise QueryError("Execute failed", query=query, cause=e) from e

    async def executemany(
        self,
        query: str,
        args: list[tuple[Any, ...]],
        timeout: float | None = None,
    ) -> None:
        """Execute a query with multiple parameter sets.

        Args:
            query: SQL query
            args: List of parameter tuples
            timeout: Optional query timeout

        Raises:
            QueryError: If query fails
        """
        async with self.acquire() as conn:
            try:
                await conn.executemany(query, args, timeout=timeout)
            except asyncpg.PostgresError as e:
                raise QueryError("Executemany failed", query=query, cause=e) from e

    async def fetch(
        self,
        query: str,
        *args: Any,
        timeout: float | None = None,
    ) -> list[Record]:
        """Execute query and return all rows.

        Args:
            query: SQL query
            *args: Query parameters
            timeout: Optional query timeout

        Returns:
            List of records

        Raises:
            QueryError: If query fails
        """
        async with self.acquire() as conn:
            try:
                return await conn.fetch(query, *args, timeout=timeout)
            except asyncpg.PostgresError as e:
                raise QueryError("Fetch failed", query=query, cause=e) from e

    async def fetchrow(
        self,
        query: str,
        *args: Any,
        timeout: float | None = None,
    ) -> Record | None:
        """Execute query and return first row.

        Args:
            query: SQL query
            *args: Query parameters
            timeout: Optional query timeout

        Returns:
            First record or None

        Raises:
            QueryError: If query fails
        """
        async with self.acquire() as conn:
            try:
                return await conn.fetchrow(query, *args, timeout=timeout)
            except asyncpg.PostgresError as e:
                raise QueryError("Fetchrow failed", query=query, cause=e) from e

    async def fetchval(
        self,
        query: str,
        *args: Any,
        column: int = 0,
        timeout: float | None = None,
    ) -> Any:
        """Execute query and return a single value.

        Args:
            query: SQL query
            *args: Query parameters
            column: Column index to return
            timeout: Optional query timeout

        Returns:
            Single value from first row

        Raises:
            QueryError: If query fails
        """
        async with self.acquire() as conn:
            try:
                return await conn.fetchval(query, *args, column=column, timeout=timeout)
            except asyncpg.PostgresError as e:
                raise QueryError("Fetchval failed", query=query, cause=e) from e

    async def health_check(self) -> bool:
        """Check database health.

        Returns:
            True if database is healthy

        Raises:
            DatabaseError: If health check fails
        """
        try:
            result = await self.fetchval("SELECT 1")
            return result == 1
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    async def get_stats(self) -> dict[str, Any]:
        """Get database connection pool statistics.

        Returns:
            Dictionary with pool stats
        """
        pool = self._ensure_connected()

        return {
            "connected": self._connected,
            "pool_size": pool.get_size(),
            "pool_min_size": pool.get_min_size(),
            "pool_max_size": pool.get_max_size(),
            "pool_free_size": pool.get_idle_size(),
        }


# Convenience function for creating database from settings
def create_database_from_settings() -> Database | None:
    """Create Database instance from application settings.

    Returns:
        Database instance if database_url is configured, None otherwise
    """
    from mcp_memoria.config.settings import get_settings

    settings = get_settings()
    if not settings.database_url:
        return None

    return Database(settings.database_url)
