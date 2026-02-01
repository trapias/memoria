"use client";

import { useState } from "react";
import { Trash2, Edit2, Link2, Clock, Star } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Memory } from "@/lib/api";
import { MEMORY_TYPE_COLORS } from "@/lib/hooks/use-memories";
import { cn } from "@/lib/utils";

interface MemoryCardProps {
  memory: Memory;
  onView: () => void;
  onEdit: () => void;
  onDelete: () => void;
  onViewRelations: () => void;
}

export function MemoryCard({
  memory,
  onView,
  onEdit,
  onDelete,
  onViewRelations,
}: MemoryCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const contentPreview = memory.content.length > 200
    ? memory.content.slice(0, 200) + "..."
    : memory.content;

  const formatDate = (dateStr: string) => {
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
      });
    } catch {
      return dateStr;
    }
  };

  return (
    <Card
      className="hover:shadow-md transition-shadow cursor-pointer"
      onClick={onView}
    >
      <CardContent className="p-4">
        {/* Header */}
        <div className="flex items-start justify-between gap-2 mb-3">
          <div className="flex items-center gap-2 flex-wrap">
            <Badge
              variant="secondary"
              className={cn("text-xs", MEMORY_TYPE_COLORS[memory.memory_type])}
            >
              {memory.memory_type}
            </Badge>
            {memory.has_relations && (
              <Badge variant="outline" className="text-xs">
                <Link2 className="h-3 w-3 mr-1" />
                linked
              </Badge>
            )}
          </div>
          <div className="flex gap-1">
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={(e) => { e.stopPropagation(); onEdit(); }}
              title="Edit"
            >
              <Edit2 className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={(e) => { e.stopPropagation(); onViewRelations(); }}
              title="View Relations"
            >
              <Link2 className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 text-destructive hover:text-destructive"
              onClick={(e) => { e.stopPropagation(); onDelete(); }}
              title="Delete"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>

        {/* Content */}
        <p className="text-sm whitespace-pre-wrap mb-3">
          {isExpanded ? memory.content : contentPreview}
        </p>
        {memory.content.length > 200 && (
          <Button
            variant="link"
            size="sm"
            className="p-0 h-auto text-xs"
            onClick={(e) => {
              e.stopPropagation();
              setIsExpanded(!isExpanded);
            }}
          >
            {isExpanded ? "Show less" : "Show more"}
          </Button>
        )}

        {/* Tags */}
        {memory.tags.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-3">
            {memory.tags.slice(0, 5).map((tag) => (
              <Badge key={tag} variant="outline" className="text-xs">
                {tag}
              </Badge>
            ))}
            {memory.tags.length > 5 && (
              <span className="text-xs text-muted-foreground">
                +{memory.tags.length - 5} more
              </span>
            )}
          </div>
        )}

        {/* Footer */}
        <div className="flex items-center justify-between text-xs text-muted-foreground pt-2 border-t">
          <div className="flex items-center gap-1">
            <Clock className="h-3 w-3" />
            {formatDate(memory.created_at)}
          </div>
          <div className="flex items-center gap-1">
            <Star className="h-3 w-3" />
            {Math.round(memory.importance * 100)}%
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
