# Memoria Docker Architecture

Complete documentation of the dual-database Docker setup for Memoria.

## Overview

Memoria now supports multiple deployment scenarios with an emphasis on the **dual-database architecture** (Qdrant + PostgreSQL) for production deployments with advanced features like work tracking, knowledge graphs, and web UI.

### Key Components

- **Qdrant** (Vector Database): Fast semantic search and embeddings storage
- **PostgreSQL** (Relational Database): Work sessions, clients, projects, memory relations, and analytics
- **Memoria MCP Server** (Optional): HTTP/SSE transport layer for Claude Code integration
- **Ollama** (External): Local embedding generation

---

## Deployment Scenarios

### 1. Central Architecture (Production-Ready)

**File:** `docker-compose.central.yml`

**Components:**
- Qdrant (vector store)
- PostgreSQL (relational store)
- Optional: Memoria HTTP/SSE server (⚠️ testing only - see warning above)

**Use Cases:**
- Production deployments
- Multi-user environments (each with local stdio Memoria process)
- Persistent data with advanced features
- Web UI integration (future)
- Work tracking and analytics

**Start:**
```bash
docker-compose -f docker-compose.central.yml up -d
```

**Architecture Diagram:**
```
┌─────────────────────────────────────────────────────────┐
│         Docker Compose (Central)                        │
│                                                         │
│  ┌──────────────┐      ┌─────────────────┐            │
│  │    Qdrant    │      │   PostgreSQL    │            │
│  │  :6333/6334  │      │     :5432       │            │
│  │   (vectors)  │      │  (relational)   │            │
│  └──────┬───────┘      └────────┬────────┘            │
│         │                       │                      │
│         └───────────┬───────────┘                      │
│                     │                                   │
│        ┌────────────▼─────────────┐                    │
│        │  Memoria HTTP Server     │                    │
│        │     (optional)           │                    │
│        │        :8765             │                    │
│        └────────────┬─────────────┘                    │
│                     │                                   │
└─────────────────────┼───────────────────────────────────┘
                      │
          ┌───────────┴───────────┐
          │                       │
    Client Devices       Ollama (host:11434)
```

### 2. HTTP/SSE Transport (Development/Testing Only)

> ⚠️ **WARNING: FOR TESTING/DEVELOPMENT ONLY**
>
> A shared HTTP server is **NOT recommended** for multi-client production use.
>
> **Problems with shared HTTP server:**
> - WorkingMemory is shared across ALL sessions
> - Risk of context confusion between different users
> - No session isolation
>
> **Use only for:** local testing, single-user scenarios, demos/proof-of-concept.
>
> **For production:** Each Claude Code instance should have its own local Memoria process (stdio transport) connecting to shared databases.

**File:** `docker-compose.http.yml`

**Components:**
- Qdrant (vector store)
- Memoria HTTP/SSE server (MCP transport)

**Use Cases:**
- Development and testing only
- Single-user lightweight deployments
- Demos and proof-of-concept
- **NOT for multi-client production**

**Start:**
```bash
docker-compose -f docker-compose.http.yml up -d
```

### 3. Qdrant Only (Minimal)

**File:** `docker-compose.qdrant-only.yml`

**Components:**
- Qdrant (vector store)

**Use Cases:**
- Testing
- Local MCP server with `python -m mcp_memoria`
- CI/CD pipelines
- Minimal resource requirements

**Start:**
```bash
docker-compose -f docker-compose.qdrant-only.yml up -d
```

---

## Database Design

### PostgreSQL Schema

#### Clients & Projects
```sql
clients (id, name, metadata, created_at, updated_at)
projects (id, client_id, name, repo, metadata, created_at, updated_at)
```

Purpose: Organizational structure for tracking work sessions.

#### Work Sessions
```sql
work_sessions (
    id, description, category, client_id, project_id,
    issue_number, pr_number, branch,
    start_time, end_time, duration_minutes,
    pauses, total_pause_minutes, status,
    notes, memory_id,
    created_at, updated_at
)
```

Purpose: Time-tracked work activities with rich context.

Features:
- Automatic duration calculation (excluding pauses)
- JSONB pause tracking with timestamps and reasons
- Optional memory link to Qdrant episodic memories
- Status tracking (active, paused, completed)
- Category classification (coding, review, meeting, etc.)

