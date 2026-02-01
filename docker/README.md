# Memoria Docker Configuration

Complete Docker setup for MCP Memoria with multiple deployment scenarios.

## Available Configurations

### 1. `docker-compose.central.yml` - Dual-Database (Recommended)

**Best for:** Production, persistent storage, web UI, advanced features

- **Qdrant** (port 6333/6334): Vector database for semantic search
- **PostgreSQL** (port 5432): Relational database for work sessions, clients, projects, and knowledge graph
- **Optional:** Memoria MCP server with HTTP/SSE transport (port 8765) - ⚠️ for testing only, not multi-client production

**Start:**
```bash
cd docker

# Basic start (Qdrant + PostgreSQL)
docker-compose -f docker-compose.central.yml up -d

# With custom PostgreSQL password
POSTGRES_PASSWORD=your_secure_password docker-compose -f docker-compose.central.yml up -d

# Stop
docker-compose -f docker-compose.central.yml down

# View logs
docker-compose -f docker-compose.central.yml logs -f postgres
docker-compose -f docker-compose.central.yml logs -f qdrant
```

**Connection Strings (from within Docker network):**
- Qdrant: `http://qdrant:6333`
- PostgreSQL: `postgresql://memoria:memoria_dev@postgres:5432/memoria`

**Default Credentials:**
- PostgreSQL user: `memoria`
- PostgreSQL password: `memoria_dev` (set via `POSTGRES_PASSWORD` env var)
- PostgreSQL database: `memoria`

**Features:**
- Persistent vector storage with automatic initialization
- PostgreSQL schema with work sessions, clients, projects, and memory relations
- Health checks for both services
- Named volumes for data persistence
- Optional Memoria HTTP server for direct MCP connections

### 2. `docker-compose.http.yml` - HTTP/SSE Transport Only

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

**Best for:** Development and testing only

- **Qdrant** (port 6333/6334): Vector database
- **Memoria** (port 8765): HTTP/SSE server for Claude Code integration

**Start:**
```bash
cd docker
docker-compose -f docker-compose.http.yml up -d
```

**Claude Code Configuration** (`~/.claude/config.json`):
```json
{
  "mcp_servers": {
    "memoria": {
      "url": "http://localhost:8765/sse"
    }
  }
}
```

**Features:**
- Lightweight, easy to start
- No PostgreSQL dependency
- Direct HTTP/SSE connection to Memoria server
- **Single-user only** - not suitable for multi-client production

### 3. `docker-compose.qdrant-only.yml` - Qdrant Only

**Best for:** Minimal setup, testing, local MCP server

- **Qdrant** (port 6333/6334): Vector database only

**Start:**
```bash
cd docker
docker-compose -f docker-compose.qdrant-only.yml up -d
```

**Features:**
- Bare minimum setup
- Works with local `python -m mcp_memoria` server
- No network services needed

---

## Database Initialization

The `init-db.sql` script is automatically executed when PostgreSQL starts for the first time.

### What it creates:

**Enums:**
- `session_category` - Work session types (coding, review, meeting, etc.)
- `session_status` - Session state (active, paused, completed)
- `relation_type` - Memory relations (causes, fixes, supports, opposes, etc.)
- `relation_creator` - Who created a relation (user, auto, system)

**Tables:**
- `clients` - Client/company entries
- `projects` - Projects associated with clients
- `work_sessions` - Time-tracked work sessions
- `memory_relations` - Knowledge graph connections between memories
- `user_settings` - Configuration key-value store

**Indexes:**
- Optimized for common queries on time ranges, clients, projects, statuses
- Partial indexes for active sessions
- Composite indexes for efficient filtering

**Functions:**
- `get_neighbors()` - Find related memories up to N hops
- `find_path()` - Shortest path between two memories
- `refresh_work_views()` - Refresh reporting materialized views
- `update_updated_at_column()` - Auto-update timestamps

**Materialized Views:**
- `monthly_work_summary` - Monthly aggregated work statistics
- `daily_work_totals` - Daily work summaries for timeline charts

**Triggers:**
- Auto-update `updated_at` timestamps on data changes

### Custom Initialization

To add custom initialization logic:

1. Create a new SQL file in the docker directory (e.g., `init-db-custom.sql`)
2. Update `docker-compose.central.yml` to mount it:

```yaml
postgres:
  volumes:
    - ./init-db.sql:/docker-entrypoint-initdb.d/01-init.sql:ro
    - ./init-db-custom.sql:/docker-entrypoint-initdb.d/02-custom.sql:ro
```

---

## Persistence & Volumes

### Named Volumes (Recommended)

All configurations use named volumes for data persistence:

