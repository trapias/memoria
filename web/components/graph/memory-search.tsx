"use client";

import { useState, useCallback } from "react";
import { useSearchMemories } from "@/lib/hooks/use-memories";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Search, Brain } from "lucide-react";

interface MemorySearchProps {
  onSelect: (memoryId: string) => void;
}

export function MemorySearch({ onSelect }: MemorySearchProps) {
  const [query, setQuery] = useState("");
  const [isOpen, setIsOpen] = useState(false);

  const { data: results, isLoading } = useSearchMemories(query, undefined, 10);

  const handleSelect = useCallback(
    (id: string) => {
      onSelect(id);
      setQuery("");
      setIsOpen(false);
    },
    [onSelect]
  );

  return (
    <div className="relative">
      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setIsOpen(true);
          }}
          onFocus={() => setIsOpen(true)}
          placeholder="Search memories to explore..."
          className="pl-10"
        />
      </div>

      {/* Results dropdown */}
      {isOpen && query.length > 0 && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-background border rounded-lg shadow-lg z-50 max-h-80 overflow-y-auto">
          {isLoading ? (
            <div className="p-4 text-center text-muted-foreground text-sm">
              Searching...
            </div>
          ) : results && results.length > 0 ? (
            <div className="py-1">
              {results.map((memory) => (
                <button
                  key={memory.id}
                  onClick={() => handleSelect(memory.id)}
                  className="w-full px-4 py-3 text-left hover:bg-muted transition-colors"
                >
                  <div className="flex items-start gap-3">
                    <Brain className="h-4 w-4 mt-0.5 text-muted-foreground shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm line-clamp-2">{memory.content}</p>
                      <div className="flex items-center gap-2 mt-1">
                        <Badge variant="outline" className="text-xs">
                          {memory.memory_type}
                        </Badge>
                        {memory.tags.slice(0, 3).map((tag) => (
                          <Badge
                            key={tag}
                            variant="secondary"
                            className="text-xs"
                          >
                            {tag}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          ) : (
            <div className="p-4 text-center text-muted-foreground text-sm">
              No memories found
            </div>
          )}
        </div>
      )}

      {/* Click outside to close */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40"
          onClick={() => setIsOpen(false)}
        />
      )}
    </div>
  );
}
