"use client";

import { useState, useMemo, useRef, useEffect } from "react";
import { Check, ChevronsUpDown, X, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

interface TagComboboxProps {
  allTags: string[];
  selectedTags: string[];
  onTagToggle: (tag: string) => void;
  onClearAll?: () => void;
  placeholder?: string;
  maxDisplayedPopularTags?: number;
}

export function TagCombobox({
  allTags,
  selectedTags,
  onTagToggle,
  onClearAll,
  placeholder = "Search tags...",
  maxDisplayedPopularTags = 10,
}: TagComboboxProps) {
  const [open, setOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Filter tags based on search query
  const filteredTags = useMemo(() => {
    if (!searchQuery.trim()) {
      // When no search, show selected tags first, then rest
      const unselected = allTags.filter((t) => !selectedTags.includes(t));
      return [...selectedTags, ...unselected].slice(0, 100);
    }
    const query = searchQuery.toLowerCase();
    return allTags
      .filter((tag) => tag.toLowerCase().includes(query))
      .slice(0, 100);
  }, [allTags, searchQuery, selectedTags]);

  // Popular tags (first N that aren't selected)
  const popularTags = useMemo(() => {
    return allTags
      .filter((t) => !selectedTags.includes(t))
      .slice(0, maxDisplayedPopularTags);
  }, [allTags, selectedTags, maxDisplayedPopularTags]);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Handle keyboard navigation
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      setOpen(false);
      setSearchQuery("");
    }
  };

  return (
    <div className="space-y-3">
      {/* Selected tags display */}
      {selectedTags.length > 0 && (
        <div className="flex flex-wrap gap-1.5 items-center">
          <span className="text-sm text-muted-foreground mr-1">Active:</span>
          {selectedTags.map((tag) => (
            <Badge key={tag} variant="default" className="gap-1 pr-1">
              {tag}
              <button
                type="button"
                className="ml-1 rounded-full hover:bg-primary-foreground/20"
                onClick={() => onTagToggle(tag)}
              >
                <X className="h-3 w-3" />
              </button>
            </Badge>
          ))}
          {selectedTags.length > 1 && onClearAll && (
            <Button
              variant="ghost"
              size="sm"
              className="h-6 px-2 text-xs"
              onClick={onClearAll}
            >
              Clear all
            </Button>
          )}
        </div>
      )}

      {/* Combobox container */}
      <div ref={containerRef} className="relative">
        {/* Search input */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            ref={inputRef}
            placeholder={placeholder}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onFocus={() => setOpen(true)}
            onKeyDown={handleKeyDown}
            className="pl-10 pr-10"
          />
          <Button
            variant="ghost"
            size="icon"
            className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7"
            onClick={() => {
              setOpen(!open);
              if (!open) inputRef.current?.focus();
            }}
          >
            <ChevronsUpDown className="h-4 w-4 text-muted-foreground" />
          </Button>
        </div>

        {/* Dropdown */}
        {open && (
          <div className="absolute z-50 mt-1 w-full rounded-md border bg-popover shadow-lg">
            <div className="max-h-64 overflow-y-auto p-2">
              {filteredTags.length === 0 ? (
                <p className="py-6 text-center text-sm text-muted-foreground">
                  No tags found for "{searchQuery}"
                </p>
              ) : (
                <div className="space-y-0.5">
                  {filteredTags.map((tag) => {
                    const isSelected = selectedTags.includes(tag);
                    return (
                      <button
                        key={tag}
                        type="button"
                        className={cn(
                          "flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-sm text-left",
                          "hover:bg-accent hover:text-accent-foreground",
                          isSelected && "bg-accent/50 font-medium"
                        )}
                        onClick={() => {
                          onTagToggle(tag);
                          setSearchQuery("");
                          inputRef.current?.focus();
                        }}
                      >
                        <Check
                          className={cn(
                            "h-4 w-4 shrink-0",
                            isSelected ? "opacity-100" : "opacity-0"
                          )}
                        />
                        <span className="truncate">{tag}</span>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
            {allTags.length > filteredTags.length && (
              <div className="border-t px-3 py-2 text-xs text-muted-foreground">
                Showing {filteredTags.length} of {allTags.length} tags
                {searchQuery && " matching your search"}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Quick access popular tags (when dropdown closed and few/no selections) */}
      {!open && selectedTags.length < 3 && popularTags.length > 0 && (
        <div className="flex flex-wrap gap-1.5 items-center">
          <span className="text-xs text-muted-foreground mr-1">
            Quick filter:
          </span>
          {popularTags.slice(0, 8).map((tag) => (
            <Badge
              key={tag}
              variant="outline"
              className="cursor-pointer hover:bg-accent text-xs"
              onClick={() => onTagToggle(tag)}
            >
              {tag}
            </Badge>
          ))}
          {allTags.length > 8 && (
            <button
              className="text-xs text-muted-foreground hover:text-foreground"
              onClick={() => {
                setOpen(true);
                inputRef.current?.focus();
              }}
            >
              +{allTags.length - 8} more
            </button>
          )}
        </div>
      )}
    </div>
  );
}
