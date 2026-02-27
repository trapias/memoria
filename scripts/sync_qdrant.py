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
PRE_SYNC_BACKUP_DIR = Path.home() / ".mcp-memoria" / "backups" / "pre-sync"
PRE_SYNC_KEEP = 5  # keep last N pre-sync snapshots
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


def get_collection_config(url: str, collection: str) -> dict | None:
    """Get collection configuration (vector size, distance, payload indexes)."""
    result = http_request(f"{url}/collections/{collection}")
    if result and result.get("status") == "ok":
        return result["result"]
    return None


def ensure_collection_exists(url: str, collection: str, source_url: str) -> tuple[bool, bool]:
    """Ensure a collection exists on the target, creating it from source config if needed.

    Returns (success, was_created) tuple.
    """
    # Check if collection already exists
    result = http_request(f"{url}/collections/{collection}")
    if result and result.get("status") == "ok":
        return True, False

    # Get config from source
    source_config = get_collection_config(source_url, collection)
    if not source_config:
        log(f"  Cannot read config for {collection} from source", "ERROR")
        return False, False

    vectors_config = source_config["config"]["params"]["vectors"]
    log(f"  Creating collection {collection} (size={vectors_config['size']}, "
        f"distance={vectors_config['distance']})...")

    create_data = {
        "vectors": {
            "size": vectors_config["size"],
            "distance": vectors_config["distance"],
        }
    }

    create_result = http_request(
        f"{url}/collections/{collection}", "PUT", create_data, timeout=30
    )
    if not create_result or create_result.get("status") != "ok":
        log(f"  Failed to create collection {collection}", "ERROR")
        return False, False

    # Recreate payload indexes from source
    payload_schema = source_config.get("payload_schema", {})
    for field_name, field_info in payload_schema.items():
        index_data: dict[str, Any] = {"field_name": field_name}
        if "params" in field_info:
            # Text index with params
            index_data["field_schema"] = field_info["params"]
        else:
            # Simple type index
            type_map = {"keyword": "keyword", "integer": "integer", "bool": "bool", "text": "text"}
            data_type = field_info.get("data_type", "keyword")
            index_data["field_schema"] = type_map.get(data_type, "keyword")

        http_request(f"{url}/collections/{collection}/index", "PUT", index_data)

    log(f"  Collection {collection} created", "OK")
    return True, True


def get_all_points(url: str, collection: str) -> dict[str, dict] | None:
    """Get all points from a collection as {uuid: {payload, vector}}.

    Returns None on error (failed to fetch), empty dict if collection is truly empty.
    """
    points = {}
    offset = None
    first_request = True

    while True:
        data = {"limit": BATCH_SIZE, "with_payload": True, "with_vector": True}
        if offset:
            data["offset"] = offset

        result = http_request(f"{url}/collections/{collection}/points/scroll", "POST", data)
        if not result or result.get("status") != "ok":
            if first_request:
                # First request failed - cannot distinguish empty from error
                log(f"  Failed to fetch points from {url}/{collection}", "ERROR")
                return None
            break

        first_request = False

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


