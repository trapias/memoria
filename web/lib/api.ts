const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8765";

export interface GraphNode {
  id: string;
  label: string;
  type: string | null;
  importance: number;
  tags: string[];
  isCenter: boolean;
  depth?: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: string;
  weight: number;
  created_by: string;
}

export interface Subgraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface Relation {
  id: string;
  source_id: string;
  target_id: string;
  type: string;
  weight: number;
  created_at: string;
  created_by: string;
  metadata: Record<string, unknown>;
}

export interface RelationSuggestion {
  target_id: string;
  target_content: string;
  target_tags: string[];
  target_type: string | null;
  suggested_type: string;
  confidence: number;
  reason: string;
}

export interface DiscoverySuggestion {
  source_id: string;
  source_preview: string;
  source_type: string | null;
  target_id: string;
  target_preview: string;
  target_type: string | null;
  relation_type: string;
  confidence: number;
  reason: string;
  shared_tags: string[];
}

export interface DiscoverRelationsResponse {
  suggestions: DiscoverySuggestion[];
  auto_accepted: number;
  scanned_count: number;
  total_without_relations: number;
}

export interface BulkRelationsResult {
  created: number;
  duplicates: number;
  errors: number;
}

export interface BackupStats {
  memories_count: number;
  relations_count: number;
  tags_count: number;
  exported_at: string;
}

export interface ImportResult {
  memories_imported: number;
  memories_skipped: number;
  relations_imported: number;
  relations_skipped: number;
  errors: string[];
}

export interface ConsolidationPreview {
  operation: string;
  merged_count: number;
  forgotten_count: number;
  updated_count: number;
  total_processed: number;
  duration_seconds: number;
  is_preview: boolean;
}

export interface ConsolidationRequest {
  operation: "consolidate" | "forget" | "decay";
  memory_type: string;
  similarity_threshold?: number;
  max_age_days?: number;
  min_importance?: number;
  dry_run: boolean;
}

export interface Memory {
  id: string;
  content: string;
  memory_type: string;
  tags: string[];
  importance: number;
  created_at: string;
  updated_at: string;
  has_relations?: boolean;
}

export interface MemoryListResponse {
  memories: Memory[];
  total: number;
  offset: number;
  limit: number;
  has_more: boolean;
}

export interface ListMemoriesParams {
  memory_type?: string;
  tags?: string;
  query?: string;
  text_match?: string;
  limit?: number;
  offset?: number;
  sort_by?: "created_at" | "updated_at" | "importance";
  sort_order?: "asc" | "desc";
}

export interface GraphPath {
  from: string;
  to: string;
  found: boolean;
  length: number;
  steps: Array<{
    memory_id: string;
    relation: string | null;
    direction: string | null;
    content: string | null;
  }>;
  total_weight: number;
}

