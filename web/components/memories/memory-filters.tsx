"use client";

import { Search, X } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useTags, MEMORY_TYPE_COLORS } from "@/lib/hooks/use-memories";
import { cn } from "@/lib/utils";

interface MemoryFiltersProps {
  searchQuery: string;
  onSearchChange: (query: string) => void;
  memoryType: string;
  onMemoryTypeChange: (type: string) => void;
  selectedTags: string[];
  onTagToggle: (tag: string) => void;
  sortBy: string;
  onSortByChange: (sortBy: string) => void;
  sortOrder: string;
  onSortOrderChange: (order: string) => void;
}

export function MemoryFilters({
  searchQuery,
  onSearchChange,
  memoryType,
  onMemoryTypeChange,
  selectedTags,
  onTagToggle,
  sortBy,
  onSortByChange,
  sortOrder,
  onSortOrderChange,
}: MemoryFiltersProps) {
  const { data: allTags = [] } = useTags();

  return (
    <div className="space-y-4">
      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Search memories..."
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          className="pl-10"
        />
        {searchQuery && (
          <Button
            variant="ghost"
            size="icon"
            className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7"
            onClick={() => onSearchChange("")}
          >
            <X className="h-4 w-4" />
          </Button>
        )}
      </div>

      {/* Type and Sort Row */}
      <div className="flex flex-wrap gap-2">
        {/* Memory Type Filter */}
        <Select value={memoryType} onValueChange={onMemoryTypeChange}>
          <SelectTrigger className="w-[140px]">
            <SelectValue placeholder="All Types" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Types</SelectItem>
            <SelectItem value="episodic">
              <span className="flex items-center gap-2">
                <span className={cn("w-2 h-2 rounded-full", "bg-purple-500")} />
                Episodic
              </span>
            </SelectItem>
            <SelectItem value="semantic">
              <span className="flex items-center gap-2">
                <span className={cn("w-2 h-2 rounded-full", "bg-blue-500")} />
                Semantic
              </span>
            </SelectItem>
            <SelectItem value="procedural">
              <span className="flex items-center gap-2">
                <span className={cn("w-2 h-2 rounded-full", "bg-green-500")} />
                Procedural
              </span>
            </SelectItem>
          </SelectContent>
        </Select>

        {/* Sort By */}
        <Select value={sortBy} onValueChange={onSortByChange}>
          <SelectTrigger className="w-[140px]">
            <SelectValue placeholder="Sort by" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="created_at">Created</SelectItem>
            <SelectItem value="updated_at">Updated</SelectItem>
            <SelectItem value="importance">Importance</SelectItem>
          </SelectContent>
        </Select>

        {/* Sort Order */}
        <Select value={sortOrder} onValueChange={onSortOrderChange}>
          <SelectTrigger className="w-[100px]">
            <SelectValue placeholder="Order" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="desc">Newest</SelectItem>
            <SelectItem value="asc">Oldest</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Tags */}
      {allTags.length > 0 && (
        <div className="space-y-2">
          <p className="text-sm text-muted-foreground">Filter by tags:</p>
          <div className="flex flex-wrap gap-1.5 max-h-32 overflow-y-auto">
            {allTags.slice(0, 30).map((tag) => {
              const isSelected = selectedTags.includes(tag);
              return (
                <Badge
                  key={tag}
                  variant={isSelected ? "default" : "outline"}
                  className={cn(
                    "cursor-pointer transition-colors",
                    isSelected && "bg-primary"
                  )}
                  onClick={() => onTagToggle(tag)}
                >
                  {tag}
                </Badge>
              );
            })}
            {allTags.length > 30 && (
              <span className="text-xs text-muted-foreground self-center">
                +{allTags.length - 30} more
              </span>
            )}
          </div>
        </div>
      )}

      {/* Active Filters */}
      {(selectedTags.length > 0 || memoryType !== "all") && (
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Active:</span>
          {memoryType !== "all" && (
            <Badge variant="secondary" className="gap-1">
              {memoryType}
              <X
                className="h-3 w-3 cursor-pointer"
                onClick={() => onMemoryTypeChange("all")}
              />
            </Badge>
          )}
          {selectedTags.map((tag) => (
            <Badge key={tag} variant="secondary" className="gap-1">
              {tag}
              <X
                className="h-3 w-3 cursor-pointer"
                onClick={() => onTagToggle(tag)}
              />
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}
