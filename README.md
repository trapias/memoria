# MCP Memoria

**Unlimited local AI memory for any MCP-compatible client**

MCP Memoria is a Model Context Protocol (MCP) server that provides persistent, unlimited memory capabilities using **Qdrant** for vector storage and **Ollama** for local embeddings. Works with Claude Code, Claude Desktop, OpenCode, Cursor, Windsurf, and any other client that supports the [Model Context Protocol](https://modelcontextprotocol.io). Zero cloud dependencies, zero storage limits, 100% privacy.

## Features

- **Unlimited Storage**: No 50MB limits like cloud services
- **100% Local**: All data stays on your machine
- **Three Memory Types**:
  - **Episodic**: Events, conversations, time-bound memories
  - **Semantic**: Facts, knowledge, concepts
  - **Procedural**: Procedures, workflows, learned skills
- **Semantic Search**: Find relevant memories by meaning, not just keywords
- **Full-Text Match**: Filter results by exact keyword presence in content
- **Content Chunking**: Long memories are automatically split into chunks for higher-quality embeddings; results are transparently deduplicated
- **Knowledge Graph**: Create typed relationships between memories
  - 9 relation types: causes, fixes, supports, opposes, follows, supersedes, derives, part_of, related
  - Graph traversal with BFS/DFS
  - AI-powered relation suggestions
  - Path finding between memories
- **Web UI**: Browser-based Knowledge Graph explorer and memory browser
- **Time Tracking**: Track work sessions with clients, projects, and categories
- **Memory Consolidation**: Automatic merging of similar memories
- **Forgetting Curve**: Natural decay of unused, low-importance memories
- **Export/Import**: Backup and share your memories

---

## Quick Start (Docker)

The fastest way to get started. **No git clone, no Python install** — download one file, configure your client, done.

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- [Ollama](https://ollama.com/download) running with the `nomic-embed-text` model

```bash
# Install and start Ollama (if not already running)
# macOS: brew install ollama
# Linux: curl -fsSL https://ollama.com/install.sh | sh
ollama serve &
ollama pull nomic-embed-text
```

### Step 1: Download and start backend services

```bash
mkdir -p memoria && cd memoria

# Download the server compose file
curl -O https://raw.githubusercontent.com/trapias/memoria/main/docker/docker-compose.server.yml

# Start Qdrant + PostgreSQL + Web UI
docker compose -f docker-compose.server.yml up -d
```

This starts:

| Service | Port | Description |
|---------|------|-------------|
| Qdrant | 6333 | Vector database for semantic search |
| PostgreSQL | 5433 | Knowledge Graph + Time Tracking data |
| Web UI | 3000 | Browser-based memory explorer |
| REST API | 8765 | API for custom integrations |

### Step 2: Configure your MCP client

Each MCP session spawns its own Memoria container via `docker run`. This ensures **isolated WorkingMemory per session** — no risk of context confusion between concurrent sessions.

**Claude Code** (CLI):

```bash
claude mcp add --scope user memoria -- \
  docker run --rm -i \
  --network memoria-network \
  -e MEMORIA_QDRANT_HOST=qdrant \
  -e MEMORIA_QDRANT_PORT=6333 \
  -e MEMORIA_DATABASE_URL=postgresql://memoria:memoria_dev@postgres:5432/memoria \
  -e MEMORIA_OLLAMA_HOST=http://host.docker.internal:11434 \
  -e MEMORIA_LOG_LEVEL=WARNING \
  ghcr.io/trapias/memoria:latest
```

**Claude Code / Claude Desktop** (JSON config):

```json
{
  "mcpServers": {
    "memoria": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "--network", "memoria-network",
        "-e", "MEMORIA_QDRANT_HOST=qdrant",
        "-e", "MEMORIA_QDRANT_PORT=6333",
        "-e", "MEMORIA_DATABASE_URL=postgresql://memoria:memoria_dev@postgres:5432/memoria",
        "-e", "MEMORIA_OLLAMA_HOST=http://host.docker.internal:11434",
        "-e", "MEMORIA_LOG_LEVEL=WARNING",
        "ghcr.io/trapias/memoria:latest"
      ]
    }
  }
}
```

Config file locations:
- Claude Code: `~/.claude.json`
- Claude Desktop macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Claude Desktop Windows: `%APPDATA%\Claude\claude_desktop_config.json`

**OpenCode** (`opencode.json`):

```json
{
  "mcp": {
    "memoria": {
      "type": "local",
      "command": [
        "docker", "run", "--rm", "-i",
        "--network", "memoria-network",
        "-e", "MEMORIA_QDRANT_HOST=qdrant",
        "-e", "MEMORIA_QDRANT_PORT=6333",
        "-e", "MEMORIA_DATABASE_URL=postgresql://memoria:memoria_dev@postgres:5432/memoria",
        "-e", "MEMORIA_OLLAMA_HOST=http://host.docker.internal:11434",
        "-e", "MEMORIA_LOG_LEVEL=WARNING",
        "ghcr.io/trapias/memoria:latest"
      ],
      "enabled": true
    }
  }
}
```

**Codex** (CLI):

```bash
codex mcp add memoria --env MEMORIA_QDRANT_HOST=qdrant --env MEMORIA_QDRANT_PORT=6333 --env "MEMORIA_DATABASE_URL=postgresql://memoria:memoria_dev@postgres:5432/memoria" --env "MEMORIA_OLLAMA_HOST=http://host.docker.internal:11434" --env MEMORIA_LOG_LEVEL=WARNING -- docker run --rm -i --network memoria-network -e MEMORIA_DATABASE_URL -e MEMORIA_QDRANT_HOST -e MEMORIA_QDRANT_PORT -e MEMORIA_OLLAMA_HOST -e MEMORIA_LOG_LEVEL ghcr.io/trapias/memoria:latest
```

**Codex** (desktop app for macOS — `~/.codex/config.toml`):

```toml
[mcp_servers.memoria]
command = "docker"
args = [
  "run",
  "--rm",
  "-i",
  "--network",
  "memoria-network",
  "-e",
  "MEMORIA_DATABASE_URL",
  "-e",
  "MEMORIA_QDRANT_HOST",
  "-e",
  "MEMORIA_QDRANT_PORT",
  "-e",
  "MEMORIA_OLLAMA_HOST",
  "-e",
  "MEMORIA_LOG_LEVEL",
  "ghcr.io/trapias/memoria:latest",
]
enabled = true

[mcp_servers.memoria.env]
MEMORIA_DATABASE_URL = "postgresql://memoria:memoria_dev@postgres:5432/memoria"
MEMORIA_LOG_LEVEL = "WARNING"
MEMORIA_OLLAMA_HOST = "http://host.docker.internal:11434"
MEMORIA_QDRANT_HOST = "qdrant"
MEMORIA_QDRANT_PORT = "6333"
```

**Other MCP clients** — Use the Docker command above, adapting it to your client's configuration format. The key parameters:
- **Command**: `docker run --rm -i --network memoria-network ... ghcr.io/trapias/memoria:latest`
- **Transport**: stdio (each session gets its own container)
- **Network**: `memoria-network` (to reach Qdrant and PostgreSQL)

> **Why `docker run` per session?** Memoria maintains in-memory WorkingMemory (current project context, session history, memory cache) that is **per-process**. A shared persistent MCP container would mix context between concurrent Claude sessions. The per-session approach ensures complete isolation.

### Step 3: Verify

Start your client and try:

```
Show me the memoria stats
```

If you see statistics, Memoria is working. Open http://localhost:3000 for the Web UI.

### Update

```bash
# Update backend services
docker compose -f docker-compose.server.yml pull
docker compose -f docker-compose.server.yml up -d

# The MCP client image updates automatically — docker run pulls :latest on next session
docker pull ghcr.io/trapias/memoria:latest
```

To pin a specific version, replace `:latest` with a version tag (e.g., `:1.3.0`) in your MCP client config.

---

## Alternative Setups

### Option A: Local Python + Docker backends

**Best for**: Developers who want to modify Memoria or avoid Docker for the MCP process.

Backend services (Qdrant + PostgreSQL + Web UI) run in Docker, the MCP server runs as a local Python process.

```bash
git clone https://github.com/trapias/memoria.git
cd memoria

# Start backend services
cd docker
docker network create memoria-network 2>/dev/null || true
docker compose -f docker-compose.central.yml up -d

# Install Memoria
cd ..
pip install -e .
```

Configure your MCP client with the local Python command:

**Claude Code** (CLI):

```bash
claude mcp add --scope user memoria \
  -e MEMORIA_QDRANT_HOST=localhost \
  -e MEMORIA_QDRANT_PORT=6333 \
  -e MEMORIA_DATABASE_URL=postgresql://memoria:memoria_dev@localhost:5433/memoria \
  -e MEMORIA_OLLAMA_HOST=http://localhost:11434 \
  -- python -m mcp_memoria
```

**Claude Code / Claude Desktop** (JSON):

```json
{
  "mcpServers": {
    "memoria": {
      "command": "python",
      "args": ["-m", "mcp_memoria"],
      "env": {
        "MEMORIA_QDRANT_HOST": "localhost",
        "MEMORIA_QDRANT_PORT": "6333",
        "MEMORIA_DATABASE_URL": "postgresql://memoria:memoria_dev@localhost:5433/memoria",
        "MEMORIA_OLLAMA_HOST": "http://localhost:11434"
      }
    }
  }
}
```

**OpenCode** (`opencode.json`):

```json
{
  "mcp": {
    "memoria": {
      "type": "local",
      "command": ["python", "-m", "mcp_memoria"],
      "enabled": true,
      "environment": {
        "MEMORIA_QDRANT_HOST": "localhost",
        "MEMORIA_QDRANT_PORT": "6333",
        "MEMORIA_DATABASE_URL": "postgresql://memoria:memoria_dev@localhost:5433/memoria",
        "MEMORIA_OLLAMA_HOST": "http://localhost:11434"
      }
    }
  }
}
```

**Codex** (CLI):

```bash
codex mcp add memoria --env MEMORIA_QDRANT_HOST=localhost --env MEMORIA_QDRANT_PORT=6333 --env "MEMORIA_DATABASE_URL=postgresql://memoria:memoria_dev@localhost:5433/memoria" --env "MEMORIA_OLLAMA_HOST=http://localhost:11434" -- python -m mcp_memoria
```

**Codex** (desktop app for macOS — `~/.codex/config.toml`):

```toml
[mcp_servers.memoria]
command = "python"
args = ["-m", "mcp_memoria"]
enabled = true

[mcp_servers.memoria.env]
MEMORIA_QDRANT_HOST = "localhost"
MEMORIA_QDRANT_PORT = "6333"
MEMORIA_DATABASE_URL = "postgresql://memoria:memoria_dev@localhost:5433/memoria"
MEMORIA_OLLAMA_HOST = "http://localhost:11434"
```

Update: `git pull && pip install -e .` or `mcp-memoria --update`

### Option B: Minimal (Qdrant only)

**Best for**: Quick testing. No Knowledge Graph, Time Tracking, or Web UI.

```bash
# Download just the Qdrant compose file
mkdir -p memoria && cd memoria
curl -O https://raw.githubusercontent.com/trapias/memoria/main/docker/docker-compose.qdrant-only.yml

# Start Qdrant
docker compose -f docker-compose.qdrant-only.yml up -d
```

Configure your MCP client (Docker or Python, without `MEMORIA_DATABASE_URL`):

```json
{
  "mcpServers": {
    "memoria": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "--network", "memoria-network",
        "-e", "MEMORIA_QDRANT_HOST=qdrant",
        "-e", "MEMORIA_QDRANT_PORT=6333",
        "-e", "MEMORIA_OLLAMA_HOST=http://host.docker.internal:11434",
        "-e", "MEMORIA_LOG_LEVEL=WARNING",
        "ghcr.io/trapias/memoria:latest"
      ]
    }
  }
}
```

---

### Managing Services

```bash
# Check status
docker compose -f docker-compose.server.yml ps

# View logs
docker compose -f docker-compose.server.yml logs -f

# Stop services (data is preserved)
docker compose -f docker-compose.server.yml down

# Stop and DELETE all data (irreversible!)
docker compose -f docker-compose.server.yml down -v
```

---

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      Your Machine                            │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Ollama (native)                                      │   │
│  │  http://localhost:11434                               │   │
│  │  Provides: nomic-embed-text embeddings                │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Docker Services (docker-compose.server.yml)             │   │
│  │                                                        │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌────────────────┐   │   │
│  │  │   Qdrant    │ │ PostgreSQL  │ │    Web UI      │   │   │
│  │  │   :6333     │ │   :5433     │ │    :3000       │   │   │
│  │  │  (vectors)  │ │ (relations) │ │   (browser)    │   │   │
│  │  └─────────────┘ └─────────────┘ └────────────────┘   │   │
│  └──────────────────────────────────────────────────────┘   │
│                           ▲                                  │
│                           │                                  │
│  ┌────────────────────────┼─────────────────────────────┐   │
│  │  Any MCP Client (Claude Code, OpenCode, Cursor...)    │   │
│  │         ┌──────────────┴───────────────┐              │   │
│  │         │  Memoria Container (stdio)   │              │   │
│  │         │  ghcr.io/trapias/memoria     │              │   │
│  │         │  (one per session, isolated) │              │   │
│  │         └──────────────────────────────┘              │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## Web UI

The Web UI provides a browser-based interface to explore and manage your memories. Access it at **http://localhost:3000** after starting the Docker services.

### Features

- **Dashboard**: Overview of memory statistics, recent activity, and quick actions
- **Knowledge Graph Explorer**: Interactive force-directed graph visualization of memory relationships
  - Click nodes to view memory details
  - Drag to rearrange the layout
  - Filter by relation type
  - Zoom and pan navigation
- **Memory Browser**: Search and browse all stored memories
  - Semantic search with filters
  - Filter by memory type (episodic, semantic, procedural)
  - Sort by date, importance, or relevance
- **Relation Management**: Create, view, and delete relationships between memories
- **AI Suggestions**: Get recommended relations based on content similarity

---

## Usage

Once configured, Claude will have access to memory tools. You can interact naturally — Claude will automatically use the appropriate memory tools based on your requests.

### Quick Test Commands

Try these commands in Claude to verify Memoria is working:

```
# Check system status
Show me the memoria stats

# Store a test memory
Remember this: The project uses Python 3.11 and FastAPI

# Recall memories
What do you remember about this project?
```

### Available Tools

**Memory Tools:**

| Tool | Description |
|------|-------------|
| `memoria_store` | Store new memories |
| `memoria_recall` | Recall memories by semantic similarity (supports `text_match` keyword filter) |
| `memoria_search` | Advanced search with filters (supports `text_match` keyword filter) |
| `memoria_update` | Update existing memories |
| `memoria_delete` | Delete memories |
| `memoria_consolidate` | Merge similar memories |
| `memoria_export` | Export memories to file (JSON/JSONL, optional vector export) |
| `memoria_import` | Import memories from file (merge or replace mode) |
| `memoria_stats` | View system statistics |
| `memoria_set_context` | Set current project/file context |

**Knowledge Graph Tools** (require PostgreSQL):

| Tool | Description |
|------|-------------|
| `memoria_link` | Create a relationship between two memories |
| `memoria_unlink` | Remove a relationship between memories |
| `memoria_related` | Find memories related through the knowledge graph |
| `memoria_path` | Find shortest path between two memories |
| `memoria_suggest_links` | Get AI-powered relation suggestions |

**Time Tracking Tools** (require PostgreSQL):

| Tool | Description |
|------|-------------|
| `memoria_work_start` | Start tracking a work session |
| `memoria_work_stop` | Stop active session and get duration |
| `memoria_work_status` | Check if a session is active |
| `memoria_work_pause` | Pause session (e.g., for breaks) |
| `memoria_work_resume` | Resume a paused session |
| `memoria_work_note` | Add notes to active session |
| `memoria_work_report` | Generate time tracking reports |

### Skill: `/memoria-guide`

If you're using Claude Code or OpenCode, you can type `/memoria-guide` at any time to get a quick reference for all Memoria tools. This skill provides:

- Complete list of all memory, knowledge graph, and time tracking tools
- Memory types reference (episodic, semantic, procedural)
- Importance level guidelines (0-1 scale)
- Common usage patterns and examples
- Tag naming conventions
- Session workflow recommendations

This is especially useful when you're not sure which tool to use or need a quick reminder of the available options without leaving your conversation.

#### Installing the Skill

The skill is included in the repository at `.claude/skills/memoria-guide/SKILL.md`. Both Claude Code and OpenCode discover skills from the same `.claude/skills/` directory.

**Option 1: Project-level (automatic)**

If you're working inside the `mcp-memoria` directory, the skill is automatically available — no installation needed.

**Option 2: User-level (available in all projects)**

To make the skill available globally in any project:

```bash
# Create the user skills directory if it doesn't exist
mkdir -p ~/.claude/skills

# Copy the skill directory (skills must be directories, not single files)
cp -r .claude/skills/memoria-guide ~/.claude/skills/
```

> **Note**: After installing or updating skills, restart Claude Code or OpenCode for changes to take effect.

After installation, type `/memoria-guide` in any session to load the quick reference.

---

## Example Interactions

### Storing Different Memory Types

**Semantic memories** (facts and knowledge):
```
Remember that the API endpoint for users is /api/v1/users
Store this: The database password is rotated every 30 days
```

**Episodic memories** (events and experiences):
```
Log this event: Deployed version 2.1.0 to production today
Remember that we had a meeting about the new auth system
```

**Procedural memories** (how-to and workflows):
```
Save this procedure: To deploy, run ./scripts/deploy.sh --env prod
Remember the steps to set up the dev environment
```

### Recalling Memories

```
# Semantic search - finds relevant memories by meaning
What do you know about the database?
How do we handle authentication?

# With filters
Search memories about deployment from last week
Find all procedural memories about testing
```

### Project Context

Set context to associate memories with a specific project:

```
Set the project context to "ecommerce-api"
Now remember that this project uses Stripe for payments
```

Later, when working on the same project:
```
What do you remember about the ecommerce-api project?
```

### Knowledge Graph

Create and explore relationships between memories:

```
# Create a relationship
Link memory [problem-id] to [solution-id] with type "fixes"

# Find related memories
What memories are related to [memory-id]?
Show me all memories that this one causes

# Find connections
Is there a path between [memory-a] and [memory-b]?

# Get suggestions
Suggest relationships for memory [id]
```

**Relation Types:**

| Type | Description | Example |
|------|-------------|---------|
| `causes` | A leads to B | Decision → Consequence |
| `fixes` | A resolves B | Solution → Problem |
| `supports` | A confirms B | Evidence → Claim |
| `opposes` | A contradicts B | Counterargument → Argument |
| `follows` | A comes after B | Event → Previous event |
| `supersedes` | A replaces B | New fact → Old fact |
| `derives` | A is derived from B | Summary → Original |
| `part_of` | A is component of B | Chapter → Book |
| `related` | Generic connection | Any correlation |

### Memory Management

```
# Update a memory
Update memory [id] to include the new API version

# Delete memories
Delete all memories about the old authentication system
Forget the deprecated deployment process

# Consolidate similar memories
Consolidate memories to merge duplicates

# Export/Import
Export all memories to backup.json
Import memories from shared-knowledge.json
```

### Time Tracking

Track time spent on tasks, issues, and projects (requires PostgreSQL):

```
# Start tracking work
Start working on fixing the login timeout issue for AuthService

# Check status
What am I working on?

# Add a note
Note: Found the bug - timeout was set to 10s instead of 30s

# Take a break
Pause work for lunch

# Resume
Resume working

# Stop and see duration
Stop working - fixed by increasing timeout to 30s

# Get reports
Show me my work report for this week
How much time did I spend on AuthService this month?
```

Time tracking supports:
- **Categories**: coding, review, meeting, support, research, documentation, devops
- **Clients and Projects**: Track billable hours per client/project
- **GitHub integration**: Link sessions to issues and PRs
- **Pause/Resume**: Exclude breaks from work time
- **Reports**: Aggregate by period, client, project, or category

---

## Tips for Effective Use

1. **Be specific**: "Remember the PostgreSQL connection string is postgres://..." is better than "Remember the database info"

2. **Use context**: Set project context when working on specific projects to keep memories organized

3. **Regular consolidation**: Run consolidation periodically to merge similar memories and reduce redundancy

4. **Importance levels**: Mention importance for critical information: "This is important: never delete the production database"

5. **Natural language**: You don't need special syntax — just talk naturally about what you want to remember or recall

---

## CLI Options

```bash
mcp-memoria                    # Start MCP server (stdio)
mcp-memoria --version          # Show version
mcp-memoria --update           # Update to latest version (native install only)
mcp-memoria --skip-update-check  # Start without checking for updates
```

Environment variable: `MEMORIA_SKIP_UPDATE_CHECK=true` disables the startup update check.

---

## Advanced Topics

### Backup & Recovery

Memoria includes a backup script (`scripts/backup_memoria.py`) that exports all memories with their embeddings to a JSON file, enabling full restore without re-embedding.

#### Manual Backup

```bash
# Full backup (default: ~/.mcp-memoria/backups/)
uv run scripts/backup_memoria.py

# Custom output directory, keep last 5 backups
uv run scripts/backup_memoria.py --output-dir /path/to/backups --keep 5

# Connect to non-default Qdrant
uv run scripts/backup_memoria.py --host 192.168.1.100 --port 6333
```

Backup files are named `memoria-backup-YYYYMMDD-HHMMSS.json` and include all three collections (episodic, semantic, procedural) with vectors.

#### Automated Backups (macOS)

Use a LaunchAgent to schedule automatic backups. Create `~/Library/LaunchAgents/com.memoria.backup.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.memoria.backup</string>
    <key>ProgramArguments</key>
    <array>
        <string>/opt/homebrew/bin/uv</string>
        <string>run</string>
        <string>--directory</string>
        <string>/path/to/mcp-memoria</string>
        <string>scripts/backup_memoria.py</string>
        <string>--keep</string>
        <string>20</string>
    </array>
    <key>StartCalendarInterval</key>
    <array>
        <dict><key>Hour</key><integer>1</integer><key>Minute</key><integer>0</integer></dict>
        <dict><key>Hour</key><integer>7</integer><key>Minute</key><integer>0</integer></dict>
        <dict><key>Hour</key><integer>13</integer><key>Minute</key><integer>0</integer></dict>
        <dict><key>Hour</key><integer>19</integer><key>Minute</key><integer>0</integer></dict>
    </array>
    <key>StandardOutPath</key>
    <string>/Users/you/.mcp-memoria/backups/backup.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/you/.mcp-memoria/backups/backup-error.log</string>
</dict>
</plist>
```

Load with: `launchctl load ~/Library/LaunchAgents/com.memoria.backup.plist`

On Linux, use a cron job instead:

```bash
# Every 6 hours
0 1,7,13,19 * * * cd /path/to/mcp-memoria && uv run scripts/backup_memoria.py --keep 20
```

#### Restore from Backup

> **Note**: Full restore requires a backup created with `include_vectors: true` (the default for `backup_memoria.py`). Backups created via `memoria_export` without `include_vectors` cannot be restored directly — they would need re-embedding.

Use the `memoria_import` MCP tool, or restore directly via the Qdrant API:

```bash
# Via MCP (in Claude)
Import memories from ~/.mcp-memoria/backups/memoria-backup-20260207-130120.json

# Via Python script
python -c "
from qdrant_client import QdrantClient
import json

client = QdrantClient(host='localhost', port=6333)
backup = json.load(open('path/to/backup.json'))

for coll, items in backup['collections'].items():
    points = [{'id': p['id'], 'vector': p['vector'], 'payload': p['payload']} for p in items]
    # Upsert in batches of 100
    for i in range(0, len(points), 100):
        client.upsert(collection_name=coll, points=points[i:i+100])
"
```

### Multi-Node Sync

If you run Qdrant on multiple machines (e.g., a Mac and a Linux server), you can keep them synchronized using the included sync script.

The sync script (`scripts/sync_qdrant.py`) performs **incremental bidirectional synchronization**:

- **New memories**: Copied to the other node
- **Updated memories**: Newer timestamp wins
- **Deleted memories**: Propagated to the other node (with safety limits)

```bash
# Run sync
python scripts/sync_qdrant.py

# Dry run (show what would happen)
python scripts/sync_qdrant.py --dry-run

# Verbose output
python scripts/sync_qdrant.py -v

# Reset sync state (treat all points as new, no deletions)
python scripts/sync_qdrant.py --reset-state
```

Edit the script to set your node addresses:

```python
LOCAL_URL = "http://localhost:6333"
REMOTE_URL = "http://your-server.local:6333"
```

#### Safety Features

The sync script includes multiple layers of protection against accidental data loss:

1. **Pre-sync backup**: A full snapshot of local data is saved to `~/.mcp-memoria/backups/pre-sync/` before every sync run (last 5 kept)
2. **Fetch error detection**: If a node fails to respond, the sync aborts instead of treating it as "all data deleted"
3. **Empty-vs-full asymmetry check**: If one side has 0 points and the other has many, the sync skips that collection (likely a connectivity issue, not a real deletion)
4. **Deletion cap**: Maximum 20 deletions per sync run; anything above aborts with a warning

#### Automated Sync (macOS)

Create `~/Library/LaunchAgents/com.memoria.qdrant-sync.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.memoria.qdrant-sync</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/mcp-memoria/.venv/bin/python</string>
        <string>/path/to/mcp-memoria/scripts/sync_qdrant.py</string>
    </array>
    <key>StartInterval</key>
    <integer>3600</integer>
    <key>StandardOutPath</key>
    <string>/tmp/qdrant-sync.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/qdrant-sync.log</string>
</dict>
</plist>
```

### HTTP/SSE Transport

> **Warning**: HTTP mode is for testing/development only. It shares WorkingMemory across all connected clients, which can cause context confusion.

For scenarios where you can't spawn processes (web apps, remote access):

```bash
# Start HTTP server
cd docker && docker-compose -f docker-compose.http.yml up -d

# Configure Claude to connect via URL
{
  "mcpServers": {
    "memoria": {
      "url": "http://localhost:8765/sse"
    }
  }
}
```

**Endpoints:**
- `GET /sse` — SSE connection endpoint
- `POST /messages/` — Message endpoint
- `GET /health` — Health check

### Content Chunking

When a memory exceeds `MEMORIA_CHUNK_SIZE` characters (default 500), it is automatically split into overlapping chunks. Each chunk is stored as a separate Qdrant point with its own embedding, linked to the original memory via a `parent_id`.

**How it works:**

- **Store**: long content → TextChunker → N chunks → N embeddings → N Qdrant points (same `parent_id`)
- **Recall/Search**: query matches individual chunks; results are deduplicated by `parent_id`, returning the full original content
- **Update**: content changes delete all existing chunks and re-create them; metadata-only changes propagate to every chunk
- **Delete**: removes all points belonging to the logical memory

Chunking is transparent — callers always see complete memories, never individual chunks.

---

## Configuration

All settings via environment variables with `MEMORIA_` prefix:

**Core:**

| Variable | Default | Description |
|----------|---------|-------------|
| `MEMORIA_QDRANT_HOST` | - | Qdrant server host |
| `MEMORIA_QDRANT_PORT` | `6333` | Qdrant port |
| `MEMORIA_QDRANT_PATH` | `~/.mcp-memoria/qdrant` | Local Qdrant storage path (if no host) |
| `MEMORIA_OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |
| `MEMORIA_EMBEDDING_MODEL` | `nomic-embed-text` | Embedding model |
| `MEMORIA_EMBEDDING_DIMENSIONS` | `768` | Embedding vector dimensions |
| `MEMORIA_CACHE_ENABLED` | `true` | Enable embedding cache |
| `MEMORIA_CACHE_PATH` | `~/.mcp-memoria/cache` | Path for embedding cache |
| `MEMORIA_CHUNK_SIZE` | `500` | Max characters per chunk |
| `MEMORIA_CHUNK_OVERLAP` | `50` | Overlap between consecutive chunks |
| `MEMORIA_LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `MEMORIA_LOG_FILE` | - | Path to log file (in addition to stderr) |
| `MEMORIA_HTTP_PORT` | - | HTTP port (enables HTTP mode) |
| `MEMORIA_HTTP_HOST` | `0.0.0.0` | HTTP host to bind to |
| `MEMORIA_DATABASE_URL` | - | PostgreSQL URL for Knowledge Graph and Time Tracking |
| `MEMORIA_SKIP_UPDATE_CHECK` | `false` | Disable startup update check |

**Advanced tuning:**

| Variable | Default | Description |
|----------|---------|-------------|
| `MEMORIA_DEFAULT_MEMORY_TYPE` | `episodic` | Default memory type for storage |
| `MEMORIA_DEFAULT_RECALL_LIMIT` | `5` | Default number of results for recall |
| `MEMORIA_MIN_SIMILARITY_SCORE` | `0.5` | Minimum similarity score for recall |
| `MEMORIA_CONSOLIDATION_THRESHOLD` | `0.9` | Similarity threshold for memory consolidation |
| `MEMORIA_FORGETTING_DAYS` | `30` | Days before forgetting unused memories |
| `MEMORIA_MIN_IMPORTANCE_THRESHOLD` | `0.3` | Minimum importance to retain during forgetting |
| `MEMORIA_DB_MIGRATE` | `false` | Run database migrations on startup |
| `MEMORIA_DB_POOL_MIN` | `2` | Minimum database connection pool size |
| `MEMORIA_DB_POOL_MAX` | `10` | Maximum database connection pool size |

---

## Memory Types

### Episodic Memory
For events and experiences:
- Conversations
- Decisions made
- Problems encountered
- Meeting notes

### Semantic Memory
For facts and knowledge:
- Project configurations
- API endpoints
- Best practices
- Technical documentation

### Procedural Memory
For skills and procedures:
- Deployment workflows
- Build commands
- Testing procedures
- Common code patterns

---

## Troubleshooting

### Common Issues

#### "Failed to connect" when starting Claude

**Most common cause**: Backend services not running. Make sure to start Docker services BEFORE launching Claude.

1. **Check Qdrant is running**:
   ```bash
   curl http://localhost:6333/health
   # Should return: {"title":"qdrant","version":"..."}
   ```

2. **Check Ollama is running**:
   ```bash
   curl http://localhost:11434/api/tags
   # Should return list of models
   ```

3. **Verify the embedding model is installed**:
   ```bash
   ollama list | grep nomic-embed-text
   ```

4. **Check PostgreSQL (if using full setup)**:
   ```bash
   docker exec memoria-postgres pg_isready -U memoria
   ```

#### "Connection refused" errors

- Ensure services are running: `docker compose -f docker-compose.server.yml ps`
- For Docker setups, verify the network: `docker network ls | grep memoria`
- Check firewall settings if running on remote servers

#### Memories not being found

- Run `memoria_stats` to verify memories are being stored
- Check that the embedding model is working
- Try consolidating memories if you have many similar entries

#### Slow performance

- The first query may be slow as models are loaded into memory
- Ensure Ollama is using GPU acceleration if available
- Consider using a smaller embedding model for faster results

### Debug Mode

Enable debug logging for more information:

```bash
export MEMORIA_LOG_LEVEL=DEBUG
```

Or in Claude config:
```json
{
  "env": {
    "MEMORIA_LOG_LEVEL": "DEBUG",
    "MEMORIA_LOG_FILE": "/tmp/memoria.log"
  }
}
```

### Reset All Data

To completely reset Memoria and start fresh:

```bash
# Stop services and delete all data (irreversible!)
docker compose -f docker-compose.server.yml down -v
docker compose -f docker-compose.server.yml up -d
```

---

## Development

```bash
# Clone and install with dev dependencies
git clone https://github.com/trapias/memoria.git
cd memoria
pip install -e ".[dev]"

# Run tests
pytest

# Type checking
mypy src/mcp_memoria

# Linting
ruff check src/mcp_memoria

# Build Docker images locally
docker build -t mcp-memoria -f docker/Dockerfile .
docker build -t memoria-ui -f docker/Dockerfile.ui .
```

---

## Comparison

| Feature | MCP Memoria | Memvid | Mem0 |
|---------|-------------|--------|------|
| Storage Limit | Unlimited | 50MB free | Varies |
| Local-only | Yes | Partial | No |
| MCP Native | Yes | No | No |
| Cost | Free | Freemium | Freemium |
| Vector DB | Qdrant | Custom | Cloud |

---

## License

Apache 2.0

## Contributing

Contributions welcome! Please read CONTRIBUTING.md first.
