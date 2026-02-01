"use client";

import { Check, X, ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { DiscoverySuggestion } from "@/lib/api";
import { getConfidenceColor, getConfidenceBadgeVariant } from "@/lib/hooks/use-discovery";
import { RELATION_COLORS, RELATION_DESCRIPTIONS } from "@/lib/hooks/use-graph";
import { cn } from "@/lib/utils";
import { useState } from "react";

interface SuggestionCardProps {
  suggestion: DiscoverySuggestion;
  selected: boolean;
  onSelect: (selected: boolean) => void;
  onAccept: (relationType: string) => void;
  onReject: () => void;
  disabled?: boolean;
}

const RELATION_TYPES = [
  "causes",
  "fixes",
  "supports",
  "opposes",
  "follows",
  "supersedes",
  "derives",
  "part_of",
  "related",
];

const PREVIEW_LENGTH = 200;

export function SuggestionCard({
  suggestion,
  selected,
  onSelect,
  onAccept,
  onReject,
  disabled = false,
}: SuggestionCardProps) {
  const [relationType, setRelationType] = useState(suggestion.relation_type);
  const [sourceExpanded, setSourceExpanded] = useState(false);
  const [targetExpanded, setTargetExpanded] = useState(false);
  const confidencePercent = Math.round(suggestion.confidence * 100);
  const confidenceColorClass = getConfidenceColor(suggestion.confidence);

  const sourceNeedsExpansion = suggestion.source_preview.length > PREVIEW_LENGTH;
  const targetNeedsExpansion = suggestion.target_preview.length > PREVIEW_LENGTH;

  const displayedSource = sourceExpanded
    ? suggestion.source_preview
    : suggestion.source_preview.slice(0, PREVIEW_LENGTH);
  const displayedTarget = targetExpanded
    ? suggestion.target_preview
    : suggestion.target_preview.slice(0, PREVIEW_LENGTH);

  return (
    <Card className={cn(
      "transition-all",
      selected && "ring-2 ring-primary",
      disabled && "opacity-50"
    )}>
      <CardContent className="p-4">
        {/* Header with confidence and checkbox */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={selected}
              onChange={(e) => onSelect(e.target.checked)}
              disabled={disabled}
              className="h-4 w-4 rounded border-gray-300"
            />
            <Badge variant={getConfidenceBadgeVariant(suggestion.confidence)} className={cn("text-xs", confidenceColorClass)}>
              {confidencePercent}% confidence
            </Badge>
          </div>
          <div className="flex gap-1">
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-green-600 hover:text-green-700 hover:bg-green-100"
              onClick={() => onAccept(relationType)}
              disabled={disabled}
              title="Accept suggestion"
            >
              <Check className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-red-600 hover:text-red-700 hover:bg-red-100"
              onClick={onReject}
              disabled={disabled}
              title="Reject suggestion"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* Source and Target */}
        <div className="space-y-3 mb-3">
          {/* Source */}
          <div className="bg-muted/50 rounded-lg p-3">
            <div className="flex items-center gap-2 mb-2">
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Source</p>
              {suggestion.source_type && (
                <Badge variant="outline" className="text-xs">
                  {suggestion.source_type}
                </Badge>
              )}
            </div>
            <p className="text-sm leading-relaxed">
              {displayedSource}
              {sourceNeedsExpansion && (
                <button
                  onClick={() => setSourceExpanded(!sourceExpanded)}
                  className="ml-1 text-primary hover:underline text-xs font-medium"
                >
                  {sourceExpanded ? "Show less" : "...Show more"}
                </button>
              )}
            </p>
          </div>

          {/* Arrow with relation type */}
          <div className="flex items-center justify-center py-2">
            <div className="flex items-center gap-3 text-muted-foreground">
              <div className="h-px w-12 bg-border" />
              <Select value={relationType} onValueChange={setRelationType} disabled={disabled}>
                <SelectTrigger className="h-8 w-auto min-w-[120px] text-sm font-medium">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {RELATION_TYPES.map((type) => (
                    <SelectItem key={type} value={type} className="text-sm">
                      <span
                        className="inline-block w-2 h-2 rounded-full mr-2"
                        style={{ backgroundColor: RELATION_COLORS[type] }}
                      />
                      {type}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <span className="text-xl">&#8595;</span>
            </div>
          </div>

          {/* Target */}
          <div className="bg-muted/50 rounded-lg p-3">
            <div className="flex items-center gap-2 mb-2">
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Target</p>
              {suggestion.target_type && (
                <Badge variant="outline" className="text-xs">
                  {suggestion.target_type}
                </Badge>
              )}
            </div>
            <p className="text-sm leading-relaxed">
              {displayedTarget}
              {targetNeedsExpansion && (
                <button
                  onClick={() => setTargetExpanded(!targetExpanded)}
                  className="ml-1 text-primary hover:underline text-xs font-medium"
                >
                  {targetExpanded ? "Show less" : "...Show more"}
                </button>
              )}
            </p>
          </div>
        </div>

        {/* Reason and shared tags */}
        <div className="pt-2 border-t">
          {suggestion.reason && (
            <p className="text-xs text-muted-foreground mb-2">{suggestion.reason}</p>
          )}
          {suggestion.shared_tags.length > 0 && (
            <div className="flex flex-wrap gap-1">
              <span className="text-xs text-muted-foreground">Shared tags:</span>
              {suggestion.shared_tags.slice(0, 3).map((tag) => (
                <Badge key={tag} variant="secondary" className="text-xs">
                  {tag}
                </Badge>
              ))}
              {suggestion.shared_tags.length > 3 && (
                <span className="text-xs text-muted-foreground">
                  +{suggestion.shared_tags.length - 3} more
                </span>
              )}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
