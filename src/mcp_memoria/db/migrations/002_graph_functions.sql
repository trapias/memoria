-- Graph Traversal Functions for Memory Relations
-- Provides WITH RECURSIVE queries for knowledge graph navigation

-- =============================================================================
-- GET NEIGHBORS FUNCTION
-- Find all neighbors up to N hops from a given memory
-- =============================================================================

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
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION get_neighbors IS 'Find all neighboring memories up to N hops from a starting memory';

-- =============================================================================
-- FIND PATH FUNCTION
-- Find shortest path between two memories in the knowledge graph
-- =============================================================================

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
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION find_path IS 'Find shortest path between two memories in the knowledge graph';

-- =============================================================================
-- COUNT RELATIONS FUNCTION
-- Count relations for a memory by type
-- =============================================================================

CREATE OR REPLACE FUNCTION count_relations(
    p_memory_id UUID
)
RETURNS TABLE (
    relation_type relation_type,
    outgoing_count BIGINT,
    incoming_count BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        rt.relation_type,
        COALESCE(out_counts.cnt, 0) as outgoing_count,
        COALESCE(in_counts.cnt, 0) as incoming_count
    FROM (
        SELECT DISTINCT r.relation_type
        FROM memory_relations r
        WHERE r.source_id = p_memory_id OR r.target_id = p_memory_id
    ) rt
    LEFT JOIN (
        SELECT r.relation_type, COUNT(*) as cnt
        FROM memory_relations r
        WHERE r.source_id = p_memory_id
        GROUP BY r.relation_type
    ) out_counts ON rt.relation_type = out_counts.relation_type
    LEFT JOIN (
        SELECT r.relation_type, COUNT(*) as cnt
        FROM memory_relations r
        WHERE r.target_id = p_memory_id
        GROUP BY r.relation_type
    ) in_counts ON rt.relation_type = in_counts.relation_type;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION count_relations IS 'Count incoming and outgoing relations for a memory by type';

-- =============================================================================
-- GET SUBGRAPH FUNCTION
-- Extract a subgraph centered on a memory
-- =============================================================================

CREATE OR REPLACE FUNCTION get_subgraph(
    p_center_id UUID,
    p_depth INT DEFAULT 2
)
RETURNS TABLE (
    source_id UUID,
    target_id UUID,
    relation_type relation_type,
    weight FLOAT,
    depth INT
) AS $$
BEGIN
    RETURN QUERY
    WITH RECURSIVE subgraph AS (
        -- Base case: direct relations
        SELECT
            r.source_id,
            r.target_id,
            r.relation_type,
            r.weight,
            1 as d,
            ARRAY[p_center_id] as visited
        FROM memory_relations r
        WHERE r.source_id = p_center_id OR r.target_id = p_center_id

        UNION

        -- Recursive case: relations of neighbors
        SELECT
            r.source_id,
            r.target_id,
            r.relation_type,
            r.weight,
            sg.d + 1,
            sg.visited || CASE WHEN r.source_id = ANY(sg.visited) THEN r.target_id ELSE r.source_id END
        FROM subgraph sg
        JOIN memory_relations r ON (
            (r.source_id = sg.target_id OR r.source_id = sg.source_id OR
             r.target_id = sg.target_id OR r.target_id = sg.source_id)
            AND NOT (r.source_id = ANY(sg.visited) AND r.target_id = ANY(sg.visited))
        )
        WHERE sg.d < p_depth
    )
    SELECT DISTINCT
        sg.source_id,
        sg.target_id,
        sg.relation_type,
        sg.weight,
        MIN(sg.d) as depth
    FROM subgraph sg
    GROUP BY sg.source_id, sg.target_id, sg.relation_type, sg.weight
    ORDER BY depth, sg.source_id, sg.target_id;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION get_subgraph IS 'Extract a subgraph of relations centered on a memory';
