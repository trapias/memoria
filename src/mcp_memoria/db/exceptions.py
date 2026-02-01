"""Database exception types for MCP Memoria.

Provides a hierarchy of database-specific exceptions for proper
error handling and logging throughout the application.
"""


class DatabaseError(Exception):
    """Base exception for all database-related errors."""

    def __init__(self, message: str, cause: Exception | None = None):
        self.message = message
        self.cause = cause
        super().__init__(message)

    def __str__(self) -> str:
        if self.cause:
            return f"{self.message}: {self.cause}"
        return self.message


class ConnectionError(DatabaseError):
    """Raised when database connection fails or is lost."""

    pass


class MigrationError(DatabaseError):
    """Raised when database migration fails."""

    def __init__(
        self,
        message: str,
        migration_file: str | None = None,
        cause: Exception | None = None,
    ):
        self.migration_file = migration_file
        super().__init__(message, cause)

    def __str__(self) -> str:
        base = super().__str__()
        if self.migration_file:
            return f"{base} (migration: {self.migration_file})"
        return base


class QueryError(DatabaseError):
    """Raised when a database query fails."""

    def __init__(
        self,
        message: str,
        query: str | None = None,
        cause: Exception | None = None,
    ):
        self.query = query
        super().__init__(message, cause)


class TransactionError(DatabaseError):
    """Raised when a transaction operation fails."""

    pass


class PoolExhaustedError(ConnectionError):
    """Raised when connection pool has no available connections."""

    def __init__(self, timeout: float | None = None):
        self.timeout = timeout
        message = "Connection pool exhausted"
        if timeout:
            message = f"{message} after {timeout:.1f}s timeout"
        super().__init__(message)


class RecordNotFoundError(QueryError):
    """Raised when an expected record is not found."""

    def __init__(self, table: str, identifier: str):
        self.table = table
        self.identifier = identifier
        super().__init__(f"Record not found in {table}: {identifier}")