#### Memory Relations (Knowledge Graph)
```sql
memory_relations (
    id, source_id, target_id,
    relation_type, weight,
    created_by, metadata,
    created_at
)
```

Purpose: Create knowledge graph connections between memories.

Relation Types:
- `causes` - A leads to B
- `fixes` - A resolves B
- `supports` - A confirms B
- `opposes` - A contradicts B
- `follows` - A comes after B
- `supersedes` - A replaces B
- `derives` - A is derived from B
- `part_of` - A is component of B
- `related` - Generic connection

#### Materialized Views
```sql
monthly_work_summary
daily_work_totals
```

Purpose: Pre-computed aggregations for reporting and dashboards.

### Qdrant Collections

**Unchanged from Memoria core:**
- `episodic` - Events, conversations, time-bound memories
- `semantic` - Facts, knowledge, concepts
- `procedural` - Procedures, workflows, learned skills

Each memory is indexed by Qdrant point ID (UUID) and can be referenced from PostgreSQL via `memory_relations.source_id` and `memory_relations.target_id`.

---

## Data Flow

### Storing a Memory (Qdrant)
```
Content → TextChunker → OllamaEmbedder → Qdrant Vector Storage
```

### Creating a Work Session (PostgreSQL)
```
Session Data → Database INSERT → Auto-calculated Fields → Stored in PostgreSQL
```

### Creating a Memory Relation (PostgreSQL + optional Qdrant)
```
Relation Definition → PostgreSQL INSERT → (Optional) Update Qdrant Payload
```

### Recalling Memories (Hybrid)
```
Query → Embed → Qdrant Vector Search → Filter by Relations (PostgreSQL) → Results
```

---

## Configuration

### Environment Variables

**PostgreSQL:**
```bash
POSTGRES_USER=memoria              # Database user
POSTGRES_PASSWORD=memoria_dev      # Database password (change in production!)
POSTGRES_DB=memoria               # Database name
POSTGRES_SHARED_BUFFERS=256MB     # Performance tuning
POSTGRES_MAX_CONNECTIONS=100      # Connection limit
```

**Qdrant (Optional):**
```bash
QDRANT_API_KEY=...                # Enable API key authentication
```

**Memoria HTTP (Optional):**
```bash
MEMORIA_HTTP_PORT=8765            # HTTP server port
MEMORIA_HTTP_HOST=0.0.0.0        # Bind address
MEMORIA_QDRANT_HOST=qdrant        # Internal Docker hostname
MEMORIA_QDRANT_PORT=6333          # Qdrant API port
MEMORIA_OLLAMA_HOST=http://host.docker.internal:11434
MEMORIA_EMBEDDING_MODEL=nomic-embed-text
MEMORIA_LOG_LEVEL=INFO
```

### Using .env File

```bash
# Copy template
cp docker/.env.example docker/.env

# Customize
nano docker/.env

# Load automatically
docker-compose -f docker-compose.central.yml up -d
```

---

## Quick Start

### Minimal Setup (Central Architecture)

```bash
# Navigate to docker directory
cd docker

# Start services
docker-compose -f docker-compose.central.yml up -d

# Verify health
docker-compose -f docker-compose.central.yml ps
```

**Services available:**
- Qdrant: http://localhost:6333
- PostgreSQL: postgresql://memoria:memoria_dev@localhost:5432/memoria

### With Environment Customization

```bash
# Set PostgreSQL password
POSTGRES_PASSWORD=your_secure_password \
  docker-compose -f docker-compose.central.yml up -d
```

### Using Quick Start Script

```bash
# Make script executable
chmod +x docker/start.sh

# Start central architecture
./docker/start.sh central

# Start HTTP transport
./docker/start.sh http

# Stop all services
./docker/start.sh stop

# View logs
./docker/start.sh logs central
```

---

## Database Initialization

The `init-db.sql` script is automatically executed on PostgreSQL container startup.

### What Gets Created

1. **Enums** (4)
   - `session_category` - Work session types
   - `session_status` - Session states
   - `relation_type` - Memory relation types
   - `relation_creator` - Relation source

2. **Tables** (5)
   - `clients` - Client/company entries
   - `projects` - Projects within clients
   - `work_sessions` - Time-tracked sessions
   - `memory_relations` - Knowledge graph edges
   - `user_settings` - Configuration key-value store

