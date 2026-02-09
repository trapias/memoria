"""Async update checker for MCP Memoria.

Checks GitHub tags for newer versions, with daily caching and Docker awareness.
"""

import json
import logging
import os
import time
from pathlib import Path

import httpx

from mcp_memoria import __version__

logger = logging.getLogger("mcp_memoria.update_checker")

GITHUB_TAGS_URL = "https://api.github.com/repos/trapias/memoria/tags"
CHECK_INTERVAL_SECONDS = 86400  # 24 hours
CHECK_TIMEOUT_SECONDS = 2.0
CACHE_FILE = Path.home() / ".mcp-memoria" / ".last_update_check"


def is_running_in_docker() -> bool:
    """Detect if running inside a Docker container."""
    if os.environ.get("MEMORIA_RUNNING_IN_DOCKER", "").lower() == "true":
        return True
    return Path("/.dockerenv").exists()


def _parse_version(tag: str) -> tuple[int, ...]:
    """Parse a version tag like 'v1.3.0' or '1.3.0' into a tuple of ints."""
    tag = tag.lstrip("v")
    try:
        return tuple(int(x) for x in tag.split("."))
    except (ValueError, AttributeError):
        return (0,)


def _should_check(cache_file: Path) -> bool:
    """Return True if enough time has passed since the last check."""
    if not cache_file.exists():
        return True
    try:
        data = json.loads(cache_file.read_text())
        last_check = data.get("timestamp", 0)
        return (time.time() - last_check) > CHECK_INTERVAL_SECONDS
    except (json.JSONDecodeError, OSError):
        return True


def _save_cache(cache_file: Path, latest_version: str | None) -> None:
    """Save check timestamp and result to cache."""
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    data = {"timestamp": time.time(), "latest_version": latest_version}
    try:
        cache_file.write_text(json.dumps(data))
    except OSError:
        pass


def _get_cached_result(cache_file: Path) -> str | None:
    """Return cached latest version if cache is still fresh."""
    try:
        data = json.loads(cache_file.read_text())
        last_check = data.get("timestamp", 0)
        if (time.time() - last_check) <= CHECK_INTERVAL_SECONDS:
            return data.get("latest_version")
    except (json.JSONDecodeError, OSError):
        pass
    return None


async def check_for_updates() -> str | None:
    """Check GitHub for a newer version. Returns a user-facing message or None.

    - Non-blocking, with a 2s timeout
    - Checks at most once per day (cached)
    - Returns different messages for Docker vs native installs
    """
    # Check cache first
    cached = _get_cached_result(CACHE_FILE)
    if cached is not None:
        if _parse_version(cached) > _parse_version(__version__):
            return _format_update_message(cached)
        return None

    if not _should_check(CACHE_FILE):
        return None

    try:
        async with httpx.AsyncClient(timeout=CHECK_TIMEOUT_SECONDS) as client:
            resp = await client.get(
                GITHUB_TAGS_URL,
                headers={"Accept": "application/vnd.github.v3+json"},
            )
            resp.raise_for_status()
            tags = resp.json()

        if not tags:
            _save_cache(CACHE_FILE, None)
            return None

        # Tags are returned newest-first by GitHub
        latest_tag = tags[0].get("name", "")
        latest_version = latest_tag.lstrip("v")
        _save_cache(CACHE_FILE, latest_version)

        if _parse_version(latest_version) > _parse_version(__version__):
            return _format_update_message(latest_version)

    except (httpx.HTTPError, OSError, KeyError, IndexError) as e:
        logger.debug(f"Update check failed: {e}")
        # Save cache to avoid retrying immediately
        _save_cache(CACHE_FILE, None)

    return None


def _format_update_message(latest_version: str) -> str:
    """Format the update message based on the runtime environment."""
    header = (
        f"Memoria v{latest_version} disponibile (attuale: v{__version__})"
    )

    if is_running_in_docker():
        return (
            f"{header}\n"
            f"  Aggiorna con: docker compose pull && docker compose up -d"
        )
    else:
        return (
            f"{header}\n"
            f"  Aggiorna con: pip install --upgrade "
            f"git+https://github.com/trapias/memoria.git"
        )
