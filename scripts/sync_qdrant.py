#!/usr/bin/env python3
"""
Incremental bidirectional Qdrant sync between local and remote nodes.

This script synchronizes Qdrant collections by comparing individual points
and merging changes from both sides. It handles:
- New points on either side → copied to the other
- Updated points → newer timestamp wins
- Deleted points → propagated based on last sync timestamp

Usage:
    python scripts/sync_qdrant.py [--dry-run] [--verbose] [--reset-state]
"""

import argparse
import json
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Configuration - customize these for your setup
LOCAL_URL = "http://localhost:6333"
REMOTE_URL = "http://river.local:6333"  # Change to your remote hostname
REMOTE_IP = "192.168.1.51"              # Fallback IP if hostname doesn't resolve

COLLECTIONS = ["procedural", "semantic", "episodic"]
SYNC_STATE_FILE = Path.home() / ".mcp-memoria" / "sync_state.json"
BATCH_SIZE = 100


class Logger:
    """Simple logger with verbosity control."""
    verbose = False

    @staticmethod
    def log(msg: str, level: str = "INFO", verbose_only: bool = False):
        if verbose_only and not Logger.verbose:
            return
        timestamp = datetime.now().strftime("%H:%M:%S")
        symbol = {"INFO": "•", "WARN": "⚠", "ERROR": "✗", "OK": "✓"}.get(level, "•")
        print(f"[{timestamp}] {symbol} {msg}")


log = Logger.log


def http_request(url: str, method: str = "GET", data: dict | None = None, timeout: int = 30) -> dict | None:
    """Make HTTP request and return JSON."""
    try:
        json_data = json.dumps(data).encode('utf-8') if data else None
        headers = {"Content-Type": "application/json"} if data else {}
        req = urllib.request.Request(url, data=json_data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        log(f"HTTP {e.code} for {method} {url}", "ERROR")
        return None
    except Exception as e:
        log(f"Request failed: {e}", "ERROR", verbose_only=True)
        return None


def check_node(url: str, name: str) -> bool:
    """Check if a Qdrant node is reachable."""
    result = http_request(f"{url}/collections")
    if result and result.get("status") == "ok":
        log(f"{name} reachable at {url}", "OK")
        return True
    return False


def get_remote_url() -> str:
    """Get working remote URL (try hostname first, then IP fallback)."""
    if check_node(REMOTE_URL, "Remote"):
        return REMOTE_URL
    remote_ip_url = f"http://{REMOTE_IP}:6333"
    if check_node(remote_ip_url, "Remote (IP)"):
        return remote_ip_url
    return ""


def load_sync_state() -> dict:
    """Load last sync state from file."""
    if SYNC_STATE_FILE.exists():
        try:
            return json.loads(SYNC_STATE_FILE.read_text())
        except Exception:
            pass
    return {"last_sync": None, "collections": {}}


def save_sync_state(state: dict):
    """Save sync state to file."""
    SYNC_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    SYNC_STATE_FILE.write_text(json.dumps(state, indent=2))


def get_all_points(url: str, collection: str) -> dict[str, dict]:
    """Get all points from a collection as {uuid: {payload, vector}}."""
    points = {}
    offset = None

    while True:
        data = {"limit": BATCH_SIZE, "with_payload": True, "with_vector": True}
        if offset:
            data["offset"] = offset

        result = http_request(f"{url}/collections/{collection}/points/scroll", "POST", data)
        if not result or result.get("status") != "ok":
            break

        for point in result["result"].get("points", []):
            point_id = str(point["id"])
            points[point_id] = {
                "payload": point.get("payload", {}),
                "vector": point.get("vector", [])
            }

        offset = result["result"].get("next_page_offset")
        if not offset:
            break

    return points


def parse_timestamp(value: Any) -> datetime | None:
    """Parse timestamp from various formats. Always returns timezone-aware datetime (UTC)."""
    if value is None:
        return None
    if isinstance(value, datetime):
        # Ensure datetime is timezone-aware
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, str):
        try:
            if value.endswith('Z'):
                value = value[:-1] + '+00:00'
            dt = datetime.fromisoformat(value)
            # Ensure parsed datetime is timezone-aware
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            return None
    return None


