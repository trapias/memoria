-- Memoria PostgreSQL Database Initialization
-- Schema for dual-database architecture (Qdrant vectors + PostgreSQL relational)
--
-- This script is automatically executed by docker-compose on first run.
-- For updates, see individual migration files in migrations/ directory.

-- ============================================================================
-- ENUMS
-- ============================================================================

CREATE TYPE session_category AS ENUM (
    'coding',
    'review',
    'meeting',
    'support',
    'research',
    'documentation',
    'devops',
    'other'
);

CREATE TYPE session_status AS ENUM (
    'active',
    'paused',
    'completed'
);

CREATE TYPE relation_type AS ENUM (
    'causes',      -- A leads to B
    'fixes',       -- A resolves B
    'supports',    -- A confirms B
    'opposes',     -- A contradicts B
    'follows',     -- A comes after B
    'supersedes',  -- A replaces B
    'derives',     -- A is derived from B
    'part_of',     -- A is component of B
    'related'      -- Generic connection
);

CREATE TYPE relation_creator AS ENUM (
    'user',        -- Manually created
    'auto',        -- AI suggested and accepted
    'system'       -- Created by consolidation/system
);

-- ============================================================================
-- CLIENTS & PROJECTS
-- ============================================================================

CREATE TABLE clients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT UNIQUE NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_clients_name ON clients(name);

CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID REFERENCES clients(id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    repo TEXT,  -- "owner/repo" for GitHub integration
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(client_id, name)
);

CREATE INDEX idx_projects_client ON projects(client_id);
CREATE INDEX idx_projects_repo ON projects(repo) WHERE repo IS NOT NULL;
CREATE INDEX idx_projects_name ON projects(name);

-- ============================================================================
-- WORK SESSIONS
-- ============================================================================

CREATE TABLE work_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Description
    description TEXT NOT NULL,
    category session_category NOT NULL DEFAULT 'coding',

    -- Relations (nullable for flexibility)
    client_id UUID REFERENCES clients(id) ON DELETE SET NULL,
    project_id UUID REFERENCES projects(id) ON DELETE SET NULL,

    -- GitHub context
    issue_number INT,
    pr_number INT,
    branch TEXT,

    -- Timing
    start_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    end_time TIMESTAMPTZ,

    -- Calculated duration (in minutes, excludes pauses)
    duration_minutes INT GENERATED ALWAYS AS (
        CASE
            WHEN end_time IS NOT NULL THEN
                GREATEST(0, EXTRACT(EPOCH FROM (end_time - start_time))::INT / 60 - COALESCE(total_pause_minutes, 0))
            ELSE NULL
        END
    ) STORED,

    -- Pauses as JSONB array [{start, end, reason}]
    pauses JSONB DEFAULT '[]',
    total_pause_minutes INT DEFAULT 0,

    -- Status
    status session_status DEFAULT 'active',

    -- Notes as array
    notes TEXT[] DEFAULT '{}',

    -- Link to episodic memory in Qdrant (optional)
    memory_id UUID,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX idx_sessions_client ON work_sessions(client_id);
CREATE INDEX idx_sessions_project ON work_sessions(project_id);
CREATE INDEX idx_sessions_start_time ON work_sessions(start_time DESC);
CREATE INDEX idx_sessions_status ON work_sessions(status);
CREATE INDEX idx_sessions_category ON work_sessions(category);

-- Composite index for date range + client queries
CREATE INDEX idx_sessions_time_client ON work_sessions(start_time, client_id);

-- Partial index for active sessions (usually just one)
CREATE INDEX idx_sessions_active ON work_sessions(id) WHERE status = 'active';

-- ============================================================================
-- MEMORY RELATIONS (Knowledge Graph)
-- ============================================================================

CREATE TABLE memory_relations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Endpoints (UUIDs match Qdrant point IDs)
    source_id UUID NOT NULL,
    target_id UUID NOT NULL,

    -- Relation properties
    relation_type relation_type NOT NULL,
    weight FLOAT DEFAULT 1.0 CHECK (weight >= 0 AND weight <= 1),

    -- Metadata
    created_by relation_creator DEFAULT 'user',
    metadata JSONB DEFAULT '{}',

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Prevent duplicate relations of same type
    UNIQUE(source_id, target_id, relation_type),

    -- Prevent self-loops
    CHECK (source_id != target_id)
);

