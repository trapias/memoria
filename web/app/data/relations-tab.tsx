"use client";

import { useState, useCallback } from "react";
import {
  useDataRelationList,
  useDeleteDataRelation,
  useDeleteOrphanedRelations,
  RELATION_TYPE_COLORS,
  formatDateTime,
} from "@/lib/hooks/use-data";
import { MEMORY_TYPE_COLORS } from "@/lib/hooks/use-memories";
import type { MemoryPreviewData, Memory } from "@/lib/api";
import { api } from "@/lib/api";
import { MemoryDetail } from "@/components/memories/memory-detail";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import {
  Trash2,
  Loader2,
  ArrowRight,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  Copy,
  Check,
  Eye,
  X,
} from "lucide-react";

// ─── Constants ───────────────────────────────────────────────────────────────

const RELATION_TYPES = [
  "causes", "fixes", "supports", "opposes", "follows",
  "supersedes", "derives", "part_of", "related",
] as const;

const CREATED_BY_OPTIONS = ["user", "auto", "system"] as const;

const PAGE_SIZE = 20;

const MEMORY_TYPE_BORDER: Record<string, string> = {
  episodic: "border-l-purple-400 dark:border-l-purple-500",
  semantic: "border-l-blue-400 dark:border-l-blue-500",
  procedural: "border-l-green-400 dark:border-l-green-500",
};

const WEIGHT_STYLE = (w: number) =>
  w >= 0.8 ? "text-foreground font-medium" :
  w >= 0.5 ? "text-muted-foreground" :
  "text-muted-foreground/60";

// ─── Memory Preview ──────────────────────────────────────────────────────────