def get_point_timestamp(point: dict) -> datetime:
    """Get the most recent timestamp from a point."""
    payload = point.get("payload", {})
    updated = parse_timestamp(payload.get("updated_at"))
    created = parse_timestamp(payload.get("created_at"))

    if updated:
        return updated
    if created:
        return created
    return datetime(1970, 1, 1, tzinfo=timezone.utc)


def upsert_points(url: str, collection: str, points: list[dict]) -> bool:
    """Upsert points to a collection."""
    if not points:
        return True

    result = http_request(
        f"{url}/collections/{collection}/points",
        "PUT",
        {"points": points},
        timeout=60
    )
    return result is not None and result.get("status") == "ok"


def delete_points(url: str, collection: str, point_ids: list[str]) -> bool:
    """Delete points from a collection."""
    if not point_ids:
        return True

    result = http_request(
        f"{url}/collections/{collection}/points/delete",
        "POST",
        {"points": point_ids},
        timeout=60
    )
    return result is not None and result.get("status") == "ok"


def sync_collection(
    local_url: str,
    remote_url: str,
    collection: str,
    last_sync: datetime | None,
    dry_run: bool = False
) -> dict:
    """Sync a single collection bidirectionally."""
    stats = {
        "local_to_remote": 0,
        "remote_to_local": 0,
        "conflicts_resolved": 0,
        "deletions_local": 0,
        "deletions_remote": 0,
        "errors": 0
    }

    log(f"Syncing {collection}...")

    # Get all points from both nodes
    log(f"  Fetching points from Local...", verbose_only=True)
    local_points = get_all_points(local_url, collection)
    log(f"  Fetching points from Remote...", verbose_only=True)
    remote_points = get_all_points(remote_url, collection)

    log(f"  Local: {len(local_points)} points, Remote: {len(remote_points)} points")

    all_uuids = set(local_points.keys()) | set(remote_points.keys())

    to_remote = []
    to_local = []
    delete_from_local = []
    delete_from_remote = []

    for uuid in all_uuids:
        local_point = local_points.get(uuid)
        remote_point = remote_points.get(uuid)

        if local_point and remote_point:
            # Point exists on both - compare timestamps
            local_ts = get_point_timestamp(local_point)
            remote_ts = get_point_timestamp(remote_point)

            if local_ts > remote_ts:
                to_remote.append({
                    "id": uuid,
                    "vector": local_point["vector"],
                    "payload": local_point["payload"]
                })
                stats["conflicts_resolved"] += 1
                log(f"  Conflict {uuid[:8]}... Local wins (newer)", verbose_only=True)
            elif remote_ts > local_ts:
                to_local.append({
                    "id": uuid,
                    "vector": remote_point["vector"],
                    "payload": remote_point["payload"]
                })
                stats["conflicts_resolved"] += 1
                log(f"  Conflict {uuid[:8]}... Remote wins (newer)", verbose_only=True)

        elif local_point and not remote_point:
            # Only on Local - new or deleted on Remote?
            local_ts = get_point_timestamp(local_point)

            if last_sync is None or local_ts > last_sync:
                to_remote.append({
                    "id": uuid,
                    "vector": local_point["vector"],
                    "payload": local_point["payload"]
                })
                stats["local_to_remote"] += 1
                log(f"  New on Local: {uuid[:8]}... → Remote", verbose_only=True)
            else:
                delete_from_local.append(uuid)
                stats["deletions_local"] += 1
                log(f"  Deleted on Remote: {uuid[:8]}... remove from Local", verbose_only=True)

        elif remote_point and not local_point:
            # Only on Remote - new or deleted on Local?
            remote_ts = get_point_timestamp(remote_point)

            if last_sync is None or remote_ts > last_sync:
                to_local.append({
                    "id": uuid,
                    "vector": remote_point["vector"],
                    "payload": remote_point["payload"]
                })
                stats["remote_to_local"] += 1
                log(f"  New on Remote: {uuid[:8]}... → Local", verbose_only=True)
            else:
                delete_from_remote.append(uuid)
                stats["deletions_remote"] += 1
                log(f"  Deleted on Local: {uuid[:8]}... remove from Remote", verbose_only=True)

    # Summary
    total_changes = (stats['local_to_remote'] + stats['remote_to_local'] +
                     stats['conflicts_resolved'] + stats['deletions_local'] + stats['deletions_remote'])

    if total_changes == 0:
        log(f"  ✓ Already in sync")
        return stats

    log(f"  Changes: Local→Remote: {stats['local_to_remote']}, Remote→Local: {stats['remote_to_local']}, "
        f"Conflicts: {stats['conflicts_resolved']}, Deletions: {stats['deletions_local']+stats['deletions_remote']}")

    if dry_run:
        log(f"  [DRY RUN] Would apply changes")
        return stats

    # Apply changes
    if to_remote:
        log(f"  Copying {len(to_remote)} points to Remote...")
        if not upsert_points(remote_url, collection, to_remote):
            log(f"  Failed to copy to Remote", "ERROR")
            stats["errors"] += 1

    if to_local:
        log(f"  Copying {len(to_local)} points to Local...")
        if not upsert_points(local_url, collection, to_local):
            log(f"  Failed to copy to Local", "ERROR")
            stats["errors"] += 1

    if delete_from_local:
        log(f"  Deleting {len(delete_from_local)} points from Local...")
        if not delete_points(local_url, collection, delete_from_local):
            log(f"  Failed to delete from Local", "ERROR")
            stats["errors"] += 1

    if delete_from_remote:
        log(f"  Deleting {len(delete_from_remote)} points from Remote...")
        if not delete_points(remote_url, collection, delete_from_remote):
            log(f"  Failed to delete from Remote", "ERROR")
            stats["errors"] += 1

    if stats["errors"] == 0:
        log(f"  {collection} synced", "OK")

    return stats


