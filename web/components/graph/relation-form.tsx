"use client";

import { useState, useMemo, useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useCreateRelation, RELATION_COLORS, RELATION_DESCRIPTIONS } from "@/lib/hooks/use-graph";
import { useMemoryList, useTags, MEMORY_TYPE_COLORS } from "@/lib/hooks/use-memories";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Badge } from "@/components/ui/badge";
import { Search, X, Filter, ChevronDown, ChevronUp, Tag, Brain } from "lucide-react";

const formSchema = z.object({
  targetId: z.string().min(1, "Target memory is required"),
  relationType: z.string().min(1, "Relation type is required"),
  weight: z.number().min(0).max(1),
});

type FormData = z.infer<typeof formSchema>;

interface RelationFormProps {
  sourceId: string;
  sourceLabel: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: () => void;
}

const RELATION_TYPES = Object.keys(RELATION_COLORS);
const MEMORY_TYPES = ["episodic", "semantic", "procedural"] as const;

export function RelationForm({
  sourceId,
  sourceLabel,
  open,
  onOpenChange,
  onSuccess,
}: RelationFormProps) {
  // Search and filter state
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [selectedMemoryType, setSelectedMemoryType] = useState<string | undefined>(undefined);
  const [showFilters, setShowFilters] = useState(false);
  const [tagSearch, setTagSearch] = useState("");

  // Fetch available tags
  const { data: allTags = [] } = useTags();

  // Filtered tags for tag selector
  const filteredTags = useMemo(() => {
    if (!tagSearch) return allTags.slice(0, 20); // Show first 20 when no search
    return allTags
      .filter(tag => tag.toLowerCase().includes(tagSearch.toLowerCase()))
      .slice(0, 20);
  }, [allTags, tagSearch]);

  // Build query params for memory list
  const queryParams = useMemo(() => ({
    query: searchQuery || undefined,
    tags: selectedTags.length > 0 ? selectedTags.join(",") : undefined,
    memory_type: selectedMemoryType,
    limit: 10,
    sort_by: "updated_at" as const,
    sort_order: "desc" as const,
  }), [searchQuery, selectedTags, selectedMemoryType]);

  // Search memories with combined filters
  const { data: memoryData, isLoading } = useMemoryList(
    (searchQuery.length > 0 || selectedTags.length > 0 || selectedMemoryType)
      ? queryParams
      : { limit: 0 } // Don't fetch until filters are applied
  );

  const searchResults = memoryData?.memories?.filter(m => m.id !== sourceId) ?? [];

  const createMutation = useCreateRelation();

  const {
    handleSubmit,
    setValue,
    watch,
    reset,
    formState: { errors },
  } = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      targetId: "",
      relationType: "related",
      weight: 0.8,
    },
  });

  const selectedTargetId = watch("targetId");
  const selectedRelationType = watch("relationType");
  const weight = watch("weight");

  // Find selected memory for display
  const selectedMemory = searchResults.find(m => m.id === selectedTargetId);

  // Reset filters when dialog closes
  useEffect(() => {
    if (!open) {
      setSearchQuery("");
      setSelectedTags([]);
      setSelectedMemoryType(undefined);
      setShowFilters(false);
      setTagSearch("");
      reset();
    }
  }, [open, reset]);

  const onSubmit = async (data: FormData) => {
    await createMutation.mutateAsync({
      sourceId,
      targetId: data.targetId,
      relationType: data.relationType,
      weight: data.weight,
    });
    onOpenChange(false);
    onSuccess();
  };

  const handleTargetSelect = (id: string) => {
    setValue("targetId", id);
  };

  const toggleTag = (tag: string) => {
    setSelectedTags(prev =>
      prev.includes(tag)
        ? prev.filter(t => t !== tag)
        : [...prev, tag]
    );
  };

  const clearFilters = () => {
    setSelectedTags([]);
    setSelectedMemoryType(undefined);
    setSearchQuery("");
    setTagSearch("");
  };

  const hasActiveFilters = selectedTags.length > 0 || selectedMemoryType || searchQuery.length > 0;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px] max-h-[90vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle>Create Relation</DialogTitle>
          <DialogDescription className="truncate">
            From: &quot;{sourceLabel}&quot;
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col flex-1 overflow-hidden space-y-4">
          {/* Target Memory Search Section */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <Label>Target Memory</Label>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setShowFilters(!showFilters)}
                className="h-7 gap-1 text-xs"
              >
                <Filter className="h-3 w-3" />
                Filters
                {hasActiveFilters && (
                  <Badge variant="secondary" className="ml-1 h-4 px-1 text-xs">
                    {(selectedTags.length > 0 ? 1 : 0) + (selectedMemoryType ? 1 : 0) + (searchQuery ? 1 : 0)}
                  </Badge>
                )}
                {showFilters ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
              </Button>
            </div>

            {/* Search Input */}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search by content..."
                className="pl-10 pr-8"
              />
              {searchQuery && (
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="absolute right-1 top-1/2 -translate-y-1/2 h-6 w-6"
                  onClick={() => setSearchQuery("")}
                >
                  <X className="h-3 w-3" />
                </Button>
              )}
            </div>

            {/* Filters Panel */}
            {showFilters && (
              <div className="border rounded-lg p-3 space-y-3 bg-muted/30">
                {/* Memory Type Filter */}
                <div>
                  <Label className="text-xs text-muted-foreground mb-2 block">Memory Type</Label>
                  <div className="flex gap-2">
                    {MEMORY_TYPES.map((type) => (
                      <Button
                        key={type}
                        type="button"
                        variant={selectedMemoryType === type ? "default" : "outline"}
                        size="sm"
                        className="h-7 text-xs"
                        onClick={() => setSelectedMemoryType(
                          selectedMemoryType === type ? undefined : type
                        )}
                      >
                        {type}
                      </Button>
                    ))}
                  </div>
                </div>

                {/* Tag Filter */}
                <div>
                  <Label className="text-xs text-muted-foreground mb-2 block">
                    <Tag className="h-3 w-3 inline mr-1" />
                    Filter by Tags
                  </Label>

                  {/* Selected Tags */}
                  {selectedTags.length > 0 && (
                    <div className="flex flex-wrap gap-1 mb-2">
                      {selectedTags.map((tag) => (
                        <Badge
                          key={tag}
                          variant="default"
                          className="cursor-pointer gap-1 pr-1"
                          onClick={() => toggleTag(tag)}
                        >
                          {tag}
                          <X className="h-3 w-3" />
                        </Badge>
                      ))}
                    </div>
                  )}

                  {/* Tag Search */}
                  <Input
                    value={tagSearch}
                    onChange={(e) => setTagSearch(e.target.value)}
                    placeholder="Search tags..."
                    className="h-8 text-sm mb-2"
                  />

                  {/* Available Tags */}
                  <div className="flex flex-wrap gap-1 max-h-24 overflow-y-auto">
                    {filteredTags
                      .filter(tag => !selectedTags.includes(tag))
                      .map((tag) => (
                        <Badge
                          key={tag}
                          variant="outline"
                          className="cursor-pointer hover:bg-accent"
                          onClick={() => toggleTag(tag)}
                        >
                          {tag}
                        </Badge>
                      ))}
                    {filteredTags.length === 0 && (
                      <p className="text-xs text-muted-foreground">No tags found</p>
                    )}
                  </div>
                </div>

                {/* Clear Filters */}
                {hasActiveFilters && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={clearFilters}
                    className="h-7 text-xs w-full"
                  >
                    Clear all filters
                  </Button>
                )}
              </div>
            )}

            {/* Search Results */}
            {(searchQuery.length > 0 || selectedTags.length > 0 || selectedMemoryType) && (
              <div className="border rounded-lg max-h-48 overflow-y-auto">
                {isLoading ? (
                  <p className="text-sm text-muted-foreground p-3 text-center">Searching...</p>
                ) : searchResults.length === 0 ? (
                  <p className="text-sm text-muted-foreground p-3 text-center">No memories found</p>
                ) : (
                  searchResults.map((memory) => (
                    <button
                      key={memory.id}
                      type="button"
                      onClick={() => handleTargetSelect(memory.id)}
                      className={`w-full px-3 py-2 text-left text-sm hover:bg-muted transition-colors border-b last:border-b-0 ${
                        selectedTargetId === memory.id ? "bg-primary/10" : ""
                      }`}
                    >
                      <div className="flex items-start gap-2">
                        <Brain className="h-4 w-4 mt-0.5 shrink-0 text-muted-foreground" />
                        <div className="flex-1 min-w-0">
                          <p className="line-clamp-2">{memory.content}</p>
                          <div className="flex items-center gap-2 mt-1 flex-wrap">
                            <Badge variant="outline" className={`text-xs ${MEMORY_TYPE_COLORS[memory.memory_type] || ""}`}>
                              {memory.memory_type}
                            </Badge>
                            {memory.tags.slice(0, 3).map((tag) => (
                              <Badge key={tag} variant="secondary" className="text-xs">
                                {tag}
                              </Badge>
                            ))}
                            {memory.tags.length > 3 && (
                              <span className="text-xs text-muted-foreground">
                                +{memory.tags.length - 3} more
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    </button>
                  ))
                )}
              </div>
            )}

            {/* Selected Target Display */}
            {selectedTargetId && (
              <div className="p-2 rounded-lg border bg-primary/5 border-primary/20">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted-foreground">Selected target:</span>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="h-5 w-5"
                    onClick={() => setValue("targetId", "")}
                  >
                    <X className="h-3 w-3" />
                  </Button>
                </div>
                <p className="text-sm line-clamp-1 mt-1">
                  {selectedMemory?.content || `ID: ${selectedTargetId.slice(0, 8)}...`}
                </p>
              </div>
            )}

            {errors.targetId && (
              <p className="text-sm text-destructive">{errors.targetId.message}</p>
            )}
          </div>

          {/* Relation Type */}
          <div className="space-y-2">
            <Label>Relation Type</Label>
            <div className="grid grid-cols-3 gap-2">
              {RELATION_TYPES.map((type) => (
                <button
                  key={type}
                  type="button"
                  onClick={() => setValue("relationType", type)}
                  className={`p-2 text-sm rounded-lg border transition-colors ${
                    selectedRelationType === type
                      ? "border-primary bg-primary/10"
                      : "border-muted hover:border-primary/50"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <div
                      className="w-2 h-2 rounded-full"
                      style={{ backgroundColor: RELATION_COLORS[type] }}
                    />
                    <span>{type}</span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1 text-left">
                    {RELATION_DESCRIPTIONS[type]}
                  </p>
                </button>
              ))}
            </div>
          </div>

          {/* Weight */}
          <div className="space-y-2">
            <div className="flex justify-between">
              <Label>Strength</Label>
              <span className="text-sm text-muted-foreground">
                {weight.toFixed(1)}
              </span>
            </div>
            <Slider
              value={[weight]}
              onValueChange={([v]) => setValue("weight", v)}
              min={0}
              max={1}
              step={0.1}
            />
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>Weak</span>
              <span>Strong</span>
            </div>
          </div>

          <DialogFooter className="mt-auto pt-4">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={createMutation.isPending || !selectedTargetId}>
              {createMutation.isPending ? "Creating..." : "Create Relation"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
