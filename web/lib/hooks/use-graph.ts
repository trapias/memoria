"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, Subgraph, GraphPath, Relation, RelationSuggestion, GraphNode } from "../api";

export function useSubgraph(centerId: string | null, depth: number = 2) {
  return useQuery({
    queryKey: ["subgraph", centerId, depth],
    queryFn: () => api.getSubgraph(centerId!, depth),
    enabled: !!centerId,
  });
}

export function useNeighbors(
  memoryId: string | null,
  depth: number = 1,
  relationTypes?: string[],
  direction: string = "both"
) {
  return useQuery({
    queryKey: ["neighbors", memoryId, depth, relationTypes, direction],
    queryFn: () => api.getNeighbors(memoryId!, depth, relationTypes, direction),
    enabled: !!memoryId,
  });
}

export function useFindPath(
  fromId: string | null,
  toId: string | null,
  maxDepth: number = 5
) {
  return useQuery({
    queryKey: ["path", fromId, toId, maxDepth],
    queryFn: () => api.findPath(fromId!, toId!, maxDepth),
    enabled: !!fromId && !!toId,
  });
}

export function useRelations(
  memoryId: string | null,
  direction: string = "both",
  relationType?: string
) {
  return useQuery({
    queryKey: ["relations", memoryId, direction, relationType],
    queryFn: () => api.getRelations(memoryId!, direction, relationType),
    enabled: !!memoryId,
  });
}

export function useSuggestions(memoryId: string | null, limit: number = 5) {
  return useQuery({
    queryKey: ["suggestions", memoryId, limit],
    queryFn: () => api.getSuggestions(memoryId!, limit),
    enabled: !!memoryId,
  });
}

export function useCreateRelation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      sourceId,
      targetId,
      relationType,
      weight = 1.0,
    }: {
      sourceId: string;
      targetId: string;
      relationType: string;
      weight?: number;
    }) => api.createRelation(sourceId, targetId, relationType, weight),
    onSuccess: (_, variables) => {
      // Invalidate related queries
      queryClient.invalidateQueries({ queryKey: ["subgraph"] });
      queryClient.invalidateQueries({ queryKey: ["neighbors"] });
      queryClient.invalidateQueries({
        queryKey: ["relations", variables.sourceId],
      });
      queryClient.invalidateQueries({
        queryKey: ["relations", variables.targetId],
      });
      queryClient.invalidateQueries({
        queryKey: ["suggestions", variables.sourceId],
      });
    },
  });
}

export function useDeleteRelation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      sourceId,
      targetId,
      relationType,
    }: {
      sourceId: string;
      targetId: string;
      relationType?: string;
    }) => api.deleteRelation(sourceId, targetId, relationType),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["subgraph"] });
      queryClient.invalidateQueries({ queryKey: ["neighbors"] });
      queryClient.invalidateQueries({
        queryKey: ["relations", variables.sourceId],
      });
      queryClient.invalidateQueries({
        queryKey: ["relations", variables.targetId],
      });
    },
  });
}

export function useAcceptSuggestion() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      memoryId,
      targetId,
      relationType,
    }: {
      memoryId: string;
      targetId: string;
      relationType: string;
    }) => api.acceptSuggestion(memoryId, targetId, relationType),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["subgraph"] });
      queryClient.invalidateQueries({ queryKey: ["neighbors"] });
      queryClient.invalidateQueries({
        queryKey: ["relations", variables.memoryId],
      });
      queryClient.invalidateQueries({
        queryKey: ["suggestions", variables.memoryId],
      });
    },
  });
}

// Relation type colors for visualization
export const RELATION_COLORS: Record<string, string> = {
  causes: "#ef4444", // red
  fixes: "#22c55e", // green
  supports: "#3b82f6", // blue
  opposes: "#f97316", // orange
  follows: "#a855f7", // purple
  supersedes: "#eab308", // yellow
  derives: "#06b6d4", // cyan
  part_of: "#ec4899", // pink
  related: "#6b7280", // gray
};

export const RELATION_DESCRIPTIONS: Record<string, string> = {
  causes: "A leads to B",
  fixes: "A solves/resolves B",
  supports: "A confirms/supports B",
  opposes: "A contradicts B",
  follows: "A comes after B chronologically",
  supersedes: "A replaces B (outdated info)",
  derives: "A is derived from B",
  part_of: "A is a component of B",
  related: "General connection",
};
