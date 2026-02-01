#!/bin/bash
# Memoria Web UI + REST API Startup Script
#
# This script runs inside the Docker container to start both services:
#   - FastAPI REST API on port 8765
#   - Next.js Web UI on port 3000

set -e

echo "=== Memoria Web UI Container ==="
echo ""

# Function to handle shutdown
cleanup() {
    echo ""
    echo "Shutting down..."
    kill $API_PID $UI_PID 2>/dev/null || true
    exit 0
}

trap cleanup SIGTERM SIGINT

# Wait for dependencies
echo "Waiting for Qdrant..."
QDRANT_URL="http://${QDRANT_HOST:-qdrant}:${QDRANT_PORT:-6333}"
until curl -sf "${QDRANT_URL}/" > /dev/null 2>&1; do
    echo "  Qdrant not ready, retrying..."
    sleep 2
done
echo "✓ Qdrant is ready at ${QDRANT_URL}"

# Wait for PostgreSQL using MEMORIA_DATABASE_URL
DB_URL="${MEMORIA_DATABASE_URL:-$DATABASE_URL}"
if [ -n "$DB_URL" ]; then
    echo "Waiting for PostgreSQL..."
    # Extract host from DATABASE_URL (postgresql://user:pass@host:port/db)
    PG_HOST=$(echo $DB_URL | sed -E 's|.*@([^:/]+).*|\1|')
    PG_PORT=$(echo $DB_URL | sed -E 's|.*:([0-9]+)/.*|\1|' || echo "5432")

    until nc -z "$PG_HOST" "$PG_PORT" 2>/dev/null; do
        echo "  PostgreSQL not ready at ${PG_HOST}:${PG_PORT}, retrying..."
        sleep 2
    done
    echo "✓ PostgreSQL is ready at ${PG_HOST}:${PG_PORT}"

    # Run database migrations
    echo ""
    /app/run-migrations.sh
else
    echo "⚠ DATABASE_URL not set, skipping PostgreSQL check and migrations"
fi

echo ""
echo "Starting services..."

# Start REST API in background
echo "Starting REST API on port ${API_PORT:-8765}..."
cd /app
python -m mcp_memoria.api &
API_PID=$!

# Wait a bit for API to start
sleep 3

# Check if API started successfully
if ! kill -0 $API_PID 2>/dev/null; then
    echo "✗ REST API failed to start"
    exit 1
fi
echo "✓ REST API started (PID: $API_PID)"

# Start Next.js UI
echo "Starting Web UI on port 3000..."
cd /app/web
NODE_ENV=production npm start &
UI_PID=$!

sleep 2
if ! kill -0 $UI_PID 2>/dev/null; then
    echo "✗ Web UI failed to start"
    exit 1
fi
echo "✓ Web UI started (PID: $UI_PID)"

echo ""
echo "=== Services started ==="
echo "  Web UI:   http://localhost:3000"
echo "  REST API: http://localhost:${API_PORT:-8765}"
echo ""

# Wait for both processes
wait $API_PID $UI_PID
