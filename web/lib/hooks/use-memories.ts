"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, Memory } from "../api";

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

export function useStats() {
  return useQuery({
    queryKey: ["stats"],
    queryFn: () => api.getStats(),
  });
}
