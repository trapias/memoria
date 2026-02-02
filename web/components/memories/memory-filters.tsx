"use client";

import { Search, X } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useTags } from "@/lib/hooks/use-memories";
import { cn } from "@/lib/utils";
import { TagCombobox } from "./tag-combobox";
import { DateRangeFilter } from "./date-range-filter";

interface MemoryFiltersProps {
  // Search
  searchQuery: string;
  onSearchChange: (query: string) => void;
  // Memory type
  memoryType: string;
  onMemoryTypeChange: (type: string) => void;
  // Tags
  selectedTags: string[];
  onTagToggle: (tag: string) => void;
  onClearTags?: () => void;
  // Date range
  createdAfter?: string;
  onCreatedAfterChange?: (date: string) => void;
  createdBefore?: string;
  onCreatedBeforeChange?: (date: string) => void;
  onClearDateFilter?: () => void;
  // Sort
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
  onClearTags,
  createdAfter = "",
  onCreatedAfterChange,
  createdBefore = "",
  onCreatedBeforeChange,
  onClearDateFilter,
  sortBy,
  onSortByChange,
  sortOrder,
  onSortOrderChange,
}: MemoryFiltersProps) {
  const { data: allTags = [] } = useTags();

  const hasDateFilterSupport = onCreatedAfterChange && onCreatedBeforeChange && onClearDateFilter;

  return (
    <div className="space-y-4">
      {/* Row 1: Search */}
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

      {/* Row 2: Type, Date, Sort */}
      <div className="flex flex-wrap gap-2 items-start">
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

        {/* Date Range Filter */}
        {hasDateFilterSupport && (
          <DateRangeFilter
            createdAfter={createdAfter}
            createdBefore={createdBefore}
            onCreatedAfterChange={onCreatedAfterChange}
            onCreatedBeforeChange={onCreatedBeforeChange}
            onClear={onClearDateFilter}
          />
        )}

        {/* Spacer */}
        <div className="flex-1" />

        {/* Sort By */}
        <Select value={sortBy} onValueChange={onSortByChange}>
          <SelectTrigger className="w-[120px]">
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

      {/* Row 3: Tag Combobox */}
      {allTags.length > 0 && (
        <div className="border-t pt-4">
          <TagCombobox
            allTags={allTags}
            selectedTags={selectedTags}
            onTagToggle={onTagToggle}
            onClearAll={onClearTags}
            placeholder="Search and filter by tags..."
          />
        </div>
      )}
    </div>
  );
}