function MemoryPreview({
  memory,
  memoryId,
  expanded,
  onViewMemory,
}: {
  memory: MemoryPreviewData | null;
  memoryId: string;
  expanded: boolean;
  onViewMemory?: (memoryId: string) => void;
}) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(memoryId);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }, [memoryId]);

  if (!memory) {
    return (
      <div className="flex-1 min-w-0 rounded-md border border-dashed border-muted-foreground/30 bg-muted/20 p-3">
        <div className="flex items-center gap-2">
          <span className="text-xs italic text-muted-foreground">
            Deleted memory
          </span>
          <button
            onClick={handleCopy}
            className="text-xs font-mono text-muted-foreground/60 hover:text-foreground transition-colors"
            title="Copy memory ID"
          >
            {copied ? (
              <Check className="h-3 w-3 inline" />
            ) : (
              memoryId.slice(0, 8)
            )}
          </button>
        </div>
      </div>
    );
  }

  const memType = memory.memory_type || "unknown";
  const borderClass = MEMORY_TYPE_BORDER[memType] || "border-l-gray-400";
  const badgeClass = MEMORY_TYPE_COLORS[memType] || "";

  return (
    <div
      className={cn(
        "flex-1 min-w-0 rounded-md border-l-[3px] bg-muted/20 p-3 transition-colors",
        borderClass
      )}
    >
      {/* Header: type badge + ID copy */}
      <div className="flex items-center gap-2 mb-1.5">
        <Badge variant="secondary" className={cn("text-[10px] px-1.5 py-0", badgeClass)}>
          {memType}
        </Badge>
        {expanded && (
          <span className={cn("text-[10px]", WEIGHT_STYLE(memory.importance))}>
            imp: {memory.importance.toFixed(2)}
          </span>
        )}
        <div className="ml-auto flex items-center gap-1">
          {onViewMemory && (
            <button
              onClick={() => onViewMemory(memoryId)}
              className="text-muted-foreground/50 hover:text-foreground transition-colors"
              title="View full memory"
            >
              <Eye className="h-3 w-3" />
            </button>
          )}
          <button
            onClick={handleCopy}
            className="text-muted-foreground/50 hover:text-foreground transition-colors"
            title="Copy memory ID"
          >
            {copied ? (
              <Check className="h-3 w-3" />
            ) : (
              <Copy className="h-3 w-3" />
            )}
          </button>
        </div>
      </div>

      {/* Content */}
      <p
        className={cn(
          "text-sm leading-relaxed",
          expanded ? "" : "line-clamp-2"
        )}
      >
        {memory.content_preview}
      </p>

      {/* Tags */}
      {memory.tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-2">
          {(expanded ? memory.tags : memory.tags.slice(0, 3)).map((tag) => (
            <span
              key={tag}
              className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground"
            >
              #{tag}
            </span>
          ))}
          {!expanded && memory.tags.length > 3 && (
            <span className="text-[10px] text-muted-foreground/60">
              +{memory.tags.length - 3}
            </span>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Relation Card ───────────────────────────────────────────────────────────

function RelationCard({
  relation,
  onDelete,
  onViewMemory,
  isDeleting,
}: {
  relation: {
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
  };
  onDelete: (id: string) => void;
  onViewMemory: (memoryId: string) => void;
  isDeleting: boolean;
}) {
  const [expanded, setExpanded] = useState(false);

  const badgeColor =
    RELATION_TYPE_COLORS[relation.relation_type] ??
    "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200";

  return (
    <div
      className={cn(
        "rounded-lg border bg-card transition-all",
        expanded && "ring-1 ring-primary/20"
      )}
    >
      {/* Main row: Source → Relation → Target */}
      <div className="flex flex-col md:flex-row items-stretch gap-3 p-4">
        {/* Source */}
        <MemoryPreview
          memory={relation.source}
          memoryId={relation.source_id}
          expanded={expanded}
          onViewMemory={onViewMemory}
        />

        {/* Relation indicator */}
        <div className="flex md:flex-col items-center justify-center gap-1 shrink-0 md:w-[100px] py-1">
          <ArrowRight className="h-4 w-4 text-muted-foreground hidden md:block" />
          <ArrowRight className="h-4 w-4 text-muted-foreground md:hidden rotate-90" />
          <Badge variant="secondary" className={cn("text-xs whitespace-nowrap", badgeColor)}>
            {relation.relation_type}
          </Badge>
          <span className={cn("text-xs tabular-nums", WEIGHT_STYLE(relation.weight))}>
            {relation.weight.toFixed(2)}
          </span>
        </div>

        {/* Target */}
        <MemoryPreview
          memory={relation.target}
          memoryId={relation.target_id}
          expanded={expanded}
          onViewMemory={onViewMemory}
        />
      </div>

      {/* Metadata row */}
      <div className="flex items-center gap-3 px-4 pb-3 text-xs text-muted-foreground">
        <Badge variant="outline" className="text-[10px] px-1.5 py-0">
          {relation.created_by}
        </Badge>
        <span>{formatDateTime(relation.created_at)}</span>

        {expanded && Object.keys(relation.metadata).length > 0 && (
          <span className="font-mono text-[10px] truncate max-w-[200px]" title={JSON.stringify(relation.metadata)}>
            meta: {JSON.stringify(relation.metadata)}
          </span>
        )}

        <div className="flex items-center gap-1 ml-auto">
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={() => setExpanded((e) => !e)}
            title={expanded ? "Collapse" : "Expand"}
          >
            {expanded ? (
              <ChevronUp className="h-4 w-4" />
            ) : (
              <ChevronDown className="h-4 w-4" />
            )}
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 text-muted-foreground hover:text-destructive"
            onClick={() => onDelete(relation.id)}
            disabled={isDeleting}
            title="Delete relation"
          >
            {isDeleting ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Trash2 className="h-4 w-4" />
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}

// ─── Main Component ──────────────────────────────────────────────────────────

export function RelationsTab() {
  const [relationType, setRelationType] = useState("");
  const [createdBy, setCreatedBy] = useState("");
  const [memoryId, setMemoryId] = useState("");
  const [page, setPage] = useState(1);

  const { data, isLoading, isError, error } = useDataRelationList({
    relation_type: relationType || undefined,
    created_by: createdBy || undefined,
    memory_id: memoryId || undefined,
    page,
    page_size: PAGE_SIZE,
  });

  const deleteMutation = useDeleteDataRelation();
  const orphanMutation = useDeleteOrphanedRelations();
  const [orphanResult, setOrphanResult] = useState<number | null>(null);

  // Memory detail modal
  const [detailMemory, setDetailMemory] = useState<Memory | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);

  const handleViewMemory = useCallback(async (memoryId: string) => {
    try {
      const memory = await api.getMemory(memoryId);
      setDetailMemory(memory);
      setDetailOpen(true);
    } catch (error) {
      console.error("Failed to load memory:", error);
    }
  }, []);

  const handleCleanOrphaned = useCallback(async () => {
    if (
      !window.confirm(
        "Delete all relations where source or target memory no longer exists?\nThis cannot be undone."
      )
    )
      return;
    try {
      const res = await orphanMutation.mutateAsync();
      setOrphanResult(res.deleted);
      setTimeout(() => setOrphanResult(null), 5000);
    } catch {
      // mutation error handled by react-query
    }
  }, [orphanMutation]);

  const handleDelete = useCallback(
    (id: string) => {
      if (window.confirm("Delete this relation? This cannot be undone.")) {
        deleteMutation.mutate(id);
      }
    },
    [deleteMutation]
  );

  const hasFilters = !!(relationType || createdBy || memoryId);

  const resetFilters = useCallback(() => {
    setRelationType("");
    setCreatedBy("");
    setMemoryId("");
    setPage(1);
  }, []);

  const relations = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = data?.pages ?? 1;

  return (
    <div className="space-y-4">
      {/* Filters bar */}
      <div className="flex flex-wrap items-end gap-3">
        <div className="space-y-1">
          <Label className="text-xs text-muted-foreground">Type</Label>
          <Select
            value={relationType || "all"}
            onValueChange={(v) => {
              setRelationType(v === "all" ? "" : v);
              setPage(1);
            }}
          >
            <SelectTrigger className="w-[160px]">
              <SelectValue placeholder="All types" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All types</SelectItem>
              {RELATION_TYPES.map((type) => (
                <SelectItem key={type} value={type}>
                  {type}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1">
          <Label className="text-xs text-muted-foreground">Created by</Label>
          <Select
            value={createdBy || "all"}
            onValueChange={(v) => {
              setCreatedBy(v === "all" ? "" : v);
              setPage(1);
            }}
          >
            <SelectTrigger className="w-[140px]">
              <SelectValue placeholder="All creators" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All creators</SelectItem>
              {CREATED_BY_OPTIONS.map((opt) => (
                <SelectItem key={opt} value={opt}>
                  {opt}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1">
          <Label className="text-xs text-muted-foreground">Memory ID</Label>
          <Input
            placeholder="Filter by UUID..."
            value={memoryId}
            onChange={(e) => {
              setMemoryId(e.target.value);
              setPage(1);
            }}
            className="w-[260px]"
          />
        </div>

        {hasFilters && (
          <Button variant="ghost" size="sm" onClick={resetFilters} className="text-muted-foreground">
            <X className="h-4 w-4 mr-1" />
            Reset
          </Button>
        )}

        <div className="flex items-center gap-2 ml-auto">
          {orphanResult !== null && (
            <span className="text-sm text-muted-foreground">
              {orphanResult === 0
                ? "No orphaned relations found"
                : `Deleted ${orphanResult} orphaned relation${orphanResult !== 1 ? "s" : ""}`}
            </span>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={handleCleanOrphaned}
            disabled={orphanMutation.isPending}
            className="text-destructive border-destructive/30 hover:bg-destructive/10"
          >
            {orphanMutation.isPending ? (
              <Loader2 className="h-4 w-4 mr-1 animate-spin" />
            ) : (
              <Trash2 className="h-4 w-4 mr-1" />
            )}
            Clean orphaned
          </Button>
        </div>
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          <span className="ml-2 text-sm text-muted-foreground">Loading relations...</span>
        </div>
      )}

      {/* Error */}
      {isError && (
        <div className="rounded-md border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
          Failed to load relations: {(error as Error)?.message ?? "Unknown error"}
        </div>
      )}

      {/* Empty */}
      {!isLoading && !isError && relations.length === 0 && (
        <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
          <p className="text-sm">No relations found.</p>
          {hasFilters && (
            <p className="mt-1 text-xs">
              Try adjusting the filters to see more results.
            </p>
          )}
        </div>
      )}

      {/* Relation cards */}
      {!isLoading && !isError && relations.length > 0 && (
        <>
          <div className="space-y-3">
            {relations.map((relation) => (
              <RelationCard
                key={relation.id}
                relation={relation}
                onDelete={handleDelete}
                onViewMemory={handleViewMemory}
                isDeleting={
                  deleteMutation.isPending &&
                  deleteMutation.variables === relation.id
                }
              />
            ))}
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">
              {total} relation{total !== 1 ? "s" : ""}
            </span>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
              >
                <ChevronLeft className="mr-1 h-4 w-4" />
                Previous
              </Button>
              <span className="text-sm text-muted-foreground">
                Page {page} of {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
              >
                Next
                <ChevronRight className="ml-1 h-4 w-4" />
              </Button>
            </div>
          </div>
        </>
      )}

      {/* Memory Detail Modal */}
      <MemoryDetail
        memory={detailMemory}
        open={detailOpen}
        onOpenChange={setDetailOpen}
        onSave={() => {}}
        onDelete={() => {}}
        onViewRelations={() => {}}
      />
    </div>
  );
}
