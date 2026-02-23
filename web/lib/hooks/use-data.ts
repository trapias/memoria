"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  api,
  type SessionListResponse,
  type SessionSummary,
  type WorkSessionResponse,
  type SessionCreateBody,
  type SessionUpdateBody,
  type DataClient,
  type DataProject,
  type DataRelationListResponse,
} from "@/lib/api";

// ─── Sessions ────────────────────────────────────────────────────────────────

export function useSessionList(params: {
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
} = {}) {
  return useQuery({
    queryKey: ["data", "sessions", params],
    queryFn: () => api.listSessions(params),
    staleTime: 30000,
  });
}

export function useSessionSummary(params: {
  date_from?: string;
  date_to?: string;
  client_id?: string;
} = {}) {
  return useQuery({
    queryKey: ["data", "sessions", "summary", params],
    queryFn: () => api.getSessionsSummary(params),
    staleTime: 30000,
  });
}

export function useCreateSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: SessionCreateBody) => api.createSession(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["data", "sessions"] });
    },
  });
}

export function useUpdateSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: SessionUpdateBody }) =>
      api.updateSession(id, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["data", "sessions"] });
    },
  });
}

export function useDeleteSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteSession(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["data", "sessions"] });
    },
  });
}

// ─── Clients ─────────────────────────────────────────────────────────────────

export function useClientList() {
  return useQuery({
    queryKey: ["data", "clients"],
    queryFn: () => api.listClients(),
    staleTime: 30000,
  });
}

export function useCreateClient() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; metadata?: Record<string, unknown> }) =>
      api.createClient(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["data", "clients"] });
    },
  });
}

export function useUpdateClient() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      body,
    }: {
      id: string;
      body: { name?: string; metadata?: Record<string, unknown> };
    }) => api.updateClient(id, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["data", "clients"] });
    },
  });
}

export function useDeleteClient() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteClient(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["data", "clients"] });
      queryClient.invalidateQueries({ queryKey: ["data", "projects"] });
    },
  });
}

// ─── Projects ────────────────────────────────────────────────────────────────

export function useProjectList(clientId?: string) {
  return useQuery({
    queryKey: ["data", "projects", clientId],
    queryFn: () => api.listProjects(clientId),
    staleTime: 30000,
  });
}

export function useCreateProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      name: string;
      client_id?: string;
      repo?: string;
      metadata?: Record<string, unknown>;
    }) => api.createProject(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["data", "projects"] });
    },
  });
}

export function useUpdateProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      body,
    }: {
      id: string;
      body: {
        name?: string;
        client_id?: string;
        repo?: string;
        metadata?: Record<string, unknown>;
      };
    }) => api.updateProject(id, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["data", "projects"] });
    },
  });
}

export function useDeleteProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteProject(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["data", "projects"] });
    },
  });
}

// ─── Relations ───────────────────────────────────────────────────────────────

export function useDataRelationList(params: {
  relation_type?: string;
  created_by?: string;
  memory_id?: string;
  page?: number;
  page_size?: number;
} = {}) {
  return useQuery({
    queryKey: ["data", "relations", params],
    queryFn: () => api.listDataRelations(params),
    staleTime: 30000,
  });
}

export function useDeleteDataRelation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteDataRelation(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["data", "relations"] });
    },
  });
}

export function useDeleteOrphanedRelations() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.deleteOrphanedRelations(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["data", "relations"] });
    },
  });
}

// ─── Constants ───────────────────────────────────────────────────────────────

export const SESSION_CATEGORIES = [
  "coding",
  "review",
  "meeting",
  "support",
  "research",
  "documentation",
  "devops",
  "other",
] as const;

export const CATEGORY_COLORS: Record<string, string> = {
  coding: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
  review: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200",
  meeting: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
  support: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  research: "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200",
  documentation: "bg-cyan-100 text-cyan-800 dark:bg-cyan-900 dark:text-cyan-200",
  devops: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
  other: "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200",
};

export const RELATION_TYPE_COLORS: Record<string, string> = {
  causes: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
  fixes: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  supports: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
  opposes: "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200",
  follows: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200",
  supersedes: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
  derives: "bg-cyan-100 text-cyan-800 dark:bg-cyan-900 dark:text-cyan-200",
  part_of: "bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-200",
  related: "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200",
};

// ─── Utilities ───────────────────────────────────────────────────────────────

export function formatDuration(minutes: number | null | undefined): string {
  if (!minutes) return "—";
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (h === 0) return `${m}m`;
  return `${h}h ${m}m`;
}

export function formatDate(isoString: string): string {
  if (!isoString) return "—";
  const d = new Date(isoString);
  return d.toLocaleDateString("it-IT", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
}

export function formatDateTime(isoString: string): string {
  if (!isoString) return "—";
  const d = new Date(isoString);
  return d.toLocaleString("it-IT", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}
