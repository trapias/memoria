# MCP Memoria

**Unlimited local AI memory for Claude Code and Claude Desktop**

MCP Memoria is a Model Context Protocol (MCP) server that provides persistent, unlimited memory capabilities using **Qdrant** for vector storage and **Ollama** for local embeddings. Zero cloud dependencies, zero storage limits, 100% privacy.

## Features

- **Unlimited Storage**: No 50MB limits like cloud services
- **100% Local**: All data stays on your machine
- **Three Memory Types**:
  - **Episodic**: Events, conversations, time-bound memories
  - **Semantic**: Facts, knowledge, concepts
  - **Procedural**: Procedures, workflows, learned skills
- **Semantic Search**: Find relevant memories by meaning, not just keywords
- **Memory Consolidation**: Automatic merging of similar memories
- **Forgetting Curve**: Natural decay of unused, low-importance memories
- **Export/Import**: Backup and share your memories

## Quick Start

### Prerequisites

- Python 3.11+
- [Ollama](https://ollama.com/download) with `nomic-embed-text` model
- (Optional) Docker for Qdrant containerized deployment

### Installation

#### Option A: Automated (Recommended)

```bash
# Clone the repository
git clone https://github.com/yourusername/mcp-memoria.git
cd mcp-memoria

# Run installation script (installs Ollama, model, and dependencies)
./scripts/install.sh
```

#### Option B: Manual Installation

```bash
# 1. Install Ollama (skip if already installed)
# macOS
brew install ollama

# Linux
curl -fsSL https://ollama.com/install.sh | sh

# 2. Start Ollama and pull the embedding model
ollama serve  # Run in background or separate terminal
ollama pull nomic-embed-text

# 3. Install MCP Memoria
git clone https://github.com/yourusername/mcp-memoria.git
cd mcp-memoria
pip install -e .

# 4. Start Qdrant (choose one option)

# Option 4a: Using Docker (recommended)
cd docker
docker-compose -f docker-compose.qdrant-only.yml up -d

# Option 4b: Local storage (no Docker needed)
# Just configure MEMORIA_QDRANT_PATH in Claude config
```

### Configure Claude Code

#### Option 1: Using CLI (Recommended)

```bash
# Add MCP server at user level (available for all projects)
claude mcp add --scope user memoria \
  -e MEMORIA_QDRANT_HOST=localhost \
  -e MEMORIA_QDRANT_PORT=6333 \
  -e MEMORIA_OLLAMA_HOST=http://localhost:11434 \
  -- python -m mcp_memoria

# Or for project-level only
claude mcp add memoria -- python -m mcp_memoria
```

#### Option 2: Manual Configuration

Add to `~/.claude/config.json`:

```json
{
  "mcp_servers": {
    "memoria": {
      "command": "python",
      "args": ["-m", "mcp_memoria"],
      "env": {
        "MEMORIA_QDRANT_PATH": "~/.mcp-memoria/qdrant",
        "MEMORIA_OLLAMA_HOST": "http://localhost:11434",
        "MEMORIA_EMBEDDING_MODEL": "nomic-embed-text"
      }
    }
  }
}
```

### Configure Claude Desktop

Add to your Claude Desktop config:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "memoria": {
      "command": "python",
      "args": ["-m", "mcp_memoria"],
      "env": {
        "MEMORIA_QDRANT_PATH": "/path/to/qdrant/storage",
        "MEMORIA_OLLAMA_HOST": "http://localhost:11434"
      }
    }
  }
}
```

## Usage

Once configured, Claude will have access to memory tools. You can interact naturally - Claude will automatically use the appropriate memory tools based on your requests.

### Verify Installation

Before using Memoria, ensure the services are running:

```bash
# 1. Check Qdrant is running
curl http://localhost:6333/healthz

# 2. Check Ollama is running and has the model
ollama list | grep nomic-embed-text

