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
- [Ollama](https://ollama.com/download)
- (Optional) Docker for containerized deployment

### Installation

```bash
# Clone the repository
cd /home/alberto/dev/Memoria

# Run installation script
./scripts/install.sh
```

Or manually:

```bash
# Install Ollama and pull embedding model
curl -fsSL https://ollama.com/install.sh | sh
ollama pull nomic-embed-text

# Install MCP Memoria
pip install -e .
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

Once configured, Claude will have access to these tools:

### Store Memories

```
Store this fact: The project uses FastAPI with PostgreSQL
```

Claude will use `memoria_store` to save this as a semantic memory.

### Recall Memories

```
What database does this project use?
```

Claude will use `memoria_recall` to find relevant memories.

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

## Docker Deployment

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

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `MEMORIA_QDRANT_PATH` | `~/.mcp-memoria/qdrant` | Qdrant storage path |
| `MEMORIA_QDRANT_HOST` | - | Qdrant server host (for server mode) |
| `MEMORIA_OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |
| `MEMORIA_EMBEDDING_MODEL` | `nomic-embed-text` | Embedding model |
| `MEMORIA_CACHE_ENABLED` | `true` | Enable embedding cache |
| `MEMORIA_LOG_LEVEL` | `INFO` | Logging level |

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
