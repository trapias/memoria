"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, BackupStats, ImportResult } from "../api";

export function useBackupStats() {
  return useQuery({
    queryKey: ["backup", "stats"],
    queryFn: () => api.getBackupStats(),
  });
}

export function useExportBackup() {
  return useMutation({
    mutationFn: async (options: {
      include_graph?: boolean;
      memory_types?: string[];
    }) => {
      const blob = await api.exportBackup(options);

      // Trigger download
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `memoria_backup_${new Date().toISOString().slice(0, 10)}.json`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      return blob;
    },
  });
}

export function useImportBackup() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      file,
      skipExisting = true,
    }: {
      file: File;
      skipExisting?: boolean;
    }): Promise<ImportResult> => {
      return api.importBackup(file, skipExisting);
    },
    onSuccess: () => {
      // Invalidate all queries after import
      queryClient.invalidateQueries({ queryKey: ["memories"] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
      queryClient.invalidateQueries({ queryKey: ["subgraph"] });
      queryClient.invalidateQueries({ queryKey: ["backup"] });
    },
  });
}
