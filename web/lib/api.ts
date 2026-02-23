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
  source_project: string | null;
  target_id: string;
  target_preview: string;
  target_type: string | null;
  target_project: string | null;
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

// Data Management types
export interface WorkSessionResponse {
  id: string;
  description: string;
  category: string;
  client_id: string | null;
  client_name: string | null;
  project_id: string | null;
  project_name: string | null;
  issue_number: number | null;
  pr_number: number | null;
  branch: string | null;
  start_time: string;
  end_time: string | null;
  duration_minutes: number | null;
  total_pause_minutes: number;
  pauses: Array<{ start: string; end?: string; reason?: string }>;
  status: string;
  notes: string[];
  created_at: string;
  updated_at: string;
}

export interface SessionListResponse {
  items: WorkSessionResponse[];
  total: number;
  page: number;
  pages: number;
}

export interface SessionSummary {
  total_minutes: number;
  session_count: number;
  avg_minutes: number;
  client_count: number;
}

export interface SessionCreateBody {
  description: string;
  category?: string;
  client_id?: string;
  project_id?: string;
  start_time: string;
  end_time: string;
  issue_number?: number;
  pr_number?: number;
  branch?: string;
  notes?: string[];
}

export interface SessionUpdateBody {
  description?: string;
  category?: string;
  client_id?: string;
  project_id?: string;
  start_time?: string;
  end_time?: string;
  issue_number?: number;
  pr_number?: number;
  branch?: string;
  notes?: string[];
}

export interface DataClient {
  id: string;
  name: string;
  metadata: Record<string, unknown>;
  project_count: number;
  session_count: number;
  total_minutes: number;
  last_activity: string | null;
  created_at: string;
  updated_at: string;
}

export interface DataProject {
  id: string;
  name: string;
  client_id: string | null;
  client_name: string | null;
  repo: string | null;
  metadata: Record<string, unknown>;
  session_count: number;
  total_minutes: number;
  last_activity: string | null;
  created_at: string;
  updated_at: string;
}

export interface MemoryPreviewData {
  id: string;
  content_preview: string;
  memory_type: string | null;
  tags: string[];
  importance: number;
}

export interface DataRelation {
  id: string;
  source_id: string;
  target_id: string;
  relation_type: string;
  weight: number;
  created_by: string;
  metadata: Record<string, unknown>;
  created_at: string;
  source: MemoryPreviewData | null;
  target: MemoryPreviewData | null;
}

export interface DataRelationListResponse {
  items: DataRelation[];
  total: number;
  page: number;
  pages: number;
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
  metadata: Record<string, unknown>;
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
  created_after?: string;
  created_before?: string;
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
    if (params.created_after) urlParams.set("created_after", params.created_after);
    if (params.created_before) urlParams.set("created_before", params.created_before);
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
    updates: {
      content?: string;
      tags?: string[];
      importance?: number;
      metadata?: Record<string, unknown>;
    }
  ): Promise<Memory> {
    return this.fetch<Memory>(`/api/memories/${id}`, {
      method: "PUT",
      body: JSON.stringify(updates),
    });
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

  // Data Management endpoints
  async listSessions(params: {
    page?: number;
    page_size?: number;
    date_from?: string;
    date_to?: string;
    client_id?: string;
    project_id?: string;
    status?: string;
    category?: string;
    search?: string;
    sort_by?: string;
    sort_dir?: string;
  } = {}): Promise<SessionListResponse> {
    const urlParams = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") urlParams.set(k, String(v));
    });
    return this.fetch<SessionListResponse>(`/api/data/sessions?${urlParams}`);
  }

  async getSessionsSummary(params: {
    date_from?: string;
    date_to?: string;
    client_id?: string;
  } = {}): Promise<SessionSummary> {
    const urlParams = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") urlParams.set(k, String(v));
    });
    return this.fetch<SessionSummary>(`/api/data/sessions/summary?${urlParams}`);
  }

  async createSession(body: SessionCreateBody): Promise<WorkSessionResponse> {
    return this.fetch("/api/data/sessions", {
      method: "POST",
      body: JSON.stringify(body),
    });
  }

  async updateSession(id: string, body: SessionUpdateBody): Promise<WorkSessionResponse> {
    return this.fetch(`/api/data/sessions/${id}`, {
      method: "PUT",
      body: JSON.stringify(body),
    });
  }

  async deleteSession(id: string): Promise<{ status: string }> {
    return this.fetch(`/api/data/sessions/${id}`, { method: "DELETE" });
  }

  async exportSessionsCsv(params: {
    date_from?: string;
    date_to?: string;
    client_id?: string;
  } = {}): Promise<Blob> {
    const urlParams = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") urlParams.set(k, String(v));
    });
    const response = await fetch(`${API_BASE}/api/data/sessions/export?${urlParams}`);
    if (!response.ok) throw new Error(`Export failed: ${response.status}`);
    return response.blob();
  }

  async listClients(): Promise<DataClient[]> {
    return this.fetch<DataClient[]>("/api/data/clients");
  }

  async createClient(body: { name: string; metadata?: Record<string, unknown> }): Promise<DataClient> {
    return this.fetch("/api/data/clients", {
      method: "POST",
      body: JSON.stringify(body),
    });
  }

  async updateClient(id: string, body: { name?: string; metadata?: Record<string, unknown> }): Promise<DataClient> {
    return this.fetch(`/api/data/clients/${id}`, {
      method: "PUT",
      body: JSON.stringify(body),
    });
  }

  async deleteClient(id: string): Promise<{ status: string }> {
    return this.fetch(`/api/data/clients/${id}`, { method: "DELETE" });
  }

  async listProjects(clientId?: string): Promise<DataProject[]> {
    const params = clientId ? `?client_id=${clientId}` : "";
    return this.fetch<DataProject[]>(`/api/data/projects${params}`);
  }

  async createProject(body: {
    name: string;
    client_id?: string;
    repo?: string;
    metadata?: Record<string, unknown>;
  }): Promise<DataProject> {
    return this.fetch("/api/data/projects", {
      method: "POST",
      body: JSON.stringify(body),
    });
  }

  async updateProject(id: string, body: {
    name?: string;
    client_id?: string;
    repo?: string;
    metadata?: Record<string, unknown>;
  }): Promise<DataProject> {
    return this.fetch(`/api/data/projects/${id}`, {
      method: "PUT",
      body: JSON.stringify(body),
    });
  }

  async deleteProject(id: string): Promise<{ status: string }> {
    return this.fetch(`/api/data/projects/${id}`, { method: "DELETE" });
  }

  async listDataRelations(params: {
    relation_type?: string;
    created_by?: string;
    memory_id?: string;
    page?: number;
    page_size?: number;
  } = {}): Promise<DataRelationListResponse> {
    const urlParams = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") urlParams.set(k, String(v));
    });
    return this.fetch<DataRelationListResponse>(`/api/data/relations?${urlParams}`);
  }

  async deleteOrphanedRelations(): Promise<{ status: string; deleted: number }> {
    return this.fetch("/api/data/relations/orphaned", { method: "DELETE" });
  }

  async deleteDataRelation(id: string): Promise<{ status: string }> {
    return this.fetch(`/api/data/relations/${id}`, { method: "DELETE" });
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