class ApiClient {
  private async fetch<T>(
    endpoint: string,
    options?: RequestInit
  ): Promise<T> {
    const response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options?.headers,
      },
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.status} ${response.statusText}`);
    }

    return response.json();
  }

  // Graph endpoints
  async getGraphOverview(limit: number = 10, depth: number = 2): Promise<Subgraph> {
    return this.fetch<Subgraph>(`/api/graph/overview?limit=${limit}&depth=${depth}`);
  }

  async getSubgraph(centerId: string, depth: number = 2): Promise<Subgraph> {
    return this.fetch<Subgraph>(`/api/graph/subgraph/${centerId}?depth=${depth}`);
  }

  async getNeighbors(
    memoryId: string,
    depth: number = 1,
    relationTypes?: string[],
    direction: string = "both"
  ): Promise<{ center: string; depth: number; neighbors: GraphNode[] }> {
    const params = new URLSearchParams({
      depth: depth.toString(),
      direction,
    });
    if (relationTypes?.length) {
      params.set("relation_types", relationTypes.join(","));
    }
    return this.fetch(`/api/graph/neighbors/${memoryId}?${params}`);
  }

  async findPath(
    fromId: string,
    toId: string,
    maxDepth: number = 5
  ): Promise<GraphPath> {
    const params = new URLSearchParams({
      from_id: fromId,
      to_id: toId,
      max_depth: maxDepth.toString(),
    });
    return this.fetch<GraphPath>(`/api/graph/path?${params}`);
  }

  async getRelations(
    memoryId: string,
    direction: string = "both",
    relationType?: string
  ): Promise<{ memory_id: string; relations: Relation[] }> {
    const params = new URLSearchParams({ direction });
    if (relationType) {
      params.set("relation_type", relationType);
    }
    return this.fetch(`/api/graph/memories/${memoryId}/relations?${params}`);
  }

  async createRelation(
    sourceId: string,
    targetId: string,
    relationType: string,
    weight: number = 1.0
  ): Promise<{ status: string; relation: Relation }> {
    return this.fetch("/api/graph/relations", {
      method: "POST",
      body: JSON.stringify({
        source_id: sourceId,
        target_id: targetId,
        relation_type: relationType,
        weight,
      }),
    });
  }

  async deleteRelation(
    sourceId: string,
    targetId: string,
    relationType?: string
  ): Promise<{ status: string }> {
    const params = new URLSearchParams({
      source_id: sourceId,
      target_id: targetId,
    });
    if (relationType) {
      params.set("relation_type", relationType);
    }
    return this.fetch(`/api/graph/relations?${params}`, {
      method: "DELETE",
    });
  }

  async getSuggestions(
    memoryId: string,
    limit: number = 5
  ): Promise<{ memory_id: string; suggestions: RelationSuggestion[] }> {
    return this.fetch(`/api/graph/suggestions/${memoryId}?limit=${limit}`);
  }

  async acceptSuggestion(
    memoryId: string,
    targetId: string,
    relationType: string
  ): Promise<{ status: string; relation: Relation }> {
    return this.fetch(`/api/graph/suggestions/${memoryId}/accept`, {
      method: "POST",
      body: JSON.stringify({
        target_id: targetId,
        relation_type: relationType,
      }),
    });
  }

  // Memory endpoints
  async listMemories(params: ListMemoriesParams = {}): Promise<MemoryListResponse> {
    const urlParams = new URLSearchParams();
    if (params.memory_type) urlParams.set("memory_type", params.memory_type);
    if (params.tags) urlParams.set("tags", params.tags);
    if (params.query) urlParams.set("query", params.query);
    if (params.text_match) urlParams.set("text_match", params.text_match);
    if (params.limit) urlParams.set("limit", params.limit.toString());
    if (params.offset) urlParams.set("offset", params.offset.toString());
    if (params.sort_by) urlParams.set("sort_by", params.sort_by);
    if (params.sort_order) urlParams.set("sort_order", params.sort_order);
    return this.fetch<MemoryListResponse>(`/api/memories/list?${urlParams}`);
  }

  async searchMemories(
    query: string,
    memoryType?: string,
    limit: number = 10
  ): Promise<Memory[]> {
    const params = new URLSearchParams({
      query,
      limit: limit.toString(),
    });
    if (memoryType) {
      params.set("memory_type", memoryType);
    }
    return this.fetch<Memory[]>(`/api/memories/search?${params}`);
  }

  async getMemory(id: string): Promise<Memory> {
    return this.fetch<Memory>(`/api/memories/${id}`);
  }

  async getAllTags(): Promise<string[]> {
    const result = await this.fetch<{ tags: string[] }>("/api/memories/tags");
    return result.tags;
  }

  async deleteMemory(id: string): Promise<{ status: string }> {
    return this.fetch(`/api/memories/${id}`, { method: "DELETE" });
  }

  async updateMemory(
    id: string,
    updates: { content?: string; tags?: string[]; importance?: number }
  ): Promise<Memory> {
    const params = new URLSearchParams();
    if (updates.content !== undefined) params.set("content", updates.content);
    if (updates.tags !== undefined) params.set("tags", JSON.stringify(updates.tags));
    if (updates.importance !== undefined) params.set("importance", updates.importance.toString());
    return this.fetch<Memory>(`/api/memories/${id}?${params}`, { method: "PUT" });
  }

  async consolidateMemories(request: ConsolidationRequest): Promise<ConsolidationPreview> {
    return this.fetch("/api/memories/consolidate", {
      method: "POST",
      body: JSON.stringify(request),
    });
  }

  async getStats(): Promise<{
    total_memories: number;
    by_type: Record<string, number>;
    total_relations: number;
  }> {
    return this.fetch("/api/stats");
  }

  // Discovery endpoints
  async discoverRelations(params: {
    limit?: number;
    min_confidence?: number;
    auto_accept_threshold?: number;
    skip_with_relations?: boolean;
    memory_types?: string[];
  } = {}): Promise<DiscoverRelationsResponse> {
    return this.fetch("/api/graph/discover", {
      method: "POST",
      body: JSON.stringify(params),
    });
  }

  async createRelationsBulk(
    relations: Array<{ source_id: string; target_id: string; relation_type: string }>,
    createdBy: "user" | "auto" = "auto"
  ): Promise<BulkRelationsResult> {
    return this.fetch("/api/graph/relations/bulk", {
      method: "POST",
      body: JSON.stringify({
        relations,
        created_by: createdBy,
      }),
    });
  }

  async rejectSuggestion(
    sourceId: string,
    targetId: string,
    relationType: string
  ): Promise<{ status: string }> {
    return this.fetch("/api/graph/suggestions/reject", {
      method: "POST",
      body: JSON.stringify({
        source_id: sourceId,
        target_id: targetId,
        relation_type: relationType,
      }),
    });
  }

  // Backup endpoints
  async getBackupStats(): Promise<BackupStats> {
    return this.fetch("/api/backup/stats");
  }

  async exportBackup(options: {
    include_graph?: boolean;
    memory_types?: string[];
  } = {}): Promise<Blob> {
    const response = await fetch(`${API_BASE}/api/backup/export`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        include_graph: options.include_graph ?? true,
        memory_types: options.memory_types ?? ["episodic", "semantic", "procedural"],
      }),
    });

    if (!response.ok) {
      throw new Error(`Export failed: ${response.status}`);
    }

    return response.blob();
  }

  async importBackup(file: File, skipExisting: boolean = true): Promise<ImportResult> {
    const formData = new FormData();
    formData.append("file", file);

    const response = await fetch(
      `${API_BASE}/api/backup/import?skip_existing=${skipExisting}`,
      {
        method: "POST",
        body: formData,
      }
    );

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Import failed" }));
      throw new Error(error.detail || "Import failed");
    }

    return response.json();
  }
}

export const api = new ApiClient();
