"use client";

import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { RELATION_COLORS, RELATION_DESCRIPTIONS } from "@/lib/hooks/use-graph";

interface GraphControlsProps {
  depth: number;
  onDepthChange: (depth: number) => void;
  relationFilter: string | null;
  onRelationFilterChange: (filter: string | null) => void;
}

const RELATION_TYPES = Object.keys(RELATION_COLORS);

export function GraphControls({
  depth,
  onDepthChange,
  relationFilter,
  onRelationFilterChange,
}: GraphControlsProps) {
  return (
    <div className="flex items-center gap-4">
      {/* Depth selector */}
      <div className="flex items-center gap-2">
        <span className="text-sm text-muted-foreground">Depth:</span>
        <div className="flex gap-1">
          {[1, 2, 3].map((d) => (
            <Button
              key={d}
              variant={depth === d ? "default" : "outline"}
              size="sm"
              onClick={() => onDepthChange(d)}
            >
              {d}
            </Button>
          ))}
        </div>
      </div>

      {/* Relation type filter */}
      <div className="flex items-center gap-2">
        <span className="text-sm text-muted-foreground">Filter:</span>
        <Select
          value={relationFilter ?? "all"}
          onValueChange={(v) =>
            onRelationFilterChange(v === "all" ? null : v)
          }
        >
          <SelectTrigger className="w-36">
            <SelectValue placeholder="All relations" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All relations</SelectItem>
            {RELATION_TYPES.map((type) => (
              <SelectItem key={type} value={type}>
                <div className="flex items-center gap-2">
                  <div
                    className="w-2 h-2 rounded-full"
                    style={{ backgroundColor: RELATION_COLORS[type] }}
                  />
                  {type}
                </div>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-2 ml-4">
        <span className="text-sm text-muted-foreground">Legend:</span>
        <div className="flex flex-wrap gap-1">
          {RELATION_TYPES.slice(0, 5).map((type) => (
            <Badge
              key={type}
              variant={type as "causes" | "fixes" | "supports" | "opposes" | "follows"}
              className="text-xs"
              title={RELATION_DESCRIPTIONS[type]}
            >
              {type}
            </Badge>
          ))}
        </div>
      </div>
    </div>
  );
}
