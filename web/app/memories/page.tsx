"use client";

import { useState, useCallback, useMemo } from "react";
import { useRouter } from "next/navigation";
import { Loader2, ChevronLeft, ChevronRight, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { MemoryCard } from "@/components/memories/memory-card";
import { MemoryFilters } from "@/components/memories/memory-filters";
import { MemoryDetail } from "@/components/memories/memory-detail";
import {
  useMemoryList,
  useDeleteMemory,
  useUpdateMemory,
} from "@/lib/hooks/use-memories";
import { Memory } from "@/lib/api";

export default function MemoriesPage() {
  const router = useRouter();

  // Filter state
  const [searchQuery, setSearchQuery] = useState("");
  const [memoryType, setMemoryType] = useState("all");
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [createdAfter, setCreatedAfter] = useState("");
  const [createdBefore, setCreatedBefore] = useState("");
  const [sortBy, setSortBy] = useState("created_at");
  const [sortOrder, setSortOrder] = useState("desc");
  const [offset, setOffset] = useState(0);
  const limit = 20;

  // Selected memory for detail view
  const [selectedMemory, setSelectedMemory] = useState<Memory | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);

  // Confirmation state
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);

  // Build query params
  const queryParams = useMemo(() => ({
    memory_type: memoryType !== "all" ? memoryType : undefined,
    tags: selectedTags.length > 0 ? selectedTags.join(",") : undefined,
    query: searchQuery || undefined,
    created_after: createdAfter || undefined,
    created_before: createdBefore || undefined,
    sort_by: sortBy as "created_at" | "updated_at" | "importance",
    sort_order: sortOrder as "asc" | "desc",
    limit,
    offset,
  }), [searchQuery, memoryType, selectedTags, createdAfter, createdBefore, sortBy, sortOrder, offset]);

  // Queries
  const { data, isLoading, error, refetch } = useMemoryList(queryParams);
  const deleteMutation = useDeleteMemory();
  const updateMutation = useUpdateMemory();

  // Handlers
  const handleTagToggle = useCallback((tag: string) => {
    setSelectedTags((prev) =>
      prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]
    );
    setOffset(0); // Reset pagination
  }, []);

  const handleClearTags = useCallback(() => {
    setSelectedTags([]);
    setOffset(0);
  }, []);

  const handleClearDateFilter = useCallback(() => {
    setCreatedAfter("");
    setCreatedBefore("");
    setOffset(0);
  }, []);

  const handleViewMemory = (memory: Memory) => {
    setSelectedMemory(memory);
    setDetailOpen(true);
  };

  const handleEditMemory = (memory: Memory) => {
    setSelectedMemory(memory);
    setDetailOpen(true);
  };

  const handleDeleteMemory = async (id: string) => {
    if (deleteConfirm !== id) {
      setDeleteConfirm(id);
      return;
    }

    try {
      await deleteMutation.mutateAsync(id);
      setDeleteConfirm(null);
      setDetailOpen(false);
      setSelectedMemory(null);
    } catch (error) {
      console.error("Delete failed:", error);
    }
  };

  const handleSaveMemory = async (updates: {
    content?: string;
    tags?: string[];
    importance?: number;
    metadata?: Record<string, unknown>;
  }) => {
    if (!selectedMemory) return;

    try {
      await updateMutation.mutateAsync({
        id: selectedMemory.id,
        updates,
      });
      // Refresh the memory
      refetch();
    } catch (error) {
      console.error("Update failed:", error);
    }
  };

  const handleViewRelations = (memory: Memory) => {
    router.push(`/graph?center=${memory.id}`);
  };

  // Pagination
  const totalPages = data ? Math.ceil(data.total / limit) : 0;
  const currentPage = Math.floor(offset / limit) + 1;

  return (
    <div className="container py-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">Memory Browser</h1>
        <p className="text-muted-foreground">
          View, search, and manage your memories
        </p>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="pt-6">
          <MemoryFilters
            searchQuery={searchQuery}
            onSearchChange={(q) => { setSearchQuery(q); setOffset(0); }}
            memoryType={memoryType}
            onMemoryTypeChange={(t) => { setMemoryType(t); setOffset(0); }}
            selectedTags={selectedTags}
            onTagToggle={handleTagToggle}
            onClearTags={handleClearTags}
            createdAfter={createdAfter}
            onCreatedAfterChange={(d) => { setCreatedAfter(d); setOffset(0); }}
            createdBefore={createdBefore}
            onCreatedBeforeChange={(d) => { setCreatedBefore(d); setOffset(0); }}
            onClearDateFilter={handleClearDateFilter}
            sortBy={sortBy}
            onSortByChange={setSortBy}
            sortOrder={sortOrder}
            onSortOrderChange={setSortOrder}
          />
        </CardContent>
      </Card>

      {/* Results count */}
      {data && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            Showing {data.memories.length} of {data.total} memories
          </p>
          {totalPages > 1 && (
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setOffset(Math.max(0, offset - limit))}
                disabled={offset === 0}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <span className="text-sm">
                Page {currentPage} of {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setOffset(offset + limit)}
                disabled={!data.has_more}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          )}
        </div>
      )}

      {/* Loading state */}
      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      )}

      {/* Error state */}
      {error && (
        <Card className="border-destructive">
          <CardContent className="py-6">
            <div className="flex items-center gap-2 text-destructive">
              <AlertCircle className="h-5 w-5" />
              <span>Failed to load memories: {error.message}</span>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Memory grid */}
      {data && data.memories.length > 0 && (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {data.memories.map((memory) => (
            <div key={memory.id} className="relative">
              <MemoryCard
                memory={memory}
                onView={() => handleViewMemory(memory)}
                onEdit={() => handleEditMemory(memory)}
                onDelete={() => handleDeleteMemory(memory.id)}
                onViewRelations={() => handleViewRelations(memory)}
              />
              {/* Delete confirmation overlay */}
              {deleteConfirm === memory.id && (
                <div className="absolute inset-0 bg-background/80 backdrop-blur-sm flex items-center justify-center rounded-lg">
                  <div className="text-center space-y-2">
                    <p className="text-sm font-medium">Delete this memory?</p>
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        variant="destructive"
                        onClick={() => handleDeleteMemory(memory.id)}
                        disabled={deleteMutation.isPending}
                      >
                        {deleteMutation.isPending ? "Deleting..." : "Delete"}
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setDeleteConfirm(null)}
                      >
                        Cancel
                      </Button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Empty state */}
      {data && data.memories.length === 0 && (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-muted-foreground">
              No memories found matching your filters.
            </p>
          </CardContent>
        </Card>
      )}

      {/* Memory Detail Dialog */}
      <MemoryDetail
        memory={selectedMemory}
        open={detailOpen}
        onOpenChange={(open) => {
          setDetailOpen(open);
          if (!open) setSelectedMemory(null);
        }}
        onSave={handleSaveMemory}
        onDelete={() => selectedMemory && handleDeleteMemory(selectedMemory.id)}
        onViewRelations={() => selectedMemory && handleViewRelations(selectedMemory)}
        isSaving={updateMutation.isPending}
      />
    </div>
  );
}