def main():
    parser = argparse.ArgumentParser(description="Incremental Qdrant sync between local and remote")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--verbose", "-v", action="store_true", help="Detailed output")
    parser.add_argument("--reset-state", action="store_true", help="Reset sync state (first sync mode)")
    args = parser.parse_args()

    Logger.verbose = args.verbose

    print()
    log("═" * 45)
    log("Qdrant Incremental Sync (Local ↔ Remote)")
    log("═" * 45)

    # Check connectivity
    if not check_node(LOCAL_URL, "Local"):
        log("Local Qdrant not reachable", "ERROR")
        sys.exit(1)

    remote_url = get_remote_url()
    if not remote_url:
        log("Remote not reachable", "ERROR")
        sys.exit(1)

    # Load sync state
    if args.reset_state:
        state = {"last_sync": None, "collections": {}}
        log("Sync state reset - treating all points as new", "WARN")
    else:
        state = load_sync_state()

    last_sync_str = state.get("last_sync")
    last_sync = parse_timestamp(last_sync_str) if last_sync_str else None

    if last_sync:
        log(f"Last sync: {last_sync.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    else:
        log("First sync - all points will be merged (no deletions)")

    print()

    # Sync each collection
    total_stats = {
        "local_to_remote": 0,
        "remote_to_local": 0,
        "conflicts_resolved": 0,
        "deletions_local": 0,
        "deletions_remote": 0,
        "errors": 0
    }

    for collection in COLLECTIONS:
        stats = sync_collection(
            local_url=LOCAL_URL,
            remote_url=remote_url,
            collection=collection,
            last_sync=last_sync,
            dry_run=args.dry_run
        )
        for key in total_stats:
            total_stats[key] += stats[key]

    print()

    # Save new sync state
    if not args.dry_run and total_stats["errors"] == 0:
        state["last_sync"] = datetime.now(timezone.utc).isoformat()
        save_sync_state(state)

    # Summary
    log("─" * 45)
    total_ops = (total_stats['local_to_remote'] + total_stats['remote_to_local'] +
                 total_stats['conflicts_resolved'])
    total_del = total_stats['deletions_local'] + total_stats['deletions_remote']

    if total_ops == 0 and total_del == 0:
        log("Everything in sync!", "OK")
    else:
        log(f"Synced: {total_ops} points, Deletions: {total_del}")

    if total_stats["errors"] > 0:
        log(f"Errors: {total_stats['errors']}", "ERROR")
        sys.exit(1)

    log("═" * 45)


if __name__ == "__main__":
    main()