# 3. Start Claude in any project directory
cd /path/to/your/project
claude
```

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

| Tool | Description |
|------|-------------|
| `memoria_store` | Store new memories |
| `memoria_recall` | Recall memories by semantic similarity |
| `memoria_search` | Advanced search with filters |
| `memoria_update` | Update existing memories |
| `memoria_delete` | Delete memories |
| `memoria_consolidate` | Merge similar memories |
| `memoria_export` | Export memories to file |
| `memoria_import` | Import memories from file |
| `memoria_stats` | View system statistics |
| `memoria_set_context` | Set current project/file context |

### Example Interactions

#### Storing Different Memory Types

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

#### Recalling Memories

```
# Semantic search - finds relevant memories by meaning
What do you know about the database?
How do we handle authentication?

# With filters
Search memories about deployment from last week
Find all procedural memories about testing
```

#### Project Context

Set context to associate memories with a specific project:

```
Set the project context to "ecommerce-api"
Now remember that this project uses Stripe for payments
```

Later, when working on the same project:
```
What do you remember about the ecommerce-api project?
```

#### Memory Management

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

### Tips for Effective Use

1. **Be specific**: "Remember the PostgreSQL connection string is postgres://..." is better than "Remember the database info"

2. **Use context**: Set project context when working on specific projects to keep memories organized

3. **Regular consolidation**: Run consolidation periodically to merge similar memories and reduce redundancy

4. **Importance levels**: Mention importance for critical information: "This is important: never delete the production database"

5. **Natural language**: You don't need special syntax - just talk naturally about what you want to remember or recall

## Docker Deployment

### Recommended Setup: Dockerized Memoria with Persistent Qdrant

This setup runs Qdrant persistently via docker-compose, while each Claude Code session spawns its own ephemeral Memoria container. This provides:

- **Persistent storage**: Qdrant keeps all memories across sessions
- **Clean sessions**: Each Claude instance gets a fresh Memoria container (removed on exit)
- **Native GPU**: Ollama runs on your Mac with Metal acceleration

#### Step 1: Start Qdrant (one-time setup)

```bash
cd docker
docker-compose -f docker-compose.qdrant-only.yml up -d
```

This creates:
- `memoria-qdrant` container (persistent)
- `memoria-network` Docker network
- `qdrant_data` volume for persistent storage

#### Step 2: Build the Memoria Image

```bash
cd docker
docker build -t docker-memoria .
```

#### Step 3: Configure Claude Code

Add to your Claude Code MCP configuration (`~/.claude.json` or project settings):

```json
{
  "mcpServers": {
    "memoria": {
      "type": "stdio",
      "command": "docker",
      "args": [
        "run",
        "--rm",
        "-i",
        "--network", "memoria-network",
        "-e", "MEMORIA_QDRANT_HOST=memoria-qdrant",
        "-e", "MEMORIA_QDRANT_PORT=6333",
        "-e", "MEMORIA_OLLAMA_HOST=http://host.docker.internal:11434",
        "-e", "MEMORIA_LOG_LEVEL=WARNING",
        "docker-memoria"
      ]
    }
  }
}
```

**Flags explained**:
- `--rm`: Remove container when Claude session ends
- `-i`: Interactive mode for MCP stdio communication
- `--network memoria-network`: Connect to Qdrant's network

#### Environment Variables

| Variable | Value | Why |
|----------|-------|-----|
| `MEMORIA_QDRANT_HOST` | `memoria-qdrant` | Container name on Docker network (NOT `localhost`) |
| `MEMORIA_QDRANT_PORT` | `6333` | Qdrant's default port |
| `MEMORIA_OLLAMA_HOST` | `http://host.docker.internal:11434` | Special Docker DNS to reach host's native Ollama |

> **Note**: Inside a Docker container, `localhost` refers to the container itself. Use container names for inter-container communication on the same Docker network.

#### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Your Mac/Host                         │
│                                                          │
│  ┌─────────────┐                                        │
│  │   Ollama    │◀─── host.docker.internal:11434         │
│  │  (native)   │     (Metal GPU acceleration)           │
│  └─────────────┘                                        │
│                                                          │
│  ┌────────────────── memoria-network ─────────────────┐ │
│  │                                                     │ │
│  │  ┌──────────────────┐    ┌──────────────────────┐  │ │
│  │  │  docker-memoria  │───▶│    memoria-qdrant    │  │ │
│  │  │   (ephemeral)    │    │    (persistent)      │  │ │
│  │  │   per session    │    │    via compose       │  │ │
│  │  └──────────────────┘    └──────────────────────┘  │ │
│  │           │                       │                │ │
│  └───────────┼───────────────────────┼────────────────┘ │
│              │                       │                  │
│              ▼                       ▼                  │
│     host.docker.internal      qdrant_data volume       │
│                                (persistent)             │
└─────────────────────────────────────────────────────────┘
```

#### Managing the Setup

```bash
# Check Qdrant status
docker-compose -f docker-compose.qdrant-only.yml ps

# View Qdrant logs
docker-compose -f docker-compose.qdrant-only.yml logs -f

# Stop Qdrant (memories preserved in volume)
docker-compose -f docker-compose.qdrant-only.yml down

# Reset all memories (destructive!)
docker-compose -f docker-compose.qdrant-only.yml down -v
```

### macOS (with native Ollama)

If you have Ollama installed natively on your Mac (recommended for Metal GPU acceleration):

```bash
# 1. Ensure Ollama is running
ollama serve

# 2. Pull the embedding model
ollama pull nomic-embed-text

# 3. Start containers (Qdrant + Memoria only)
cd docker
docker-compose -f docker-compose.mac.yml up -d

# 4. Check status
docker-compose -f docker-compose.mac.yml ps

# 5. Stop
docker-compose -f docker-compose.mac.yml down
```

This starts:
- Qdrant vector database (containerized)
- MCP Memoria server (containerized, connects to host Ollama)

### Full Stack (Linux/GPU)

For a fully containerized setup with Ollama included:

```bash
# With GPU support (NVIDIA)
cd docker
docker-compose up -d

# CPU only
docker-compose -f docker-compose.cpu.yml up -d
```

This starts:
- Qdrant vector database
- Ollama with embedding models
- MCP Memoria server

## Multi-Node Sync

If you run Qdrant on multiple machines (e.g., a Mac and a Linux server), you can keep them synchronized using the included sync script.

### How It Works

The sync script (`scripts/sync_qdrant.py`) performs **incremental bidirectional synchronization**:

- **New memories**: Copied to the other node
- **Updated memories**: Newer timestamp wins
- **Deleted memories**: Propagated to the other node

The script tracks the last sync timestamp in `~/.mcp-memoria/sync_state.json` to determine what's new vs. what's been deleted.

### Configuration

Edit the script to set your node addresses:

```python
LOCAL_URL = "http://localhost:6333"
REMOTE_URL = "http://your-server.local:6333"  # Your remote hostname
REMOTE_IP = "192.168.1.51"                    # Fallback IP if hostname doesn't resolve
```

### Usage

```bash
# Run sync
python scripts/sync_qdrant.py

# Dry run (show what would happen)
python scripts/sync_qdrant.py --dry-run

# Verbose output
python scripts/sync_qdrant.py -v

# Reset sync state (treat all as new, no deletions)
python scripts/sync_qdrant.py --reset-state
```

### Scheduling

You can schedule the sync using cron or launchd:

**macOS (launchd)**:
```xml
<!-- ~/Library/LaunchAgents/com.memoria.sync.plist -->
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.memoria.sync</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/path/to/scripts/sync_qdrant.py</string>
    </array>
    <key>StartInterval</key>
    <integer>300</integer> <!-- Every 5 minutes -->
</dict>
</plist>
```

**Linux (cron)**:
```bash
# Every 5 minutes
*/5 * * * * /usr/bin/python3 /path/to/scripts/sync_qdrant.py >> ~/.mcp-memoria/sync.log 2>&1
```

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `MEMORIA_QDRANT_PATH` | `~/.mcp-memoria/qdrant` | Qdrant storage path |
| `MEMORIA_QDRANT_HOST` | - | Qdrant server host (for server mode) |
| `MEMORIA_OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |
| `MEMORIA_EMBEDDING_MODEL` | `nomic-embed-text` | Embedding model |
| `MEMORIA_CACHE_ENABLED` | `true` | Enable embedding cache |
| `MEMORIA_LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `MEMORIA_LOG_FILE` | - | Path to log file (logs to file in addition to stderr) |

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

## Architecture

```
┌─────────────────────────────────────┐
│         Claude Code/Desktop          │
└───────────────┬─────────────────────┘
                │ MCP Protocol
                ▼
