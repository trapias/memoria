-- Initial Memoria PostgreSQL Schema
-- Creates clients, projects, work_sessions, memory_relations, and user_settings tables

-- =============================================================================
-- ENUM TYPES
-- =============================================================================

CREATE TYPE session_category AS ENUM (
    'coding', 'review', 'meeting', 'support',
    'research', 'documentation', 'devops', 'other'
);

CREATE TYPE session_status AS ENUM ('active', 'paused', 'completed');

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

-- =============================================================================
-- CLIENTS TABLE
-- =============================================================================

CREATE TABLE clients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT UNIQUE NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Trigger to auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER clients_updated_at
    BEFORE UPDATE ON clients
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- PROJECTS TABLE
-- =============================================================================

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

CREATE TRIGGER projects_updated_at
    BEFORE UPDATE ON projects
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- WORK SESSIONS TABLE
-- =============================================================================

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

    -- Pauses as JSONB array [{start, end, reason}]
    pauses JSONB DEFAULT '[]',
    total_pause_minutes INT DEFAULT 0,

    -- Calculated duration (in minutes, excludes pauses)
    duration_minutes INT GENERATED ALWAYS AS (
        CASE
            WHEN end_time IS NOT NULL THEN
                GREATEST(0, EXTRACT(EPOCH FROM (end_time - start_time))::INT / 60 - total_pause_minutes)
            ELSE NULL
        END
    ) STORED,

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

CREATE TRIGGER work_sessions_updated_at
    BEFORE UPDATE ON work_sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- MEMORY RELATIONS TABLE (Knowledge Graph)
-- =============================================================================

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

-- =============================================================================
-- USER SETTINGS TABLE
-- =============================================================================

CREATE TABLE user_settings (
    key TEXT PRIMARY KEY,
    value JSONB NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TRIGGER user_settings_updated_at
    BEFORE UPDATE ON user_settings
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Default settings
INSERT INTO user_settings (key, value) VALUES
    ('default_client', 'null'),
    ('default_project', 'null'),
    ('work_day_hours', '8'),
    ('timezone', '"UTC"'),
    ('consolidation_enabled', 'true'),
    ('consolidation_threshold', '0.85')
ON CONFLICT (key) DO NOTHING;
