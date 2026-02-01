"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, DiscoverRelationsResponse, DiscoverySuggestion } from "../api";

export interface DiscoveryParams {
  limit?: number;
  min_confidence?: number;
  auto_accept_threshold?: number;
  skip_with_relations?: boolean;
  memory_types?: string[];
}

export function useDiscoverRelations(params: DiscoveryParams = {}, enabled: boolean = false) {
  return useQuery({
    queryKey: ["discover-relations", params],
    queryFn: () => api.discoverRelations(params),
    enabled,
    staleTime: 0, // Always refetch when triggered
  });
}

export function useDiscoverRelationsMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (params: DiscoveryParams) => api.discoverRelations(params),
    onSuccess: () => {
      // Invalidate related queries after discovery
      queryClient.invalidateQueries({ queryKey: ["subgraph"] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
    },
  });
}

export function useAcceptDiscoverySuggestions() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (suggestions: Array<{ source_id: string; target_id: string; relation_type: string }>) =>
      api.createRelationsBulk(suggestions, "auto"),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["subgraph"] });
      queryClient.invalidateQueries({ queryKey: ["neighbors"] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
      queryClient.invalidateQueries({ queryKey: ["discover-relations"] });
    },
  });
}

export function useRejectSuggestion() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ sourceId, targetId, relationType }: {
      sourceId: string;
      targetId: string;
      relationType: string;
    }) => api.rejectSuggestion(sourceId, targetId, relationType),
    onSuccess: () => {
      // Invalidate discovery so rejected suggestions don't appear
      queryClient.invalidateQueries({ queryKey: ["discover-relations"] });
    },
  });
}

// Helper to get confidence color
export function getConfidenceColor(confidence: number): string {
  if (confidence >= 0.85) return "text-green-600 bg-green-100 dark:bg-green-900/30";
  if (confidence >= 0.75) return "text-yellow-600 bg-yellow-100 dark:bg-yellow-900/30";
  return "text-orange-600 bg-orange-100 dark:bg-orange-900/30";
}

export function getConfidenceBadgeVariant(confidence: number): "default" | "secondary" | "destructive" | "outline" {
  if (confidence >= 0.85) return "default";
  if (confidence >= 0.75) return "secondary";
  return "outline";
}
