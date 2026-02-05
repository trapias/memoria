-- Auto-refresh materialized views when work sessions are completed
-- Also adds missing components from migration 003

-- =============================================================================
-- ADD MISSING FUNCTIONS (idempotent)
-- =============================================================================

-- Refresh function for work views only
CREATE OR REPLACE FUNCTION refresh_work_views()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY monthly_work_summary;
    REFRESH MATERIALIZED VIEW CONCURRENTLY daily_work_totals;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION refresh_work_views IS 'Refresh work session materialized views';

-- =============================================================================
-- CLIENT STATISTICS VIEW (if not exists)
-- =============================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_matviews WHERE matviewname = 'client_statistics') THEN
        CREATE MATERIALIZED VIEW client_statistics AS
        SELECT
            c.id as client_id,
            c.name as client_name,
            COUNT(DISTINCT ws.id) as total_sessions,
            COALESCE(SUM(ws.duration_minutes), 0) as total_minutes,
            COALESCE(AVG(ws.duration_minutes)::INT, 0) as avg_session_minutes,
            COUNT(DISTINCT p.id) as project_count,
            MIN(ws.start_time) as first_session,
            MAX(ws.start_time) as last_session,
            COUNT(DISTINCT DATE(ws.start_time)) as days_worked
        FROM clients c
        LEFT JOIN work_sessions ws ON ws.client_id = c.id AND ws.status = 'completed'
        LEFT JOIN projects p ON p.client_id = c.id
        GROUP BY c.id, c.name;

        CREATE UNIQUE INDEX idx_client_statistics_pk ON client_statistics(client_id);
    END IF;
END $$;

-- =============================================================================
-- REFRESH ALL STATISTICS FUNCTION
-- =============================================================================

CREATE OR REPLACE FUNCTION refresh_all_statistics()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY monthly_work_summary;
    REFRESH MATERIALIZED VIEW CONCURRENTLY daily_work_totals;
    -- Only refresh client_statistics if it exists
    IF EXISTS (SELECT 1 FROM pg_matviews WHERE matviewname = 'client_statistics') THEN
        REFRESH MATERIALIZED VIEW CONCURRENTLY client_statistics;
    END IF;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION refresh_all_statistics IS 'Refresh all materialized views for statistics';

-- =============================================================================
-- AUTO-REFRESH TRIGGER
-- Automatically refreshes views when a session is completed
-- =============================================================================

-- Function that performs the refresh
CREATE OR REPLACE FUNCTION trigger_refresh_work_views()
RETURNS TRIGGER AS $$
BEGIN
    -- Only refresh when status changes to 'completed'
    IF NEW.status = 'completed' AND (OLD.status IS NULL OR OLD.status != 'completed') THEN
        -- Use non-concurrent refresh in trigger (faster, and we're in a transaction)
        REFRESH MATERIALIZED VIEW monthly_work_summary;
        REFRESH MATERIALIZED VIEW daily_work_totals;
        -- Refresh client_statistics if it exists
        IF EXISTS (SELECT 1 FROM pg_matviews WHERE matviewname = 'client_statistics') THEN
            REFRESH MATERIALIZED VIEW client_statistics;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION trigger_refresh_work_views IS 'Trigger function to auto-refresh views on session completion';

-- Create the trigger (drop first if exists to ensure clean state)
DROP TRIGGER IF EXISTS work_session_completed_refresh ON work_sessions;

CREATE TRIGGER work_session_completed_refresh
    AFTER UPDATE ON work_sessions
    FOR EACH ROW
    WHEN (NEW.status = 'completed' AND OLD.status IS DISTINCT FROM 'completed')
    EXECUTE FUNCTION trigger_refresh_work_views();

COMMENT ON TRIGGER work_session_completed_refresh ON work_sessions IS
    'Auto-refresh materialized views when a work session is completed';

-- =============================================================================
-- INITIAL REFRESH
-- Ensure views are populated after migration
-- =============================================================================

SELECT refresh_all_statistics();
