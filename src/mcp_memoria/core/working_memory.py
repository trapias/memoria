"""Working memory for current session context."""

import logging
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ContextItem(BaseModel):
    """Item in working memory context."""

    key: str
    value: Any
    timestamp: datetime
    access_count: int = 0
    ttl_seconds: int | None = None

    def is_expired(self) -> bool:
        """Check if the item has expired."""
        if self.ttl_seconds is None:
            return False
        return datetime.now() > self.timestamp + timedelta(seconds=self.ttl_seconds)

    def touch(self) -> None:
        """Update access count and timestamp."""
        self.access_count += 1
        self.timestamp = datetime.now()


class LRUCache(OrderedDict):
    """Least Recently Used cache with max size."""

    def __init__(self, max_size: int = 100):
        super().__init__()
        self.max_size = max_size

    def get(self, key: str, default: Any = None) -> Any:
        """Get item and move to end (most recent)."""
        if key in self:
            self.move_to_end(key)
            return self[key]
        return default

    def put(self, key: str, value: Any) -> None:
        """Add item, evicting oldest if at capacity."""
        if key in self:
            self.move_to_end(key)
        self[key] = value
        while len(self) > self.max_size:
            self.popitem(last=False)


class WorkingMemory:
    """Working memory for maintaining current session context.

    This provides fast, in-memory storage for the current session,
    including recently accessed memories and current project context.
    """

    def __init__(
        self,
        max_size: int = 100,
        default_ttl: int = 3600,  # 1 hour
    ):
        """Initialize working memory.

        Args:
            max_size: Maximum number of items to cache
            default_ttl: Default time-to-live in seconds
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache = LRUCache(max_size)
        self._context: dict[str, ContextItem] = {}
        self._session_start = datetime.now()

    @property
    def session_duration(self) -> timedelta:
        """Get current session duration."""
        return datetime.now() - self._session_start

    def set_context(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> None:
        """Set a context value.

        Args:
            key: Context key
            value: Context value
            ttl: Time-to-live in seconds (None for no expiry)
        """
        self._context[key] = ContextItem(
            key=key,
            value=value,
            timestamp=datetime.now(),
            ttl_seconds=ttl,
        )
        logger.debug(f"Set context: {key}")

    def get_context(self, key: str, default: Any = None) -> Any:
        """Get a context value.

        Args:
            key: Context key
            default: Default if not found or expired

        Returns:
            Context value or default
        """
        if key not in self._context:
            return default

        item = self._context[key]
        if item.is_expired():
            del self._context[key]
            return default

        item.touch()
        return item.value

    def get_all_context(self) -> dict[str, Any]:
        """Get all non-expired context values.

        Returns:
            Dict of context key -> value
        """
        self._cleanup_expired()
        return {k: v.value for k, v in self._context.items()}

    def remove_context(self, key: str) -> bool:
        """Remove a context value.

        Args:
            key: Context key

        Returns:
            True if removed
        """
        if key in self._context:
            del self._context[key]
            return True
        return False

    def clear_context(self) -> None:
        """Clear all context values."""
        self._context.clear()

    def cache_memory(self, memory_id: str, data: dict[str, Any]) -> None:
        """Cache a recently accessed memory.

        Args:
            memory_id: Memory ID
            data: Memory data to cache
        """
        self._cache.put(
            memory_id,
            {
                "data": data,
                "cached_at": datetime.now(),
                "access_count": 1,
            },
        )

    def get_cached_memory(self, memory_id: str) -> dict[str, Any] | None:
        """Get a cached memory.

        Args:
            memory_id: Memory ID

        Returns:
            Cached memory data or None
        """
        cached = self._cache.get(memory_id)
        if cached:
            cached["access_count"] += 1
            return cached["data"]
        return None

    def invalidate_cache(self, memory_id: str) -> bool:
        """Invalidate a cached memory.

        Args:
            memory_id: Memory ID

        Returns:
            True if invalidated
        """
        if memory_id in self._cache:
            del self._cache[memory_id]
            return True
        return False

    def clear_cache(self) -> None:
        """Clear all cached memories."""
        self._cache.clear()

    def get_recent_memories(self, limit: int = 10) -> list[str]:
        """Get IDs of recently accessed memories.

        Args:
            limit: Maximum number to return

        Returns:
            List of memory IDs (most recent first)
        """
        # Items are ordered, most recent at end
        items = list(self._cache.keys())
        return items[-limit:][::-1]

    def _cleanup_expired(self) -> int:
        """Remove expired context items.

        Returns:
            Number of items removed
        """
        expired = [k for k, v in self._context.items() if v.is_expired()]
        for key in expired:
            del self._context[key]
        return len(expired)

    def get_stats(self) -> dict[str, Any]:
        """Get working memory statistics.

        Returns:
            Statistics dict
        """
        self._cleanup_expired()
        return {
            "session_duration_seconds": self.session_duration.total_seconds(),
            "context_items": len(self._context),
            "cached_memories": len(self._cache),
            "cache_max_size": self.max_size,
            "context_keys": list(self._context.keys()),
        }

    def set_current_project(self, project: str) -> None:
        """Convenience method to set current project context.

        Args:
            project: Project name or path
        """
        self.set_context("current_project", project)

    def get_current_project(self) -> str | None:
        """Get current project context.

        Returns:
            Current project or None
        """
        return self.get_context("current_project")

    def set_current_file(self, file_path: str) -> None:
        """Convenience method to set current file context.

        Args:
            file_path: File path
        """
        self.set_context("current_file", file_path)

    def get_current_file(self) -> str | None:
        """Get current file context.

        Returns:
            Current file path or None
        """
        return self.get_context("current_file")

    def add_to_history(self, action: str, details: dict[str, Any] | None = None) -> None:
        """Add an action to session history.

        Args:
            action: Action description
            details: Optional action details
        """
        history = self.get_context("session_history", [])
        history.append(
            {
                "action": action,
                "timestamp": datetime.now().isoformat(),
                "details": details or {},
            }
        )
        # Keep last 100 history items
        self.set_context("session_history", history[-100:])

    def get_history(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get session history.

        Args:
            limit: Maximum items to return

        Returns:
            List of history items (most recent first)
        """
        history = self.get_context("session_history", [])
        return history[-limit:][::-1]