-- Indexes for graph traversal
CREATE INDEX idx_relations_source ON memory_relations(source_id);
CREATE INDEX idx_relations_target ON memory_relations(target_id);
CREATE INDEX idx_relations_type ON memory_relations(relation_type);

-- Composite for efficient neighbor queries
CREATE INDEX idx_relations_source_type ON memory_relations(source_id, relation_type);
CREATE INDEX idx_relations_target_type ON memory_relations(target_id, relation_type);

-- ============================================================================
-- REJECTED SUGGESTIONS (for relation discovery)
-- ============================================================================

CREATE TABLE rejected_suggestions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID NOT NULL,
    target_id UUID NOT NULL,
    relation_type TEXT NOT NULL,
    rejected_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (source_id, target_id, relation_type)
);

CREATE INDEX idx_rejected_suggestions_lookup
ON rejected_suggestions (source_id, target_id);

-- ============================================================================
-- USER SETTINGS
-- ============================================================================

CREATE TABLE user_settings (
    key TEXT PRIMARY KEY,
    value JSONB NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Default settings
INSERT INTO user_settings (key, value) VALUES
    ('default_client', 'null'),
    ('default_project', 'null'),
    ('work_day_hours', '8'),
    ('timezone', '"UTC"'),
    ('consolidation_enabled', 'true'),
    ('consolidation_threshold', '0.85'),
    ('auto_session_memory', 'true')
ON CONFLICT (key) DO NOTHING;

-- ============================================================================
-- MATERIALIZED VIEWS FOR REPORTING
-- ============================================================================

-- Monthly summary by client/project
CREATE MATERIALIZED VIEW monthly_work_summary AS
SELECT
    date_trunc('month', ws.start_time) as month,
    c.id as client_id,
    c.name as client_name,
    p.id as project_id,
    p.name as project_name,
    ws.category,
    COUNT(*) as session_count,
    SUM(ws.duration_minutes) as total_minutes,
    AVG(ws.duration_minutes)::INT as avg_minutes,
    COUNT(DISTINCT DATE(ws.start_time)) as days_worked
FROM work_sessions ws
LEFT JOIN clients c ON ws.client_id = c.id
LEFT JOIN projects p ON ws.project_id = p.id
WHERE ws.status = 'completed'
GROUP BY 1, 2, 3, 4, 5, 6;

CREATE UNIQUE INDEX idx_monthly_summary_pk
ON monthly_work_summary(month, client_id, project_id, category);

-- Daily totals for timeline charts
CREATE MATERIALIZED VIEW daily_work_totals AS
SELECT
    DATE(start_time) as date,
    client_id,
    SUM(duration_minutes) as total_minutes,
    COUNT(*) as session_count
FROM work_sessions
WHERE status = 'completed'
GROUP BY 1, 2;

CREATE UNIQUE INDEX idx_daily_totals_pk ON daily_work_totals(date, client_id);

-- ============================================================================
-- FUNCTIONS FOR GRAPH TRAVERSAL
-- ============================================================================

-- Find neighbors up to N hops
CREATE OR REPLACE FUNCTION get_neighbors(
    p_memory_id UUID,
    p_depth INT DEFAULT 1,
    p_relation_types relation_type[] DEFAULT NULL
)
RETURNS TABLE (
    memory_id UUID,
    depth INT,
    path UUID[],
    relation relation_type
) AS $$
BEGIN
    RETURN QUERY
    WITH RECURSIVE neighbors AS (
        -- Base case: direct neighbors
        SELECT
            CASE WHEN r.source_id = p_memory_id THEN r.target_id ELSE r.source_id END as mem_id,
            1 as d,
            ARRAY[p_memory_id, CASE WHEN r.source_id = p_memory_id THEN r.target_id ELSE r.source_id END] as p,
            r.relation_type as rel
        FROM memory_relations r
        WHERE (r.source_id = p_memory_id OR r.target_id = p_memory_id)
          AND (p_relation_types IS NULL OR r.relation_type = ANY(p_relation_types))

        UNION

        -- Recursive case
        SELECT
            CASE WHEN r.source_id = n.mem_id THEN r.target_id ELSE r.source_id END,
            n.d + 1,
            n.p || CASE WHEN r.source_id = n.mem_id THEN r.target_id ELSE r.source_id END,
            r.relation_type
        FROM neighbors n
        JOIN memory_relations r ON (r.source_id = n.mem_id OR r.target_id = n.mem_id)
        WHERE n.d < p_depth
          AND NOT (CASE WHEN r.source_id = n.mem_id THEN r.target_id ELSE r.source_id END = ANY(n.p))
          AND (p_relation_types IS NULL OR r.relation_type = ANY(p_relation_types))
    )
    SELECT DISTINCT ON (mem_id) mem_id, d, p, rel
    FROM neighbors
    ORDER BY mem_id, d;
END;
$$ LANGUAGE plpgsql;

-- Find shortest path between two memories
CREATE OR REPLACE FUNCTION find_path(
    p_from_id UUID,
    p_to_id UUID,
    p_max_depth INT DEFAULT 5
)
RETURNS TABLE (
    step INT,
    memory_id UUID,
    relation relation_type,
    direction TEXT
) AS $$
BEGIN
    RETURN QUERY
    WITH RECURSIVE path_search AS (
        -- Start from source
        SELECT
            CASE WHEN r.source_id = p_from_id THEN r.target_id ELSE r.source_id END as current,
            1 as s,
            ARRAY[p_from_id] as visited,
            ARRAY[r.relation_type] as relations,
            ARRAY[CASE WHEN r.source_id = p_from_id THEN 'out' ELSE 'in' END] as directions
        FROM memory_relations r
        WHERE r.source_id = p_from_id OR r.target_id = p_from_id

        UNION ALL

        SELECT
            CASE WHEN r.source_id = ps.current THEN r.target_id ELSE r.source_id END,
            ps.s + 1,
            ps.visited || ps.current,
            ps.relations || r.relation_type,
            ps.directions || CASE WHEN r.source_id = ps.current THEN 'out' ELSE 'in' END
        FROM path_search ps
        JOIN memory_relations r ON (r.source_id = ps.current OR r.target_id = ps.current)
        WHERE ps.s < p_max_depth
          AND NOT (CASE WHEN r.source_id = ps.current THEN r.target_id ELSE r.source_id END = ANY(ps.visited))
    )
    SELECT
        unnest_idx as step,
        (visited || current)[unnest_idx] as memory_id,
        relations[unnest_idx] as relation,
        directions[unnest_idx] as direction
    FROM path_search,
         generate_series(1, array_length(visited, 1) + 1) as unnest_idx
    WHERE current = p_to_id
    ORDER BY s, unnest_idx
    LIMIT p_max_depth + 1;
END;
$$ LANGUAGE plpgsql;

-- Refresh materialized views
CREATE OR REPLACE FUNCTION refresh_work_views()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY monthly_work_summary;
    REFRESH MATERIALIZED VIEW CONCURRENTLY daily_work_totals;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- TRIGGERS & AUTOMATIONS
-- ============================================================================

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_clients_updated_at
BEFORE UPDATE ON clients
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_projects_updated_at
BEFORE UPDATE ON projects
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_sessions_updated_at
BEFORE UPDATE ON work_sessions
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_settings_updated_at
BEFORE UPDATE ON user_settings
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- INITIAL DATA
-- ============================================================================

-- Add a sample client for testing (optional, comment out if not needed)
-- INSERT INTO clients (name, metadata) VALUES
--     ('Default Client', '{"default": true}')
-- ON CONFLICT (name) DO NOTHING;

-- ============================================================================
-- SUMMARY
-- ============================================================================
-- Created:
--   - Enums: session_category, session_status, relation_type, relation_creator
--   - Tables: clients, projects, work_sessions, memory_relations, user_settings
--   - Materialized Views: monthly_work_summary, daily_work_totals
--   - Functions: get_neighbors, find_path, refresh_work_views, update_updated_at_column
--   - Triggers: Auto-update timestamps
--   - Indexes: Optimized for common queries
-- ============================================================================
