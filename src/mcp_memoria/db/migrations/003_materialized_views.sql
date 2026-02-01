-- Materialized Views for Work Session Reports
-- Pre-computed aggregations for dashboard and reporting queries

-- =============================================================================
-- MONTHLY WORK SUMMARY VIEW
-- Aggregates work sessions by month, client, project, and category
-- =============================================================================

CREATE MATERIALIZED VIEW monthly_work_summary AS
SELECT
    date_trunc('month', ws.start_time) as month,
    c.id as client_id,
    c.name as client_name,
    p.id as project_id,
    p.name as project_name,
    ws.category,
    COUNT(*) as session_count,
    COALESCE(SUM(ws.duration_minutes), 0) as total_minutes,
    COALESCE(AVG(ws.duration_minutes)::INT, 0) as avg_minutes,
    COUNT(DISTINCT DATE(ws.start_time)) as days_worked
FROM work_sessions ws
LEFT JOIN clients c ON ws.client_id = c.id
LEFT JOIN projects p ON ws.project_id = p.id
WHERE ws.status = 'completed'
GROUP BY 1, 2, 3, 4, 5, 6;

-- Unique index required for CONCURRENTLY refresh
CREATE UNIQUE INDEX idx_monthly_summary_pk
ON monthly_work_summary(month, COALESCE(client_id, '00000000-0000-0000-0000-000000000000'::uuid), COALESCE(project_id, '00000000-0000-0000-0000-000000000000'::uuid), category);

-- Additional indexes for common queries
CREATE INDEX idx_monthly_summary_month ON monthly_work_summary(month DESC);
CREATE INDEX idx_monthly_summary_client ON monthly_work_summary(client_id);

-- =============================================================================
-- DAILY WORK TOTALS VIEW
-- Aggregates work sessions by day and client for timeline charts
-- =============================================================================

CREATE MATERIALIZED VIEW daily_work_totals AS
SELECT
    DATE(start_time) as date,
    client_id,
    COALESCE(SUM(duration_minutes), 0) as total_minutes,
    COUNT(*) as session_count
FROM work_sessions
WHERE status = 'completed'
GROUP BY 1, 2;

-- Unique index required for CONCURRENTLY refresh
CREATE UNIQUE INDEX idx_daily_totals_pk ON daily_work_totals(date, COALESCE(client_id, '00000000-0000-0000-0000-000000000000'::uuid));

-- Additional indexes
CREATE INDEX idx_daily_totals_date ON daily_work_totals(date DESC);
CREATE INDEX idx_daily_totals_client ON daily_work_totals(client_id);

-- =============================================================================
-- REFRESH FUNCTION
-- Call periodically or after session completion
-- =============================================================================

CREATE OR REPLACE FUNCTION refresh_work_views()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY monthly_work_summary;
    REFRESH MATERIALIZED VIEW CONCURRENTLY daily_work_totals;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION refresh_work_views IS 'Refresh all work session materialized views';

-- =============================================================================
-- CLIENT STATISTICS VIEW
-- Per-client aggregated statistics
-- =============================================================================

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

-- =============================================================================
-- REFRESH ALL VIEWS FUNCTION
-- =============================================================================

CREATE OR REPLACE FUNCTION refresh_all_statistics()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY monthly_work_summary;
    REFRESH MATERIALIZED VIEW CONCURRENTLY daily_work_totals;
    REFRESH MATERIALIZED VIEW CONCURRENTLY client_statistics;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION refresh_all_statistics IS 'Refresh all materialized views for statistics';