- `memoria-qdrant-data` - Qdrant vector storage
- `memoria-postgres-data` - PostgreSQL data directory
- `memoria_cache` - Memoria server cache (HTTP mode)
- `qdrant_data` - Qdrant data (HTTP mode)

**View volumes:**
```bash
docker volume ls | grep memoria
```

**Inspect volume:**
```bash
docker volume inspect memoria-qdrant-data
```

**Backup volumes:**
```bash
# Backup Qdrant data
docker run --rm -v memoria-qdrant-data:/data \
  -v $(pwd)/backups:/backup \
  alpine tar czf /backup/qdrant-backup.tar.gz -C /data .

# Backup PostgreSQL data
docker run --rm -v memoria-postgres-data:/data \
  -v $(pwd)/backups:/backup \
  alpine tar czf /backup/postgres-backup.tar.gz -C /data .
```

**Restore volumes:**
```bash
# Stop containers first
docker-compose -f docker-compose.central.yml stop

# Restore Qdrant
docker run --rm -v memoria-qdrant-data:/data \
  -v $(pwd)/backups:/backup \
  alpine tar xzf /backup/qdrant-backup.tar.gz -C /data

# Restore PostgreSQL
docker run --rm -v memoria-postgres-data:/data \
  -v $(pwd)/backups:/backup \
  alpine tar xzf /backup/postgres-backup.tar.gz -C /data

# Restart containers
docker-compose -f docker-compose.central.yml up -d
```

---

## Health Checks

All services include health checks:

```bash
# View health status
docker-compose -f docker-compose.central.yml ps

# Check specific service
docker ps --format "table {{.Names}}\t{{.Status}}" | grep memoria
```

**Qdrant health check:**
```bash
curl http://localhost:6333/health
# Expected response: {"title":"Qdrant","version":"...","status":"ok"}
```

**PostgreSQL health check:**
```bash
docker exec memoria-postgres pg_isready -U memoria
# Expected response: accepting connections
```

**Memoria HTTP health check (if enabled):**
```bash
curl http://localhost:8765/health
```

---

## Environment Variables

### PostgreSQL

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_PASSWORD` | `memoria_dev` | Database password (change for production) |
| `POSTGRES_USER` | `memoria` | Database user |
| `POSTGRES_DB` | `memoria` | Database name |

Example:
```bash
POSTGRES_PASSWORD=super_secret_2024 docker-compose -f docker-compose.central.yml up -d
```

### Qdrant (Optional)

| Variable | Default | Description |
| `QDRANT_API_KEY` | (none) | Enable API key authentication |

To enable Qdrant API key, uncomment in `docker-compose.central.yml`:
```yaml
environment:
  - QDRANT__API_KEY=${QDRANT_API_KEY}
```

Then set before starting:
```bash
QDRANT_API_KEY=your_secret_key docker-compose -f docker-compose.central.yml up -d
```

### Memoria Server (HTTP mode, if enabled)

| Variable | Default | Description |
| `MEMORIA_HTTP_PORT` | `8765` | HTTP server port |
| `MEMORIA_HTTP_HOST` | `0.0.0.0` | HTTP host to bind to |
| `MEMORIA_QDRANT_HOST` | `qdrant` | Qdrant hostname |
| `MEMORIA_QDRANT_PORT` | `6333` | Qdrant port |
| `MEMORIA_OLLAMA_HOST` | `http://host.docker.internal:11434` | Ollama server URL |
| `MEMORIA_LOG_LEVEL` | `INFO` | Logging level |

---

## Networking

### Service-to-Service Communication

Services communicate via Docker networks:

- `docker-compose.central.yml`: Uses `memoria-central` network
- `docker-compose.http.yml`: Uses `memoria-http-network` network

**Access from container:**
```bash
# Inside memoria container
curl http://qdrant:6333/health
psql -h postgres -U memoria -d memoria
```

### Port Mapping

| Service | Internal | External | Purpose |
|---------|----------|----------|---------|
| Qdrant REST | 6333 | 6333 | Vector database API |
| Qdrant gRPC | 6334 | 6334 | High-performance gRPC |
| PostgreSQL | 5432 | 5432 | SQL database |
| Memoria HTTP | 8765 | 8765 | SSE transport |

### Accessing from Host

```bash
# Connect to Qdrant
curl http://localhost:6333/health

# Connect to PostgreSQL
psql -h localhost -U memoria -d memoria

# Connect to Memoria HTTP
curl http://localhost:8765/health
```

---

## Performance Tuning

### PostgreSQL

The default init script includes connection pooling and memory settings:

```sql
POSTGRES_INITDB_ARGS="-c shared_buffers=256MB -c max_connections=100"
```

For production, adjust in `docker-compose.central.yml`:

```yaml
environment:
  POSTGRES_INITDB_ARGS: "-c shared_buffers=1GB -c max_connections=200 -c work_mem=10MB"
```

### Qdrant

Qdrant uses default settings. For large deployments, add environment variables:

```yaml
qdrant:
  environment:
    - QDRANT__STORAGE__SNAPSHOTS_PATH=/qdrant/snapshots
    - QDRANT__LOG_LEVEL=INFO
```

---

## Troubleshooting

### Qdrant not starting

```bash
# Check logs
docker-compose -f docker-compose.central.yml logs qdrant

# Check health
curl -i http://localhost:6333/health

# Verify volume is writable
docker run --rm -v memoria-qdrant-data:/data alpine touch /data/test && echo "OK"
```

### PostgreSQL connection refused

```bash
# Check service is running
docker ps | grep memoria-postgres

# View logs
docker-compose -f docker-compose.central.yml logs postgres

# Test connection
docker exec memoria-postgres psql -U memoria -d memoria -c "SELECT 1"
```

### Permission denied on volumes

```bash
# Fix volume permissions
docker run --rm -v memoria-postgres-data:/data \
  -v memoria-qdrant-data:/qdrant \
  alpine sh -c "chown -R 70:70 /data && chown -R 1000:1000 /qdrant"
```

### Network connectivity issues

```bash
# Check network exists
docker network ls | grep memoria

# Inspect network
docker network inspect memoria-central

# Test container-to-container connectivity
docker exec memoria-postgres ping qdrant
docker exec memoria-qdrant ping postgres
```

---

## Migration from Qdrant-only to Central Architecture

If you're currently using `docker-compose.qdrant-only.yml`:

1. **Backup existing data:**
   ```bash
   docker run --rm -v qdrant_data:/data \
     -v $(pwd)/backups:/backup \
     alpine tar czf /backup/qdrant-old.tar.gz -C /data .
   ```

2. **Stop old services:**
   ```bash
   docker-compose -f docker-compose.qdrant-only.yml down
   ```

3. **Start new services:**
   ```bash
   docker-compose -f docker-compose.central.yml up -d
   ```

4. **Restore Qdrant data (optional, if keeping old memories):**
   ```bash
   # Copy old data to new volume
   docker run --rm -v qdrant_data:/old_data \
     -v memoria-qdrant-data:/new_data \
     alpine cp -r /old_data/* /new_data/
   ```

5. **Test connectivity:**
   ```bash
   docker exec memoria-postgres pg_isready -U memoria
   curl http://localhost:6333/health
   ```

---

## Production Deployment

For production deployments:

### Security

1. **Change default passwords:**
   ```bash
   POSTGRES_PASSWORD=$(openssl rand -base64 32) docker-compose -f docker-compose.central.yml up -d
   ```

2. **Enable Qdrant API key:**
   ```bash
   QDRANT_API_KEY=$(openssl rand -base64 32) docker-compose -f docker-compose.central.yml up -d
   ```

3. **Restrict network access:**
   - Only expose services to internal networks if possible
   - Use firewall rules for external access
   - Consider using reverse proxy (nginx) for HTTPS termination

### Backups

Set up automated backups:

```bash
#!/bin/bash
# backup-memoria.sh

BACKUP_DIR="/backups/memoria"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

# Backup PostgreSQL
docker exec memoria-postgres pg_dump -U memoria -d memoria \
  | gzip > "$BACKUP_DIR/postgres_$TIMESTAMP.sql.gz"

# Backup Qdrant
docker run --rm -v memoria-qdrant-data:/data \
  -v "$BACKUP_DIR":/backup \
  alpine tar czf "/backup/qdrant_$TIMESTAMP.tar.gz" -C /data .

# Keep last 30 days
find "$BACKUP_DIR" -name "*.gz" -mtime +30 -delete
```

### Monitoring

Monitor container health:

```bash
docker-compose -f docker-compose.central.yml ps
docker stats
```

Set up alerts for:
- Service failures (health checks)
- Disk space usage
- Memory usage
- Database connection count

---

## Quick Reference

| Task | Command |
|------|---------|
| Start all services | `docker-compose -f docker-compose.central.yml up -d` |
| Stop all services | `docker-compose -f docker-compose.central.yml down` |
| View logs | `docker-compose -f docker-compose.central.yml logs -f` |
| Open PostgreSQL shell | `docker exec -it memoria-postgres psql -U memoria -d memoria` |
| Check service status | `docker-compose -f docker-compose.central.yml ps` |
| Remove all data | `docker-compose -f docker-compose.central.yml down -v` |
| Restart a service | `docker-compose -f docker-compose.central.yml restart postgres` |