3. **Indexes** (18+)
   - Foreign key indexes
   - Time-range indexes
   - Composite indexes for common queries
   - Partial indexes for active sessions

4. **Functions** (4)
   - `get_neighbors(uuid, int, relation_type[])` - Find related memories
   - `find_path(uuid, uuid, int)` - Shortest path between memories
   - `refresh_work_views()` - Refresh materialized views
   - `update_updated_at_column()` - Auto-update timestamps

5. **Triggers** (4)
   - Auto-update `updated_at` on data changes

6. **Materialized Views** (2)
   - `monthly_work_summary` - Aggregated monthly statistics
   - `daily_work_totals` - Daily work summaries

### Custom Initialization

Add additional SQL files to run on startup:

```yaml
postgres:
  volumes:
    - ./init-db.sql:/docker-entrypoint-initdb.d/01-init.sql:ro
    - ./init-db-custom.sql:/docker-entrypoint-initdb.d/02-custom.sql:ro
```

Files in `/docker-entrypoint-initdb.d/` are executed in alphabetical order.

---

## Persistence

### Volumes

**Central Architecture:**
- `memoria-qdrant-data` - Qdrant vector storage
- `memoria-postgres-data` - PostgreSQL database files

**HTTP Transport:**
- `qdrant_data` - Qdrant vector storage
- `memoria_cache` - Memoria server cache

### Backups

```bash
# Backup Qdrant data
docker run --rm -v memoria-qdrant-data:/data \
  -v $(pwd)/backups:/backup \
  alpine tar czf /backup/qdrant-$(date +%s).tar.gz -C /data .

# Backup PostgreSQL database
docker exec memoria-postgres pg_dump -U memoria -d memoria \
  | gzip > ./backups/postgres-$(date +%s).sql.gz
```

### Restore

```bash
# Restore PostgreSQL
docker exec -i memoria-postgres psql -U memoria -d memoria \
  < ./backups/postgres-latest.sql

# Restore Qdrant
docker run --rm -v memoria-qdrant-data:/data \
  -v $(pwd)/backups:/backup \
  alpine tar xzf /backup/qdrant-latest.tar.gz -C /data
```

---

## Networking

### Service Discovery (Docker Network)

Services communicate via internal Docker network:

```bash
# From within container:
curl http://qdrant:6333/health
psql -h postgres -U memoria -d memoria
```

### Port Mapping

| Service | Internal | External | Purpose |
|---------|----------|----------|---------|
| Qdrant REST | 6333 | 6333 | Vector API |
| Qdrant gRPC | 6334 | 6334 | gRPC API |
| PostgreSQL | 5432 | 5432 | SQL Database |
| Memoria HTTP | 8765 | 8765 | SSE Transport |

### Accessing from Host

```bash
# From host machine:
curl http://localhost:6333/health
psql -h localhost -U memoria -d memoria
curl http://localhost:8765/health  # If HTTP service enabled
```

---

## Health Checks

### Qdrant

```bash
curl http://localhost:6333/health
# Response: {"title":"Qdrant","version":"...","status":"ok"}
```

### PostgreSQL

```bash
docker exec memoria-postgres pg_isready -U memoria
# Response: accepting connections
```

### Memoria HTTP

```bash
curl http://localhost:8765/health
# Response: {"status":"ok"}
```

### View Container Status

```bash
docker-compose -f docker-compose.central.yml ps
# STATUS column shows "healthy" if passing health checks
```

---

## Performance Tuning

### PostgreSQL Settings

Default configuration:
```sql
shared_buffers=256MB
max_connections=100
work_mem=10MB
```

For production, adjust based on:
- Available RAM
- Expected concurrent users
- Query complexity
- Data volume

```yaml
postgres:
  environment:
    POSTGRES_INITDB_ARGS: >
      -c shared_buffers=1GB
      -c max_connections=200
      -c work_mem=50MB
      -c maintenance_work_mem=256MB
```

### Qdrant Settings

Qdrant uses sensible defaults. For large deployments, add:

```yaml
qdrant:
  environment:
    - QDRANT__STORAGE__SNAPSHOT_PATH=/qdrant/snapshots
    - QDRANT__LOG_LEVEL=INFO
```

### Connection Pooling

For production, implement connection pooling (PgBouncer):

