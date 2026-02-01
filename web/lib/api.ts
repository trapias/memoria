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

export interface Memory {
  id: string;
  content: string;
  memory_type: string;
  tags: string[];
  importance: number;
  created_at: string;
  updated_at: string;
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

  async getStats(): Promise<{
    total_memories: number;
    by_type: Record<string, number>;
    total_relations: number;
  }> {
    return this.fetch("/api/stats");
  }
}

export const api = new ApiClient();
