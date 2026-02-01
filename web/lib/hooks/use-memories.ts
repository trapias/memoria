"use client";

import { useQuery, useMutation, useQueryClient, useInfiniteQuery } from "@tanstack/react-query";
import { api, Memory, MemoryListResponse, ListMemoriesParams, ConsolidationRequest } from "../api";

export function useMemoryList(params: ListMemoriesParams = {}) {
  return useQuery({
    queryKey: ["memories", "list", params],
    queryFn: () => api.listMemories(params),
    staleTime: 30000, // 30 seconds
  });
}

export function useInfiniteMemoryList(params: Omit<ListMemoriesParams, "offset">) {
  return useInfiniteQuery({
    queryKey: ["memories", "infinite", params],
    queryFn: ({ pageParam = 0 }) =>
      api.listMemories({ ...params, offset: pageParam, limit: params.limit || 20 }),
    getNextPageParam: (lastPage) =>
      lastPage.has_more ? lastPage.offset + lastPage.limit : undefined,
    initialPageParam: 0,
  });
}

export function useSearchMemories(
  query: string,
  memoryType?: string,
  limit: number = 10
) {
  return useQuery({
    queryKey: ["memories", "search", query, memoryType, limit],
    queryFn: () => api.searchMemories(query, memoryType, limit),
    enabled: query.length > 0,
  });
}

export function useMemory(id: string | null) {
  return useQuery({
    queryKey: ["memory", id],
    queryFn: () => api.getMemory(id!),
    enabled: !!id,
  });
}

export function useTags() {
  return useQuery({
    queryKey: ["memories", "tags"],
    queryFn: () => api.getAllTags(),
    staleTime: 60000, // 1 minute
  });
}

export function useStats() {
  return useQuery({
    queryKey: ["stats"],
    queryFn: () => api.getStats(),
  });
}

export function useDeleteMemory() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => api.deleteMemory(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["memories"] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
      queryClient.invalidateQueries({ queryKey: ["subgraph"] });
    },
  });
}

export function useUpdateMemory() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      id,
      updates,
    }: {
      id: string;
      updates: { content?: string; tags?: string[]; importance?: number };
    }) => api.updateMemory(id, updates),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["memories"] });
      queryClient.invalidateQueries({ queryKey: ["memory", variables.id] });
    },
  });
}

export function useConsolidateMemories() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: ConsolidationRequest) => api.consolidateMemories(request),
    onSuccess: (result) => {
      // Only invalidate if not a preview (actual operation was performed)
      if (!result.is_preview) {
        queryClient.invalidateQueries({ queryKey: ["memories"] });
        queryClient.invalidateQueries({ queryKey: ["stats"] });
      }
    },
  });
}

// Memory type colors
export const MEMORY_TYPE_COLORS: Record<string, string> = {
  episodic: "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400",
  semantic: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
  procedural: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
};

export const MEMORY_TYPE_DESCRIPTIONS: Record<string, string> = {
  episodic: "Events, conversations, time-bound memories",
  semantic: "Facts, knowledge, concepts",
  procedural: "Procedures, workflows, learned skills",
};
