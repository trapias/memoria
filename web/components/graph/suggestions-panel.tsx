"use client";

import { useSuggestions, useAcceptSuggestion, RELATION_COLORS } from "@/lib/hooks/use-graph";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Lightbulb, Check, X } from "lucide-react";

interface SuggestionsPanelProps {
  memoryId: string;
  onAccept: () => void;
}

export function SuggestionsPanel({ memoryId, onAccept }: SuggestionsPanelProps) {
  const { data, isLoading } = useSuggestions(memoryId, 5);
  const acceptMutation = useAcceptSuggestion();

  const suggestions = data?.suggestions ?? [];

  const handleAccept = async (targetId: string, relationType: string) => {
    await acceptMutation.mutateAsync({
      memoryId,
      targetId,
      relationType,
    });
    onAccept();
  };

  if (isLoading) {
    return (
      <div className="p-4 border-t">
        <p className="text-sm text-muted-foreground text-center">
          Finding suggestions...
        </p>
      </div>
    );
  }

  if (suggestions.length === 0) {
    return null;
  }

  return (
    <div className="border-t">
      <Card className="border-0 rounded-none">
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Lightbulb className="h-4 w-4 text-yellow-500" />
            AI Suggestions
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 max-h-64 overflow-y-auto">
          {suggestions.map((suggestion) => (
            <div
              key={suggestion.target_id}
              className="p-3 rounded-lg border bg-muted/30"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <p className="text-sm line-clamp-2 mb-2">
                    {suggestion.target_content}
                  </p>
                  <div className="flex items-center gap-2 flex-wrap">
                    <Badge
                      variant={suggestion.suggested_type as "causes" | "fixes" | "supports"}
                      className="text-xs"
                    >
                      {suggestion.suggested_type}
                    </Badge>
                    <span className="text-xs text-muted-foreground">
                      {(suggestion.confidence * 100).toFixed(0)}% confidence
                    </span>
                  </div>
                  {suggestion.reason && (
                    <p className="text-xs text-muted-foreground mt-1">
                      {suggestion.reason}
                    </p>
                  )}
                </div>
                <div className="flex gap-1 shrink-0">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={() =>
                      handleAccept(suggestion.target_id, suggestion.suggested_type)
                    }
                    disabled={acceptMutation.isPending}
                  >
                    <Check className="h-4 w-4 text-green-600" />
                  </Button>
                </div>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