```yaml
pgbouncer:
  image: edoburu/pgbouncer:latest
  environment:
    DATABASES_HOST: postgres
    DATABASES_PORT: 5432
    DATABASES_USER: memoria
    DATABASES_PASSWORD: ${POSTGRES_PASSWORD}
    POOL_MODE: transaction
    MAX_CLIENT_CONN: 200
```

---

## Troubleshooting

### Qdrant Won't Start

```bash
# Check logs
docker-compose -f docker-compose.central.yml logs qdrant

# Check volume ownership
docker run --rm -v memoria-qdrant-data:/data \
  alpine ls -la /data

# Test connectivity
curl -i http://localhost:6333/health
```

### PostgreSQL Connection Issues

```bash
# Check logs
docker-compose -f docker-compose.central.yml logs postgres

# Test from host
psql -h localhost -U memoria -d memoria

# Test from container
docker exec memoria-postgres psql -U memoria -d memoria -c "SELECT 1"
```

### Data Corruption

```bash
# Backup current data
docker run --rm -v memoria-postgres-data:/data \
  -v $(pwd)/backups:/backup \
  alpine tar czf /backup/postgres-corrupted.tar.gz -C /data .

# Remove volume
docker volume rm memoria-postgres-data

# Restart container (will reinitialize)
docker-compose -f docker-compose.central.yml up -d postgres

# Check if healthy
docker-compose -f docker-compose.central.yml ps postgres
```

### Disk Space Issues

```bash
# Check volume size
docker volume inspect memoria-postgres-data

# Find large tables
docker exec memoria-postgres psql -U memoria -d memoria << EOF
SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
EOF

# Clean up old sessions
docker exec memoria-postgres psql -U memoria -d memoria << EOF
DELETE FROM work_sessions WHERE status = 'completed' AND created_at < NOW() - INTERVAL '1 year';
VACUUM ANALYZE;
EOF
```

---

## Migration from Single-Database

If upgrading from `docker-compose.http.yml` or `docker-compose.qdrant-only.yml`:

```bash
# 1. Backup existing Qdrant data
docker run --rm -v qdrant_data:/data \
  -v $(pwd)/backups:/backup \
  alpine tar czf /backup/qdrant-migration.tar.gz -C /data .

# 2. Stop old services
docker-compose -f docker-compose.http.yml down  # or qdrant-only
# Note: Don't use -v (keeps volumes)

# 3. Start new services
docker-compose -f docker-compose.central.yml up -d

# 4. Restore Qdrant data
docker run --rm -v memoria-qdrant-data:/data \
  -v $(pwd)/backups:/backup \
  alpine tar xzf /backup/qdrant-migration.tar.gz -C /data

# 5. Restart to apply
docker-compose -f docker-compose.central.yml restart qdrant
```

---

## Production Checklist

Before deploying to production:

- [ ] Change PostgreSQL password: `POSTGRES_PASSWORD=$(openssl rand -base64 32)`
- [ ] Enable Qdrant API key: `QDRANT_API_KEY=$(openssl rand -base64 32)`
- [ ] Set up automated backups (daily)
- [ ] Configure resource limits (CPU, memory)
- [ ] Enable monitoring and alerting
- [ ] Set up log aggregation
- [ ] Configure firewall rules
- [ ] Test disaster recovery procedure
- [ ] Document operational procedures
- [ ] Set up update strategy for Docker images
- [ ] Configure SSL/TLS for HTTP endpoints (via reverse proxy)
- [ ] Enable database query logging for debugging

---

## Next Steps

1. **Database Migrations**: When schema changes needed, create migration scripts in `migrations/` directory
2. **Web UI Integration**: Uncomment Memoria HTTP service in central config for future UI deployment
3. **GraphManager**: Implement Python class for knowledge graph operations
4. **MCP Tools**: Add memory relation tools to server
5. **Monitoring**: Set up Prometheus/Grafana for metrics
6. **Testing**: Create integration tests for dual-database setup

---

## References

- [Docker Compose Docs](https://docs.docker.com/compose/)
- [Qdrant Documentation](https://qdrant.tech/documentation/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Memoria Architecture](../docs/DATABASE_ARCHITECTURE.md)
- [UI & Work Tracking Plan](../docs/MEMORIA_UI_WORKTRACKING_PLAN.md)
