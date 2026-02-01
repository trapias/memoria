# Memoria Docker Setup Guide

Complete guide for setting up and running Memoria with the dual-database architecture.

## Quick Start (2 Minutes)

### Prerequisites
- Docker and Docker Compose installed
- Ollama running on your machine (http://localhost:11434)
- For Mac/Windows, Docker Desktop is recommended

### Step 1: Navigate to Docker Directory
```bash
cd /Users/alberto/Dev/Priv/Memoria/docker
```

### Step 2: Start Services
```bash
# Option A: Using docker-compose directly (central architecture - recommended)
docker-compose -f docker-compose.central.yml up -d

# Option B: Using quick start script
./start.sh central

# Option C: For HTTP/SSE transport only
./start.sh http
```

### Step 3: Verify Services are Running
```bash
docker-compose -f docker-compose.central.yml ps
```

Expected output:
```
NAME                 STATUS          PORTS
memoria-qdrant       Up (healthy)    6333-6334→6333-6334/tcp
memoria-postgres     Up (healthy)    5432→5432/tcp
```

### Step 4: Test Connectivity

**Test Qdrant:**
```bash
curl http://localhost:6333/health
# Expected: {"title":"Qdrant","version":"...","status":"ok"}
```

**Test PostgreSQL:**
```bash
psql -h localhost -U memoria -d memoria -c "SELECT version();"
# When prompted for password, enter: memoria_dev
```

### Step 5: Done!
Your Memoria infrastructure is ready.

---

## Deployment Options

### Option 1: Central Architecture (Production Recommended)

**Best for:** Production, work tracking, analytics, future web UI

**File:** `docker-compose.central.yml`

**Services:**
- Qdrant (vector database) on port 6333/6334
- PostgreSQL (relational database) on port 5432
- Optional: Memoria HTTP server on port 8765

**Features:**
- Persistent vector storage
- Relational database for work sessions, clients, projects
- Memory relations and knowledge graph support
- Materialized views for reporting
- Graph traversal functions

**Start:**
```bash
docker-compose -f docker-compose.central.yml up -d
```

**Stop:**
```bash
docker-compose -f docker-compose.central.yml down
```

### Option 2: HTTP/SSE Transport (Development)

**Best for:** Development, testing, Claude Code integration

**File:** `docker-compose.http.yml`

**Services:**
- Qdrant (vector database) on port 6333/6334
- Memoria HTTP server on port 8765

**Features:**
- Lightweight setup
- No PostgreSQL overhead
- Direct HTTP/SSE connection to Memoria

**Start:**
```bash
docker-compose -f docker-compose.http.yml up -d
```

**Claude Code Configuration:**
Add to `~/.claude/config.json`:
```json
{
  "mcp_servers": {
    "memoria": {
      "url": "http://localhost:8765/sse"
    }
  }
}
```

### Option 3: Qdrant Only (Minimal)

**Best for:** Testing, CI/CD, minimal deployments

**File:** `docker-compose.qdrant-only.yml`

**Services:**
- Qdrant (vector database) on port 6333/6334

**Start:**
```bash
docker-compose -f docker-compose.qdrant-only.yml up -d
```

**Run local MCP server:**
```bash
cd /Users/alberto/Dev/Priv/Memoria
python -m mcp_memoria
```

---

## Configuration

### Default Credentials

**PostgreSQL:**
- Username: `memoria`
- Password: `memoria_dev`
- Database: `memoria`
- Host: `localhost` (from host machine) or `postgres` (from container)
- Port: 5432

### Customizing Configuration

#### Option 1: Using .env File (Recommended)

```bash
# Copy template
cp docker/.env.example docker/.env

# Edit with your values
nano docker/.env

# Example .env contents:
# POSTGRES_PASSWORD=your_secure_password_here
# MEMORIA_EMBEDDING_MODEL=nomic-embed-text
# MEMORIA_LOG_LEVEL=DEBUG
```

Environment variables are automatically loaded by docker-compose.

#### Option 2: Command-Line Override

```bash
# Set password for this session only
POSTGRES_PASSWORD=my_secure_pass docker-compose -f docker-compose.central.yml up -d
```

#### Option 3: Edit docker-compose File

```yaml
# In docker-compose.central.yml, under postgres service:
environment:
  POSTGRES_PASSWORD: your_secure_password
```

---

## Database Access

### From Host Machine

**PostgreSQL Command Line:**
```bash
psql -h localhost -U memoria -d memoria
# When prompted: memoria_dev (or your custom password)
```

**PostgreSQL GUI Tools:**
- pgAdmin: http://localhost:5050 (requires additional container)
- DBeaver
- psql (command-line, shown above)

**Connection String:**
```
postgresql://memoria:memoria_dev@localhost:5432/memoria
```

### From within Containers

**From Memoria container:**
```bash
docker exec memoria-postgres psql -U memoria -d memoria -c "SELECT * FROM clients;"
```

**From any container:**
```bash
docker exec -it memoria-postgres psql -U memoria -d memoria
```

### Useful Queries

**View all tables:**
```sql
SELECT tablename FROM pg_tables WHERE schemaname = 'public';
```

**Check work sessions:**
```sql
SELECT id, description, status, start_time, duration_minutes FROM work_sessions LIMIT 10;
```

**Check memory relations:**
```sql
SELECT source_id, relation_type, target_id FROM memory_relations LIMIT 10;
```

**View settings:**
```sql
SELECT key, value FROM user_settings;
```

---

## Quick Start Script

The `start.sh` script provides convenient management of all configurations.

### Usage

```bash
./start.sh [COMMAND]
```

### Available Commands

| Command | Description |
|---------|-------------|
| `central` | Start central architecture (default) |
| `http` | Start HTTP/SSE transport |
| `qdrant-only` | Start Qdrant only |
| `stop` | Stop all services |
| `clean` | Remove all containers and volumes |
| `status` | Show service status |
| `logs [TYPE] [SERVICE]` | View logs |

### Examples

```bash
# Start central architecture
./start.sh central

# Check status
./start.sh status

# View Qdrant logs
./start.sh logs central qdrant

# View PostgreSQL logs
./start.sh logs central postgres

# Stop all services
./start.sh stop

# Clean everything (WARNING: deletes data!)
./start.sh clean
```

---

## Docker Compose Commands Reference

### Basic Operations

```bash
# Start services in background
docker-compose -f docker-compose.central.yml up -d

# Start with live logs
docker-compose -f docker-compose.central.yml up

# Stop services
docker-compose -f docker-compose.central.yml down

# Stop services and remove volumes (WARNING: deletes data!)
docker-compose -f docker-compose.central.yml down -v

# Restart services
docker-compose -f docker-compose.central.yml restart
```

### Monitoring

```bash
# View service status
docker-compose -f docker-compose.central.yml ps

# View logs
docker-compose -f docker-compose.central.yml logs -f

# View logs for specific service
docker-compose -f docker-compose.central.yml logs -f postgres

# View last 100 lines
docker-compose -f docker-compose.central.yml logs --tail 100

# View logs with timestamps
docker-compose -f docker-compose.central.yml logs -f --timestamps
```

### Service Management

```bash
# Restart specific service
docker-compose -f docker-compose.central.yml restart postgres

# Rebuild images
docker-compose -f docker-compose.central.yml build

# Pull latest images
docker-compose -f docker-compose.central.yml pull

# Execute command in container
docker-compose -f docker-compose.central.yml exec postgres psql -U memoria -d memoria

# View resource usage
docker stats
```

---

## Troubleshooting

### Services Not Starting

```bash
# Check logs
docker-compose -f docker-compose.central.yml logs

# Check if ports are in use
lsof -i :6333
lsof -i :5432

# Kill process using port (if needed)
kill -9 <PID>
```

### Connection Refused

```bash
# Verify containers are running
docker ps

# Check network connectivity
docker network inspect memoria-central

# Test from container
docker exec memoria-postgres ping qdrant
docker exec memoria-qdrant curl http://postgres:5432 || true
```

### Database Initialization Failed

```bash
# Check PostgreSQL logs
docker-compose -f docker-compose.central.yml logs postgres

# Reinitialize (WARNING: deletes existing data)
docker-compose -f docker-compose.central.yml down -v
docker-compose -f docker-compose.central.yml up -d postgres

# Wait for health check
sleep 10
docker-compose -f docker-compose.central.yml ps
```

### Permission Denied Errors

```bash
# Fix volume ownership
docker run --rm -v memoria-postgres-data:/data \
  -v memoria-qdrant-data:/qdrant \
  alpine sh -c "chown -R 70:70 /data && chown -R 1000:1000 /qdrant"

# Restart services
docker-compose -f docker-compose.central.yml restart
```

---

## Backup & Restore

### Backup PostgreSQL

```bash
# Backup to SQL file
docker exec memoria-postgres pg_dump -U memoria -d memoria \
  > /Users/alberto/Dev/Priv/Memoria/backups/postgres_$(date +%s).sql

# Backup compressed
docker exec memoria-postgres pg_dump -U memoria -d memoria \
  | gzip > /Users/alberto/Dev/Priv/Memoria/backups/postgres_$(date +%s).sql.gz
```

### Restore PostgreSQL

```bash
# From SQL file
docker exec -i memoria-postgres psql -U memoria -d memoria \
  < /Users/alberto/Dev/Priv/Memoria/backups/postgres_latest.sql

# From compressed file
gunzip -c /Users/alberto/Dev/Priv/Memoria/backups/postgres_latest.sql.gz \
  | docker exec -i memoria-postgres psql -U memoria -d memoria
```

### Backup Qdrant

```bash
# Using Docker
docker run --rm -v memoria-qdrant-data:/data \
  -v $(pwd)/backups:/backup \
  alpine tar czf /backup/qdrant_$(date +%s).tar.gz -C /data .
```

### Restore Qdrant

```bash
# Stop Qdrant first
docker-compose -f docker-compose.central.yml stop qdrant

# Restore from backup
docker run --rm -v memoria-qdrant-data:/data \
  -v $(pwd)/backups:/backup \
  alpine tar xzf /backup/qdrant_latest.tar.gz -C /data

# Start Qdrant
docker-compose -f docker-compose.central.yml start qdrant
```

---

## Production Deployment

### Pre-Deployment Checklist

- [ ] Change PostgreSQL password: `POSTGRES_PASSWORD=$(openssl rand -base64 32)`
- [ ] Enable Qdrant API key if using network access
- [ ] Set up automatic backups (daily)
- [ ] Configure resource limits
- [ ] Set up monitoring and alerting
- [ ] Document operational procedures
- [ ] Test disaster recovery
- [ ] Configure SSL/TLS for external access (via reverse proxy)
- [ ] Set up log aggregation
- [ ] Plan upgrade strategy

### Security Recommendations

1. **Strong Passwords**
```bash
# Generate secure password
POSTGRES_PASSWORD=$(openssl rand -base64 32)
echo $POSTGRES_PASSWORD > .env.local  # Store securely, don't commit
```

2. **API Key for Qdrant**
```bash
# Generate API key
QDRANT_API_KEY=$(openssl rand -base64 32)
```

3. **Network Isolation**
- Don't expose ports directly to internet
- Use firewall rules
- Consider reverse proxy with SSL/TLS
- Use VPN or SSH tunneling for remote access

4. **Regular Backups**
```bash
# Automated backup script
#!/bin/bash
BACKUP_DIR="/path/to/backups"
mkdir -p "$BACKUP_DIR"

# PostgreSQL
docker exec memoria-postgres pg_dump -U memoria -d memoria \
  | gzip > "$BACKUP_DIR/postgres_$(date +%Y%m%d_%H%M%S).sql.gz"

# Keep last 30 days
find "$BACKUP_DIR" -name "*.gz" -mtime +30 -delete
```

5. **Monitoring**
- Monitor container health
- Track disk space usage
- Monitor database size
- Set up alerts for failures

---

## Integration with Claude Code

### HTTP Transport Setup

1. **Start Memoria with HTTP transport:**
```bash
./start.sh http
# or
docker-compose -f docker-compose.http.yml up -d
```

2. **Configure Claude Code:**
Edit `~/.claude/config.json`:
```json
{
  "mcp_servers": {
    "memoria": {
      "url": "http://localhost:8765/sse"
    }
  }
}
```

3. **Verify connection:**
```bash
curl -i http://localhost:8765/health
```

### Available Memory Operations

Once connected, you can use:
- `memoria_store` - Store memories with tags
- `memoria_recall` - Recall similar memories
- `memoria_search` - Advanced search with filters
- `memoria_update` - Update existing memories
- `memoria_delete` - Delete memories
- `memoria_consolidate` - Merge similar memories
- `memoria_export` - Export to JSON/JSONL
- `memoria_import` - Import from backup
- `memoria_stats` - View statistics
- `memoria_set_context` - Set current project/file

---

## File Structure

```
docker/
├── docker-compose.central.yml      # Qdrant + PostgreSQL (production)
├── docker-compose.http.yml         # Qdrant + Memoria HTTP (development)
├── docker-compose.qdrant-only.yml  # Qdrant only (minimal)
├── Dockerfile                       # Memoria server image
├── init-db.sql                      # PostgreSQL schema initialization
├── start.sh                         # Quick start script
├── .env.example                     # Environment template
├── README.md                        # Docker usage guide
├── DOCKER_ARCHITECTURE.md           # Detailed architecture documentation
└── (existing files)                 # Legacy configurations

docs/
├── DATABASE_ARCHITECTURE.md         # Dual-database design
└── MEMORIA_UI_WORKTRACKING_PLAN.md # UI and work tracking features
```

---

## Next Steps

### Immediate
1. Test basic connectivity (see Quick Start)
2. Create initial work session
3. Test memory storage and recall
4. Explore CLI tools

### Short Term
1. Set up automated backups
2. Configure environment for your preferences
3. Integrate with Claude Code
4. Create custom settings

### Long Term
1. Deploy web UI (when available)
2. Set up knowledge graph relations
3. Build analytics dashboards
4. Implement monitoring/alerting

---

## Documentation

For detailed information, see:

| Document | Purpose |
|----------|---------|
| `/Users/alberto/Dev/Priv/Memoria/docker/README.md` | Docker configuration reference |
| `/Users/alberto/Dev/Priv/Memoria/docker/DOCKER_ARCHITECTURE.md` | Technical architecture details |
| `/Users/alberto/Dev/Priv/Memoria/docs/DATABASE_ARCHITECTURE.md` | Database design and rationale |
| `/Users/alberto/Dev/Priv/Memoria/docs/MEMORIA_UI_WORKTRACKING_PLAN.md` | Features and roadmap |
| `/Users/alberto/Dev/Priv/Memoria/CLAUDE.md` | Project instructions |

---

## Support

### Check Service Logs
```bash
docker-compose -f docker-compose.central.yml logs [service]
```

### Common Issues & Fixes

**Port Already in Use**
```bash
# Find what's using the port
lsof -i :6333

# Kill the process
kill -9 <PID>
```

**Database Connection Error**
```bash
# Test PostgreSQL
docker exec memoria-postgres pg_isready -U memoria

# If not ready, check logs
docker-compose -f docker-compose.central.yml logs postgres
```

**Qdrant Not Responding**
```bash
# Check Qdrant health
curl http://localhost:6333/health

# Check logs
docker-compose -f docker-compose.central.yml logs qdrant
```

---

## Clean Up

### Remove Services Only
```bash
docker-compose -f docker-compose.central.yml down
```

### Remove Services & Data (WARNING: Deletes all data!)
```bash
docker-compose -f docker-compose.central.yml down -v
```

### Using Script
```bash
./start.sh stop  # Stop services
./start.sh clean # Remove everything
```

---

## Additional Resources

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Guide](https://docs.docker.com/compose/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Qdrant Documentation](https://qdrant.tech/documentation/)