┌─────────────────────────────────────┐
│         MCP Memoria Server           │
├─────────────────────────────────────┤
│  Tools: store, recall, search, etc.  │
├─────────────────────────────────────┤
│          Memory Manager              │
│  ┌─────────┐ ┌─────────┐ ┌────────┐ │
│  │Episodic │ │Semantic │ │Procedur│ │
│  └─────────┘ └─────────┘ └────────┘ │
├─────────────────────────────────────┤
│  Ollama (embeddings) │ Qdrant (vectors)│
└─────────────────────────────────────┘
```

## Troubleshooting

### Common Issues

#### "Failed to connect" when starting Claude

1. **Check Qdrant is running**:
   ```bash
   curl http://localhost:6333/healthz
   # Should return: healthz check passed
   ```

2. **Check Ollama is running**:
   ```bash
   curl http://localhost:11434/api/tags
   # Should return list of models
   ```

3. **Verify the embedding model is installed**:
   ```bash
   ollama pull nomic-embed-text
   ```

#### "Connection refused" errors

- Ensure Qdrant is accessible on port 6333
- For Docker setups, verify the network configuration
- Check firewall settings if running on remote servers

#### Memories not being found

- Run `memoria_stats` to verify memories are being stored
- Check that the embedding model is working: memories require embeddings for semantic search
- Try consolidating memories if you have many similar entries

#### Slow performance

- The first query may be slow as models are loaded into memory
- Ensure Ollama is using GPU acceleration if available
- Consider using a smaller embedding model for faster results

### Debug Mode

Enable debug logging for more information:

```bash
# Set environment variable before starting
export MEMORIA_LOG_LEVEL=DEBUG
```

Or in Claude config:
```json
{
  "env": {
    "MEMORIA_LOG_LEVEL": "DEBUG"
  }
}
```

### File Logging

By default, Memoria logs to stderr (required for MCP protocol). You can additionally log to a file for persistent debugging or auditing:

```bash
# Log to a specific file
export MEMORIA_LOG_FILE=~/.mcp-memoria/logs/memoria.log
```

Or in Claude config:
```json
{
  "env": {
    "MEMORIA_LOG_FILE": "/Users/yourname/.mcp-memoria/logs/memoria.log"
  }
}
```

**Notes:**
- The log directory will be created automatically if it doesn't exist
- File logging is **in addition to** stderr logging (both outputs are active)
- Useful for debugging issues that occur during Claude sessions
- Combine with `MEMORIA_LOG_LEVEL=DEBUG` for detailed diagnostics

**Example: Full debug configuration**
```json
{
  "mcpServers": {
    "memoria": {
      "command": "python",
      "args": ["-m", "mcp_memoria"],
      "env": {
        "MEMORIA_QDRANT_HOST": "localhost",
        "MEMORIA_LOG_LEVEL": "DEBUG",
        "MEMORIA_LOG_FILE": "/Users/yourname/.mcp-memoria/logs/memoria.log"
      }
    }
  }
}
```

### Reset All Data

To completely reset Memoria and start fresh:

```bash
# If using local Qdrant storage
rm -rf ~/.mcp-memoria/qdrant

# If using Docker Qdrant
docker-compose -f docker-compose.qdrant-only.yml down -v
docker-compose -f docker-compose.qdrant-only.yml up -d
```

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Type checking
mypy src/mcp_memoria

# Linting
ruff check src/mcp_memoria
```

## Comparison

| Feature | MCP Memoria | Memvid | Mem0 |
|---------|-------------|--------|------|
| Storage Limit | Unlimited | 50MB free | Varies |
| Local-only | Yes | Partial | No |
| MCP Native | Yes | No | No |
| Cost | Free | Freemium | Freemium |
| Vector DB | Qdrant | Custom | Cloud |

## License

Apache 2.0

## Contributing

Contributions welcome! Please read CONTRIBUTING.md first.
