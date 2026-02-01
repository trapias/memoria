"""Simple SQL migration runner for PostgreSQL.

Provides ordered migration execution with version tracking.
Migrations are SQL files in the migrations/ directory, named
with a numeric prefix (e.g., 001_initial.sql, 002_add_relations.sql).
"""

import logging
import re
from pathlib import Path
from typing import Any

from asyncpg import Pool

from mcp_memoria.db.exceptions import MigrationError

logger = logging.getLogger(__name__)


class MigrationRunner:
    """Run SQL migrations in order, tracking applied versions.

    Migrations are stored in the migrations/ directory as .sql files.
    Each file should be named with a numeric prefix for ordering:
        001_initial.sql
        002_add_relations.sql
        003_add_views.sql

    The runner creates a _migrations table to track applied migrations.
    Already-applied migrations are skipped.

    Example:
        runner = MigrationRunner(pool, Path("./migrations"))
        applied = await runner.run()
        print(f"Applied {applied} migrations")
    """

    MIGRATION_TABLE = "_migrations"
    MIGRATION_PATTERN = re.compile(r"^(\d+)_.+\.sql$")

    def __init__(self, pool: Pool, migrations_dir: Path):
        """Initialize migration runner.

        Args:
            pool: Database connection pool
            migrations_dir: Directory containing migration .sql files
        """
        self._pool = pool
        self._migrations_dir = migrations_dir

    async def run(self) -> int:
        """Run all pending migrations.

        Returns:
            Number of migrations applied

        Raises:
            MigrationError: If any migration fails
        """
        async with self._pool.acquire() as conn:
            # Ensure migration tracking table exists
            await self._ensure_migration_table(conn)

            # Get applied migrations
            applied = await self._get_applied_migrations(conn)

            # Find and sort pending migrations
            pending = self._find_pending_migrations(applied)

            if not pending:
                logger.info("No pending migrations")
                return 0

            logger.info(f"Found {len(pending)} pending migration(s)")

            # Apply each migration in a transaction
            applied_count = 0
            for migration_file in pending:
                try:
                    await self._apply_migration(conn, migration_file)
                    applied_count += 1
                except Exception as e:
                    raise MigrationError(
                        f"Migration failed: {e}",
                        migration_file=migration_file.name,
                        cause=e,
                    ) from e

            logger.info(f"Applied {applied_count} migration(s)")
            return applied_count

    async def _ensure_migration_table(self, conn: Any) -> None:
        """Create migration tracking table if it doesn't exist."""
        await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.MIGRATION_TABLE} (
                version INT PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

    async def _get_applied_migrations(self, conn: Any) -> set[int]:
        """Get set of already-applied migration versions."""
        rows = await conn.fetch(
            f"SELECT version FROM {self.MIGRATION_TABLE}"
        )
        return {row["version"] for row in rows}

    def _find_pending_migrations(self, applied: set[int]) -> list[Path]:
        """Find migration files that haven't been applied yet.

        Returns:
            List of migration file paths, sorted by version
        """
        if not self._migrations_dir.exists():
            logger.warning(f"Migrations directory not found: {self._migrations_dir}")
            return []

        pending = []
        for file in self._migrations_dir.glob("*.sql"):
            match = self.MIGRATION_PATTERN.match(file.name)
            if match:
                version = int(match.group(1))
                if version not in applied:
                    pending.append((version, file))

        # Sort by version number
        pending.sort(key=lambda x: x[0])
        return [file for _, file in pending]

    async def _apply_migration(self, conn: Any, migration_file: Path) -> None:
        """Apply a single migration file.

        The entire migration runs in a transaction. If any statement
        fails, the entire migration is rolled back.
        """
        match = self.MIGRATION_PATTERN.match(migration_file.name)
        if not match:
            raise MigrationError(
                f"Invalid migration filename: {migration_file.name}",
                migration_file=migration_file.name,
            )

        version = int(match.group(1))
        name = migration_file.stem

        logger.info(f"Applying migration {version}: {name}")

        # Read migration SQL
        sql = migration_file.read_text(encoding="utf-8")

        # Execute in transaction
        async with conn.transaction():
            # Execute migration statements
            # Split on semicolons but be careful with PL/pgSQL blocks
            await self._execute_migration_sql(conn, sql)

            # Record migration as applied
            await conn.execute(
                f"INSERT INTO {self.MIGRATION_TABLE} (version, name) VALUES ($1, $2)",
                version,
                name,
            )

        logger.info(f"Migration {version} applied successfully")

    async def _execute_migration_sql(self, conn: Any, sql: str) -> None:
        """Execute migration SQL, handling multi-statement scripts.

        Handles:
        - Multiple statements separated by semicolons
        - PL/pgSQL function definitions (CREATE FUNCTION ... $$ ... $$)
        - Comments (-- and /* ... */)
        """
        # For simplicity, execute the entire script at once
        # PostgreSQL handles multi-statement execution
        await conn.execute(sql)

    async def get_status(self) -> dict[str, Any]:
        """Get migration status.

        Returns:
            Dictionary with applied and pending migration info
        """
        async with self._pool.acquire() as conn:
            await self._ensure_migration_table(conn)

            # Get applied migrations with timestamps
            applied_rows = await conn.fetch(f"""
                SELECT version, name, applied_at
                FROM {self.MIGRATION_TABLE}
                ORDER BY version
            """)

            applied = await self._get_applied_migrations(conn)
            pending = self._find_pending_migrations(applied)

            return {
                "applied": [
                    {
                        "version": row["version"],
                        "name": row["name"],
                        "applied_at": row["applied_at"].isoformat(),
                    }
                    for row in applied_rows
                ],
                "pending": [
                    {
                        "version": int(self.MIGRATION_PATTERN.match(f.name).group(1)),
                        "name": f.stem,
                        "file": f.name,
                    }
                    for f in pending
                ],
                "is_current": len(pending) == 0,
            }