def pre_sync_backup(local_url: str) -> bool:
    """Take a lightweight JSON snapshot of local collections before syncing.

    Saves to PRE_SYNC_BACKUP_DIR with rotation. Returns True on success.
    """
    PRE_SYNC_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = PRE_SYNC_BACKUP_DIR / f"pre-sync-{timestamp}.json"

    backup_data: dict[str, Any] = {
        "version": "1.0",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "include_vectors": True,
        "collections": {},
    }

    total = 0
    for collection in COLLECTIONS:
        points = get_all_points(local_url, collection)
        if points is None:
            log(f"Pre-sync backup: failed to read {collection}, aborting backup", "ERROR")
            return False

        records = []
        for point_id, data in points.items():
            records.append({
                "id": point_id,
                "payload": data["payload"],
                "vector": data["vector"],
            })
        backup_data["collections"][collection] = records
        total += len(records)

    backup_path.write_text(json.dumps(backup_data, default=str))
    log(f"Pre-sync backup: {total} points saved to {backup_path.name}", "OK")

    # Rotate old pre-sync backups
    old_backups = sorted(PRE_SYNC_BACKUP_DIR.glob("pre-sync-*.json"), reverse=True)
    for old in old_backups[PRE_SYNC_KEEP:]:
        old.unlink()

    return True


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
    state: dict,
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

    # Ensure collection exists on both sides (create from the other if missing)
    remote_ok, remote_created = ensure_collection_exists(remote_url, collection, local_url)
    local_ok, local_created = ensure_collection_exists(local_url, collection, remote_url)
    if not remote_ok or not local_ok:
        log(f"  SKIPPING {collection}: failed to ensure collection on both sides", "ERROR")
        stats["errors"] += 1
        return stats
    freshly_created = remote_created or local_created

    # Get all points from both nodes
    log(f"  Fetching points from Local...", verbose_only=True)
    local_points = get_all_points(local_url, collection)
    log(f"  Fetching points from Remote...", verbose_only=True)
    remote_points = get_all_points(remote_url, collection)

    # Safety: abort if either side failed to fetch (None = error, {} = truly empty)
    if local_points is None or remote_points is None:
        failed = "Local" if local_points is None else "Remote"
        log(f"  SKIPPING {collection}: failed to fetch from {failed}", "ERROR")
        stats["errors"] += 1
        return stats

    log(f"  Local: {len(local_points)} points, Remote: {len(remote_points)} points")

    # Safety: block if one side is empty but the other has many points
    # This almost certainly means a fetch error, not a legitimate mass deletion
    # Skip this check if:
    #   - we just created the collection (empty is expected)
    #   - the empty side's collection is genuinely new (fresh install / no prior sync data)
    MIN_POINTS_FOR_SAFETY = 10  # only apply safety check above this threshold

    # Detect fresh target: collection was just created, or is empty with no prior sync record
    empty_side_is_fresh = freshly_created
    if not empty_side_is_fresh and last_sync is not None:
        # If one side is empty and we have a last_sync, check if this collection was
        # tracked in previous syncs. If not, it's likely a fresh/reinstalled target.
        col_state = state.get("collections", {}).get(collection, {})
        if not col_state:
            empty_side_is_fresh = True
            log(f"  No prior sync record for {collection}, treating empty side as fresh", verbose_only=True)

    if not empty_side_is_fresh and max(len(local_points), len(remote_points)) >= MIN_POINTS_FOR_SAFETY:
        if len(local_points) == 0 and len(remote_points) > 0:
            log(f"  SKIPPING {collection}: Local returned 0 points but Remote has {len(remote_points)} "
                f"- likely a fetch error, not a deletion. Use --reset-state for a fresh sync.", "WARN")
            stats["errors"] += 1
            return stats
        if len(remote_points) == 0 and len(local_points) > 0:
            log(f"  SKIPPING {collection}: Remote returned 0 points but Local has {len(local_points)} "
                f"- likely a fetch error, not a deletion. Use --reset-state for a fresh sync.", "WARN")
            stats["errors"] += 1
            return stats

    # CRITICAL SAFETY: if one side is empty (fresh install/reinstall),
    # force first-sync mode (last_sync=None) so we only COPY, never DELETE.
    # Without this, all points on the populated side older than last_sync
    # would be incorrectly deleted (interpreted as "deleted on the empty side").
    effective_last_sync = last_sync
    if empty_side_is_fresh and (len(local_points) == 0 or len(remote_points) == 0):
        effective_last_sync = None
        log(f"  Fresh target detected, using first-sync mode (copy only, no deletions)")

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

            if effective_last_sync is None or local_ts > effective_last_sync:
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

            if effective_last_sync is None or remote_ts > effective_last_sync:
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

    # Safety: cap maximum deletions per sync run
    MAX_DELETIONS_PER_SYNC = 20
    total_deletions = len(delete_from_local) + len(delete_from_remote)
    if total_deletions > MAX_DELETIONS_PER_SYNC:
        log(f"  ABORTING {collection}: {total_deletions} deletions exceed safety limit of {MAX_DELETIONS_PER_SYNC}. "
            f"Review manually or use --reset-state.", "WARN")
        stats["errors"] += 1
        return stats

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

    # Pre-sync backup of local data
    if not args.dry_run:
        if not pre_sync_backup(LOCAL_URL):
            log("Pre-sync backup failed, aborting sync", "ERROR")
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
            state=state,
            dry_run=args.dry_run
        )
        for key in total_stats:
            total_stats[key] += stats[key]

    print()

    # Save new sync state (including per-collection records for fresh-target detection)
    if not args.dry_run and total_stats["errors"] == 0:
        now = datetime.now(timezone.utc).isoformat()
        state["last_sync"] = now
        if "collections" not in state:
            state["collections"] = {}
        for collection in COLLECTIONS:
            state["collections"][collection] = {"last_sync": now}
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
