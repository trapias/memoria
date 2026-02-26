-- Migration: Add rejected_suggestions table for storing rejected relation suggestions
-- This prevents previously rejected suggestions from being shown again.

CREATE TABLE IF NOT EXISTS rejected_suggestions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID NOT NULL,
    target_id UUID NOT NULL,
    relation_type TEXT NOT NULL,
    rejected_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (source_id, target_id, relation_type)
);

CREATE INDEX IF NOT EXISTS idx_rejected_suggestions_lookup
ON rejected_suggestions (source_id, target_id);

COMMENT ON TABLE rejected_suggestions IS 'Stores rejected relation suggestions to avoid re-suggesting them';
