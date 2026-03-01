---
updated: 2026-02-28 16:31:16
---

# MCP Memoria

> **Unlimited, persistent, local-first AI memory — 100% private, 100% yours.**

Ever had to re-explain your project context to Claude every single session? Switching between Claude Code, Cursor, and Windsurf and losing the thread every time? Wish your AI assistant actually remembered who you are, how you work, and what you've already solved?

**MCP Memoria fixes all of that.**

It's a Model Context Protocol (MCP) server that brings persistent, semantic, and structured memory to any compatible client — Claude Code, Claude Desktop, Cursor, Windsurf, OpenCode, and more. Everything runs on your machine. No cloud. No storage limits. No subscription.

-----

## Why MCP Memoria?

- **Unlimited storage** — no caps, no quotas, no plan tiers
- **100% local & private** — all data stays on your machine, zero cloud dependencies
- **MCP native** — works with any MCP-compatible client out of the box
- **Knowledge Graph** — typed relationships between memories with graph traversal
- **Built-in Time Tracking** — track work sessions per client and project directly from your AI assistant
- **Web UI included** — browser-based memory explorer and graph visualization
- **Free and open source** — Apache 2.0 license, no subscriptions

-----

## Quick Start (5 minutes with Docker)

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- [Ollama](https://ollama.com/download) with the `nomic-embed-text` model

```bash
# Install and start Ollama (if not already running)
# macOS: brew install ollama
# Linux: curl -fsSL https://ollama.com/install.sh | sh
ollama serve &
ollama pull nomic-embed-text
```

### Step 1 — Start the backend services

```bash
mkdir -p memoria && cd memoria

curl -O https://raw.githubusercontent.com/trapias/memoria/main/docker/docker-compose.server.yml

docker compose -f docker-compose.server.yml up -d
```

This starts:

|Service   |Port|Description                        |
|----------|----|-----------------------------------|
|Qdrant    |6333|Vector database for semantic search|
|PostgreSQL|5433|Knowledge Graph + Time Tracking    |
|Web UI    |3000|Browser-based memory explorer      |
|REST API  |8765|Custom integrations                |

### Step 2 — Configure your MCP client

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

**Claude Code / Claude Desktop** (`~/.claude.json` or `claude_desktop_config.json`):

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

> **Config file locations:**
>
> - Claude Desktop (macOS): `~/Library/Application Support/Claude/claude_desktop_config.json`
> - Claude Desktop (Windows): `%APPDATA%\Claude\claude_desktop_config.json`

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
codex mcp add memoria \
  --env MEMORIA_QDRANT_HOST=qdrant \
  --env MEMORIA_QDRANT_PORT=6333 \
  --env "MEMORIA_DATABASE_URL=postgresql://memoria:memoria_dev@postgres:5432/memoria" \
  --env "MEMORIA_OLLAMA_HOST=http://host.docker.internal:11434" \
  --env MEMORIA_LOG_LEVEL=WARNING \
  -- docker run --rm -i --network memoria-network \
  -e MEMORIA_DATABASE_URL -e MEMORIA_QDRANT_HOST \
  -e MEMORIA_QDRANT_PORT -e MEMORIA_OLLAMA_HOST \
  -e MEMORIA_LOG_LEVEL ghcr.io/trapias/memoria:latest
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

### Step 3 — Verify

Open your client and type:

```
Show me the memoria stats
```

If you see statistics, Memoria is working. Also visit <http://localhost:3000> for the Web UI.

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

### Update

```bash
# Update backend services
docker compose -f docker-compose.server.yml pull
docker compose -f docker-compose.server.yml up -d

# The MCP client image updates automatically — docker run pulls :latest on next session
docker pull ghcr.io/trapias/memoria:latest
```

To pin a specific version, replace `:latest` with a version tag (e.g., `:1.3.0`) in your MCP client config.

-----

## Real-world use cases

### Developer across multiple projects

You work on three projects in parallel. With Memoria you can tell Claude *"Set project context to ecommerce-api"* and it will remember the stack, endpoints, conventions, and past architectural decisions — no re-explaining needed.

### Multi-tool workflow

Define requirements in Claude Desktop, write code in Cursor, debug in Windsurf. With Memoria you share the same persistent context across all tools, because memories are stored centrally in Qdrant.

### Freelancers and consultants

Track time per project and client directly from Claude: *"Start working on fixing the login bug for ClientX"* — and at the end of the week: *"Show me my work report for this week"*. Parallel sessions supported.

### Research and knowledge management

Accumulate knowledge on a domain over time. Use *Reflection* to synthesize insights, build decision timelines, compare approaches — like a second brain, always available.

-----

## Core features

### Three memory types

|Type          |Description             |Examples                                         |
|--------------|------------------------|-------------------------------------------------|
|**Episodic**  |Events and conversations|"Deployed v2.1.0 today", "Meeting about new auth"|
|**Semantic**  |Facts and knowledge     |API endpoints, passwords, best practices         |
|**Procedural**|Workflows and procedures|How to deploy, dev environment setup             |

### Advanced hybrid search

Combines semantic vector search, keyword matching, and graph traversal using **Reciprocal Rank Fusion (RRF)** — finds memories even when you use different words than you used when saving them.

### Knowledge Graph

Create typed relationships between memories and navigate your knowledge like a graph:

|Relation    |Meaning              |
|------------|---------------------|
|`causes`    |A leads to B         |
|`fixes`     |A resolves B         |
|`supports`  |A confirms B         |
|`opposes`   |A contradicts B      |
|`follows`   |A comes after B      |
|`supersedes`|A replaces B         |
|`derives`   |A is derived from B  |
|`part_of`   |A is a component of B|
|`related`   |Generic connection   |

### Reflection & Observation

LLM-powered tools to reason over your memories — not just storage, but real cognitive processing:

- **synthesis**: unified summary merging all relevant memories (default)
- **timeline**: chronological narrative of events
- **comparison**: side-by-side contrast of different approaches
- **analysis**: deep pattern analysis with insights

### Content Chunking

When a memory exceeds `MEMORIA_CHUNK_SIZE` characters (default 500), it is automatically split into overlapping chunks. Each chunk is stored as a separate Qdrant point with its own embedding, linked to the original memory via a `parent_id`.

**How it works:**

- **Store**: long content → TextChunker → N chunks → N embeddings → N Qdrant points (same `parent_id`)
- **Recall/Search**: query matches individual chunks; results are deduplicated by `parent_id`, returning the full original content
- **Update**: content changes delete all existing chunks and re-create them; metadata-only changes propagate to every chunk
- **Delete**: removes all points belonging to the logical memory

Chunking is transparent — callers always see complete memories, never individual chunks.

### Time Tracking

Directly from Claude, no external tools needed:

```
Start working on fixing the auth bug for ClientX
Note: Found the issue — JWT expiry was set to 10s
Stop working — fixed, timeout now 30s

Show me my work report for this week
```

Supports parallel sessions, categories (coding, review, meeting, research...), GitHub issue and PR links, pause/resume.

### Web UI

Browser interface at [localhost:3000](http://localhost:3000) with:

- **Dashboard**: Overview of memory statistics, recent activity, and quick actions
- **Knowledge Graph Explorer**: Interactive force-directed graph visualization
  - Click nodes to view memory details
  - Drag to rearrange the layout
  - Filter by relation type
  - Zoom and pan navigation
- **Memory Browser**: Search and filter all memories
  - Semantic search with filters
  - Filter by memory type (episodic, semantic, procedural)
  - Sort by date, importance, or relevance
- **Relation Management**: Create, view, and delete relationships between memories
- **AI Suggestions**: Get recommended relations based on content similarity
- **Data Management**: Browse and manage PostgreSQL data (requires PostgreSQL)
  - **Sessions**: View, create, edit, and delete work sessions with filters (date range, category, client, project, status, text search), summary cards (total hours, session count, average duration), and CSV export
  - **Clients**: Manage clients with aggregate stats (project count, session count, total hours, last activity) and JSON metadata
  - **Projects**: Manage projects linked to clients, with GitHub repo links and automatic client propagation to unlinked sessions
  - **Relations**: Browse memory relations with enriched previews from Qdrant, filter by type/creator/memory, and clean up orphaned relations

### More features

- **Memory Consolidation** — automatically merges similar memories to reduce redundancy
- **Forgetting Curve** — natural decay of unused, low-importance memories
- **Backup & Restore** — full export/import including vectors
- **Multi-node Sync** — incremental bidirectional sync between machines
- **Temporal filters** — natural language date filters in English and Italian: "last week", "last 3 days", "ultima settimana"
- **Compact Mode** — token-efficient recall that returns summaries instead of full content

-----

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Your Machine                            │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Ollama (native)                                      │   │
│  │  http://localhost:11434                               │   │
│  │  Provides: nomic-embed-text (embeddings)              │   │
│  │            + LLM model (reflect/observe)              │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Docker Services                                      │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌────────────────┐  │   │
│  │  │   Qdrant    │ │ PostgreSQL  │ │    Web UI      │  │   │
│  │  │   :6333     │ │   :5433     │ │    :3000       │  │   │
│  │  │  (vectors)  │ │  (relations)│ │   (browser)    │  │   │
│  │  └─────────────┘ └─────────────┘ └────────────────┘  │   │
│  └──────────────────────────────────────────────────────┘   │
│                           ▲                                  │
│  ┌────────────────────────┼─────────────────────────────┐   │
│  │  Any MCP Client                                       │   │
│  │  (Claude Code, OpenCode, Cursor, Windsurf…)           │   │
│  │       ┌──────────────────────────────┐                │   │
│  │       │  Memoria Container (stdio)   │                │   │
│  │       │  one per session, isolated   │                │   │
│  │       └──────────────────────────────┘                │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

> **Why one container per session?** Memoria maintains an in-memory WorkingMemory per session — this includes the current project context, recent session history, active memory cache, and any state built up during the conversation. If a single shared container served all clients simultaneously, concurrent Claude sessions (e.g. one in Claude Code and one in Cursor) would bleed into each other's context, causing unpredictable and confusing behavior. Spawning a fresh container per session via `docker run` guarantees complete isolation: each session starts clean, builds its own context independently, and terminates without affecting anything else. The persistent data (memories, relations, time tracking) lives safely in Qdrant and PostgreSQL, shared across sessions by design — only the ephemeral in-process state is isolated.

-----

## Available tools

### Memory Tools

|Tool                 |Description                                                          |
|---------------------|---------------------------------------------------------------------|
|`memoria_store`      |Store new memories                                                   |
|`memoria_recall`     |Recall memories by semantic similarity (supports `text_match` keyword filter)|
|`memoria_search`     |Advanced search with filters (supports `text_match` keyword filter)  |
|`memoria_update`     |Update existing memories                                             |
|`memoria_delete`     |Delete memories                                                      |
|`memoria_consolidate`|Merge similar memories                                               |
|`memoria_export`     |Export to JSON/JSONL (optional vector export)                        |
|`memoria_import`     |Import from file (merge or replace mode)                             |
|`memoria_stats`      |View system statistics                                               |
|`memoria_set_context`|Set current project/file context                                     |
|`memoria_reflect`    |LLM reasoning over memories (synthesis, timeline, comparison, analysis)|
|`memoria_observe`    |Find memory clusters and generate higher-level observations          |

### Knowledge Graph Tools *(require PostgreSQL)*

|Tool                   |Description                               |
|-----------------------|------------------------------------------|
|`memoria_link`         |Create a relationship between two memories|
|`memoria_unlink`       |Remove a relationship                     |
|`memoria_related`      |Find memories connected through the graph |
|`memoria_path`         |Find shortest path between two memories   |
|`memoria_suggest_links`|Get AI-powered relation suggestions       |

### Time Tracking Tools *(require PostgreSQL)*

|Tool                 |Description                                                                    |
|---------------------|-------------------------------------------------------------------------------|
|`memoria_work_start` |Start tracking a work session (supports parallel sessions)                     |
|`memoria_work_stop`  |Stop a session and record duration (specify `session_id` if multiple active)   |
|`memoria_work_status`|Show all active/paused sessions with warnings                                  |
|`memoria_work_pause` |Pause a session (specify `session_id` if multiple active)                      |
|`memoria_work_resume`|Resume a paused session (specify `session_id` if multiple paused)              |
|`memoria_work_note`  |Add notes to a session (specify `session_id` if multiple active)               |
|`memoria_work_report`|Generate time reports by period/client/project                                 |

-----

## Example interactions

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

# Hybrid search (combines semantic + keyword + graph)
Search memories about deployment using hybrid mode

# Temporal filters (English and Italian)
What happened last week?
Search memories from the last 3 days
Cerca nelle memorie di questa settimana

# Compact mode (saves tokens in long conversations)
Recall memories about authentication with compact=true

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

### Reflection and Observation

```
# Synthesize insights from related memories
Reflect on what we know about the authentication system

# Build a timeline of events
Reflect on the deployment history with style=timeline

# Compare approaches
Reflect on the pros and cons of our caching strategies with style=comparison

# Deep analysis
Reflect deeply on the project architecture with depth=deep

# Find memory clusters and generate observations (dry run first)
Observe patterns in my semantic memories

# Generate and store observations
Observe my episodic memories with dry_run=false
```

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

```
# Start tracking work
Start working on fixing the login timeout issue for AuthService

# Start a second parallel session
Start working on reviewing PR #42 for Memoria

# Check status — shows all active sessions
What am I working on?

# Add a note (auto-targets if only 1 session, asks if multiple)
Note: Found the bug - timeout was set to 10s instead of 30s

# Take a break
Pause work for lunch

# Resume
Resume working

# Stop a specific session when multiple are active
Stop working on the login fix - increased timeout to 30s

# Get reports
Show me my work report for this week
How much time did I spend on AuthService this month?
```

Time tracking supports:
- **Parallel sessions**: Run multiple sessions simultaneously (configurable limit, default 3)
  - **Hybrid disambiguation**: With 1 session, everything works without `session_id` — fully transparent. With multiple sessions, the system asks you to specify which one
  - **Smart warnings**: Alerts for sessions open too long, duplicate sessions on the same project, and approaching the parallel limit
- **Categories**: coding, review, meeting, support, research, documentation, devops
- **Clients and Projects**: Track billable hours per client/project
- **GitHub integration**: Link sessions to issues and PRs
- **Pause/Resume**: Exclude breaks from work time
- **Reports**: Aggregate by period, client, project, or category

-----

## Tips for Effective Use

1. **Be specific**: "Remember the PostgreSQL connection string is postgres://..." is better than "Remember the database info"

2. **Use context**: Set project context when working on specific projects to keep memories organized

3. **Regular consolidation**: Run consolidation periodically to merge similar memories and reduce redundancy

4. **Importance levels**: Mention importance for critical information: "This is important: never delete the production database"

5. **Natural language**: You don't need special syntax — just talk naturally about what you want to remember or recall

-----

## Configuration

All settings via environment variables with the `MEMORIA_` prefix:

### Core

|Variable                       |Default                 |Description                                     |
|-------------------------------|------------------------|-------------------------------------------------|
|`MEMORIA_QDRANT_HOST`          |—                       |Qdrant server host                               |
|`MEMORIA_QDRANT_PORT`          |`6333`                  |Qdrant port                                      |
|`MEMORIA_QDRANT_PATH`          |`~/.mcp-memoria/qdrant` |Local Qdrant storage path (if no host)            |
|`MEMORIA_OLLAMA_HOST`          |`http://localhost:11434`|Ollama server URL                                |
|`MEMORIA_EMBEDDING_MODEL`      |`nomic-embed-text`      |Embedding model                                  |
|`MEMORIA_EMBEDDING_DIMENSIONS` |`768`                   |Embedding vector dimensions                      |
|`MEMORIA_LLM_MODEL`            |`llama3.2`              |LLM for reflect and observe tools                |
|`MEMORIA_CACHE_ENABLED`        |`true`                  |Enable embedding cache                            |
|`MEMORIA_CACHE_PATH`           |`~/.mcp-memoria/cache`  |Path for embedding cache                          |
|`MEMORIA_CHUNK_SIZE`           |`500`                   |Max characters per chunk                          |
|`MEMORIA_CHUNK_OVERLAP`        |`50`                    |Overlap between consecutive chunks                |
|`MEMORIA_DATABASE_URL`         |—                       |PostgreSQL URL (Knowledge Graph + Time Tracking)  |
|`MEMORIA_LOG_LEVEL`            |`INFO`                  |Logging level (DEBUG, INFO, WARNING, ERROR)       |
|`MEMORIA_LOG_FILE`             |—                       |Path to log file (in addition to stderr)          |
|`MEMORIA_HTTP_PORT`            |—                       |HTTP port (enables HTTP mode)                     |
|`MEMORIA_HTTP_HOST`            |`0.0.0.0`               |HTTP host to bind to                              |
|`MEMORIA_SKIP_UPDATE_CHECK`    |`false`                 |Disable startup update check                      |

### Advanced tuning

|Variable                            |Default|Description                             |
|------------------------------------|-------|----------------------------------------|
|`MEMORIA_DEFAULT_MEMORY_TYPE`       |`episodic`|Default memory type for storage      |
|`MEMORIA_DEFAULT_RECALL_LIMIT`      |`5`    |Default number of results for recall    |
|`MEMORIA_MIN_SIMILARITY_SCORE`      |`0.5`  |Minimum similarity threshold for recall |
|`MEMORIA_CONSOLIDATION_THRESHOLD`   |`0.9`  |Similarity threshold for consolidation  |
|`MEMORIA_FORGETTING_DAYS`           |`30`   |Days before forgetting unused memories  |
|`MEMORIA_MIN_IMPORTANCE_THRESHOLD`  |`0.3`  |Minimum importance to retain during forgetting|
|`MEMORIA_DB_MIGRATE`                |`false`|Run database migrations on startup      |
|`MEMORIA_DB_POOL_MIN`               |`2`    |Minimum database connection pool size   |
|`MEMORIA_DB_POOL_MAX`               |`10`   |Maximum database connection pool size   |
|`MEMORIA_WORK_MAX_PARALLEL_SESSIONS`|`3`    |Max parallel active/paused work sessions|
|`MEMORIA_WORK_SESSION_WARNING_HOURS`|`8.0`  |Hours before a session triggers a forgotten-session warning|

-----

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

-----

## Ollama Models

Memoria uses Ollama for two distinct purposes:

### Embedding Model (always active)

The embedding model converts text into vector representations for semantic search. It runs on every store, recall, and search operation.

| Variable | Default | Purpose |
|----------|---------|---------|
| `MEMORIA_EMBEDDING_MODEL` | `nomic-embed-text` | Text-to-vector conversion |

**Recommended:** `nomic-embed-text` is the best balance of quality and speed. Other supported models: `mxbai-embed-large` (1024d, higher quality), `bge-m3` (1024d, multilingual), `all-minilm` (384d, fastest).

> **Important**: Changing the embedding model after storing memories requires re-embedding all existing data (different models produce incompatible vectors). Stick with one model.

### LLM Model (reflect and observe only)

The LLM model is used exclusively by `memoria_reflect` and `memoria_observe` to generate natural language synthesis from retrieved memories. It is **not** used for basic store/recall/search operations.

| Variable | Default | Purpose |
|----------|---------|---------|
| `MEMORIA_LLM_MODEL` | `llama3.2` | Text generation for reflect/observe |

You can also override the model per-call using the `llm_model` parameter in either tool.

**Recommended models by hardware:**

| Model | Size | RAM | Quality | Speed | Best for |
|-------|------|-----|---------|-------|----------|
| `llama3.2` | 3B | ~4 GB | Good | Fast | Default, CPU-friendly |
| `gemma3:4b` | 4B | ~5 GB | Good | Fast | Alternative lightweight |
| `llama3.1:8b` | 8B | ~8 GB | Better | Medium | Better synthesis quality |
| `qwen2.5:7b` | 7B | ~7 GB | Better | Medium | Good multilingual support |
| `llama3.1:70b` | 70B | ~40 GB | Best | Slow | Maximum quality (GPU required) |

**Setup example:**

```bash
# Pull the embedding model (required)
ollama pull nomic-embed-text

# Pull an LLM model for reflect/observe (optional, only needed if you use these tools)
ollama pull llama3.2
```

**Docker configuration with custom LLM model:**

```bash
claude mcp add --scope user memoria -- \
  docker run --rm -i \
  --network memoria-network \
  -e MEMORIA_QDRANT_HOST=qdrant \
  -e MEMORIA_QDRANT_PORT=6333 \
  -e MEMORIA_DATABASE_URL=postgresql://memoria:memoria_dev@postgres:5432/memoria \
  -e MEMORIA_OLLAMA_HOST=http://host.docker.internal:11434 \
  -e MEMORIA_LLM_MODEL=llama3.1:8b \
  -e MEMORIA_LOG_LEVEL=WARNING \
  ghcr.io/trapias/memoria:latest
```

-----

## CLI Options

```bash
mcp-memoria                    # Start MCP server (stdio)
mcp-memoria --version          # Show version
mcp-memoria --update           # Update to latest version (native install only)
mcp-memoria --skip-update-check  # Start without checking for updates
```

Environment variable: `MEMORIA_SKIP_UPDATE_CHECK=true` disables the startup update check.

-----

## Alternative setups

### Local Python + Docker backend

For developers who want to modify Memoria or avoid Docker for the MCP process.

```bash
git clone https://github.com/trapias/memoria.git
cd memoria
pip install -e .

cd docker
docker network create memoria-network 2>/dev/null || true
docker compose -f docker-compose.central.yml up -d
```

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

<details>
<summary><strong>OpenCode</strong> (opencode.json)</summary>

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

</details>

<details>
<summary><strong>Codex</strong> (CLI)</summary>

```bash
codex mcp add memoria --env MEMORIA_QDRANT_HOST=localhost --env MEMORIA_QDRANT_PORT=6333 --env "MEMORIA_DATABASE_URL=postgresql://memoria:memoria_dev@localhost:5433/memoria" --env "MEMORIA_OLLAMA_HOST=http://localhost:11434" -- python -m mcp_memoria
```

</details>

<details>
<summary><strong>Codex</strong> (desktop app for macOS — <code>~/.codex/config.toml</code>)</summary>

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

</details>

Update: `git pull && pip install -e .` or `mcp-memoria --update`

### Qdrant only (minimal setup)

For quick testing, without Knowledge Graph or Time Tracking.

```bash
mkdir -p memoria && cd memoria
curl -O https://raw.githubusercontent.com/trapias/memoria/main/docker/docker-compose.qdrant-only.yml
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

-----

## Backup and restore

### Manual backup

```bash
# Full backup with vectors (recommended)
uv run scripts/backup_memoria.py

# Custom output directory, keep last 5 backups
uv run scripts/backup_memoria.py --output-dir /path/to/backups --keep 5

# Connect to non-default Qdrant
uv run scripts/backup_memoria.py --host 192.168.1.100 --port 6333
```

Backup files are named `memoria-backup-YYYYMMDD-HHMMSS.json` and include all three collections (episodic, semantic, procedural) with vectors.

### Automated backup (macOS)

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

### Restore

> **Note**: Full restore requires a backup created with `include_vectors: true` (the default for `backup_memoria.py`). Backups created via `memoria_export` without `include_vectors` cannot be restored directly — they would need re-embedding.

```
# From Claude
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

### Multi-machine sync

```bash
# Incremental bidirectional sync
python scripts/sync_qdrant.py

# Dry run (preview without changes)
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

**Safety features:**

The sync script includes multiple layers of protection against accidental data loss:

1. **Pre-sync backup**: A full snapshot of local data is saved to `~/.mcp-memoria/backups/pre-sync/` before every sync run (last 5 kept)
2. **Fetch error detection**: If a node fails to respond, the sync aborts instead of treating it as "all data deleted"
3. **Empty-vs-full asymmetry check**: If one side has 0 points and the other has many, the sync skips that collection (likely a connectivity issue, not a real deletion)
4. **Deletion cap**: Maximum 20 deletions per sync run; anything above aborts with a warning

#### Automated sync (macOS)

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

-----

## Skill: `/memoria-guide`

If you use Claude Code or OpenCode, type `/memoria-guide` at any time for a quick reference to all Memoria tools without leaving your conversation. This skill provides:

- Complete list of all memory, knowledge graph, and time tracking tools
- Memory types reference (episodic, semantic, procedural)
- Importance level guidelines (0-1 scale)
- Common usage patterns and examples
- Tag naming conventions
- Session workflow recommendations

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

-----

## Troubleshooting

### "Failed to connect" on startup

Make sure backend services are running **before** launching your client:

```bash
# Qdrant
curl http://localhost:6333/health

# Ollama
curl http://localhost:11434/api/tags

# Embedding model
ollama list | grep nomic-embed-text

# PostgreSQL
docker exec memoria-postgres pg_isready -U memoria
```

### "Connection refused" errors

- Ensure services are running: `docker compose -f docker-compose.server.yml ps`
- For Docker setups, verify the network: `docker network ls | grep memoria`
- Check firewall settings if running on remote servers

### Memories not being found

- Run `memoria_stats` to verify memories are being stored
- Check that the embedding model is working
- Try consolidating memories if you have many similar entries

### Slow performance

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

### Full reset

```bash
# Warning: irreversible — deletes all data
docker compose -f docker-compose.server.yml down -v
docker compose -f docker-compose.server.yml up -d
```

-----

## Development

```bash
git clone https://github.com/trapias/memoria.git
cd memoria
pip install -e ".[dev]"

pytest                          # Run tests
mypy src/mcp_memoria           # Type checking
ruff check src/mcp_memoria     # Linting

# Build Docker images locally
docker build -t mcp-memoria -f docker/Dockerfile .
docker build -t memoria-ui -f docker/Dockerfile.ui .
```

-----

## Contributing

Contributions are welcome! Please read CONTRIBUTING.md before opening a PR.

- **Found a bug?** Open an [Issue](https://github.com/trapias/memoria/issues)
- **Have an idea?** Start a [Discussion](https://github.com/trapias/memoria/discussions)
- **Like the project?** A star on GitHub goes a long way!

<a href="https://www.buymeacoffee.com/trapias" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;" ></a>

-----

## License

Distributed under the **Apache 2.0** license — free for personal and commercial use.

