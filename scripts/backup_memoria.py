#!/usr/bin/env python3
"""
Backup script for MCP Memoria.

Exports all memories from Qdrant to a JSON file with vectors included,
enabling full restore capability.

Usage:
    uv run scripts/backup_memoria.py [--output-dir /path/to/backups] [--keep 5]

Options:
    --output-dir    Directory for backup files (default: ~/.mcp-memoria/backups)
    --keep N        Keep only the N most recent backups (default: 10, 0 = keep all)
    --host          Qdrant host (default: localhost)
    --port          Qdrant port (default: 6333)
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from qdrant_client import QdrantClient


def export_memories(client: QdrantClient, output_path: Path) -> dict:
    """Export all memories from Qdrant to JSON file."""
    collections = ["episodic", "semantic", "procedural"]
    export_data = {
        "version": "1.0",
        "exported_at": datetime.now().isoformat(),
        "include_vectors": True,
        "collections": {},
    }

    total = 0
    for coll in collections:
        try:
            if not client.collection_exists(coll):
                print(f"  {coll}: (not found)")
                continue

            records = []
            offset = None
            while True:
                result = client.scroll(
                    collection_name=coll,
                    limit=100,
                    offset=offset,
                    with_vectors=True,
                )
                points, next_offset = result
                for p in points:
                    records.append({
                        "id": str(p.id),
                        "payload": p.payload,
                        "vector": p.vector if p.vector else None,
                    })
                if not next_offset:
                    break
                offset = next_offset

            export_data["collections"][coll] = records
            total += len(records)
            print(f"  {coll}: {len(records)} memories")
        except Exception as e:
            print(f"  {coll}: error - {e}", file=sys.stderr)

    # Write to file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)

    return {"total": total, "collections": export_data["collections"]}


def cleanup_old_backups(backup_dir: Path, keep: int) -> int:
    """Remove old backups, keeping only the most recent N files."""
    if keep <= 0:
        return 0

    backups = sorted(backup_dir.glob("memoria-backup-*.json"), reverse=True)
    removed = 0

    for old_backup in backups[keep:]:
        old_backup.unlink()
        removed += 1
        print(f"  Removed old backup: {old_backup.name}")

    return removed


def main():
    parser = argparse.ArgumentParser(
        description="Backup MCP Memoria memories from Qdrant"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.home() / ".mcp-memoria" / "backups",
        help="Directory for backup files",
    )
    parser.add_argument(
        "--keep",
        type=int,
        default=10,
        help="Keep only N most recent backups (0 = keep all)",
    )
    parser.add_argument(
        "--host",
        default="localhost",
        help="Qdrant host",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=6333,
        help="Qdrant port",
    )
    args = parser.parse_args()

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_path = args.output_dir / f"memoria-backup-{timestamp}.json"

    print(f"Connecting to Qdrant at {args.host}:{args.port}...")
    try:
        client = QdrantClient(host=args.host, port=args.port)
        # Test connection
        client.get_collections()
    except Exception as e:
        print(f"Error: Cannot connect to Qdrant - {e}", file=sys.stderr)
        sys.exit(1)

    print("Exporting memories...")
    result = export_memories(client, output_path)

    print(f"\nBackup complete: {result['total']} memories")
    print(f"Saved to: {output_path}")

    if args.keep > 0:
        print(f"\nCleaning up (keeping {args.keep} most recent)...")
        removed = cleanup_old_backups(args.output_dir, args.keep)
        if removed:
            print(f"  Removed {removed} old backup(s)")

    # Print file size
    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"\nBackup size: {size_mb:.2f} MB")


if __name__ == "__main__":
    main()
