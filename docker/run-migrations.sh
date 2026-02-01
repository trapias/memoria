#!/bin/bash
# Automatic PostgreSQL migration runner for Memoria
# Runs pending migrations on container startup

set -e

MIGRATIONS_DIR="/app/docker/migrations"
DATABASE_URL="${MEMORIA_DATABASE_URL:-postgresql://memoria:memoria_dev@postgres:5432/memoria}"

echo "🔄 Running database migrations..."

# Create schema_migrations table if it doesn't exist
psql "$DATABASE_URL" -c "
CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ DEFAULT NOW()
);
" 2>/dev/null || true

# Check if migrations directory exists
if [ ! -d "$MIGRATIONS_DIR" ]; then
    echo "⚠️  No migrations directory found at $MIGRATIONS_DIR"
    exit 0
fi

# Get list of migration files sorted by name
MIGRATIONS=$(ls -1 "$MIGRATIONS_DIR"/*.sql 2>/dev/null | sort)

if [ -z "$MIGRATIONS" ]; then
    echo "✅ No migrations to apply"
    exit 0
fi

# Apply each migration if not already applied
APPLIED=0
for migration in $MIGRATIONS; do
    filename=$(basename "$migration")

    # Check if already applied
    EXISTS=$(psql "$DATABASE_URL" -t -c "SELECT 1 FROM schema_migrations WHERE version = '$filename'" 2>/dev/null | tr -d ' ')

    if [ "$EXISTS" = "1" ]; then
        echo "  ⏭️  $filename (already applied)"
    else
        echo "  📦 Applying $filename..."
        psql "$DATABASE_URL" -f "$migration"
        psql "$DATABASE_URL" -c "INSERT INTO schema_migrations (version) VALUES ('$filename')"
        echo "  ✅ $filename applied"
        APPLIED=$((APPLIED + 1))
    fi
done

if [ $APPLIED -gt 0 ]; then
    echo "🎉 Applied $APPLIED migration(s)"
else
    echo "✅ Database is up to date"
fi
