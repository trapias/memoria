"use client";

import { useState, useCallback } from "react";
import { Search, Loader2, CheckCircle2, XCircle, Settings2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Slider } from "@/components/ui/slider";
import { Label } from "@/components/ui/label";
import { SuggestionCard } from "@/components/graph/suggestion-card";
import {
  useDiscoverRelationsMutation,
  useAcceptDiscoverySuggestions,
  useRejectSuggestion,
  DiscoveryParams,
} from "@/lib/hooks/use-discovery";
import { DiscoverySuggestion } from "@/lib/api";

export default function DiscoverPage() {
  // Discovery settings
  const [minConfidence, setMinConfidence] = useState(0.75);
  const [autoAcceptThreshold, setAutoAcceptThreshold] = useState(0.90);
  const [showSettings, setShowSettings] = useState(false);

  // Results and selection
  const [suggestions, setSuggestions] = useState<DiscoverySuggestion[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [stats, setStats] = useState<{
    autoAccepted: number;
    scannedCount: number;
    totalWithoutRelations: number;
  } | null>(null);

  // Mutations
  const discoverMutation = useDiscoverRelationsMutation();
  const acceptMutation = useAcceptDiscoverySuggestions();
  const rejectMutation = useRejectSuggestion();

  const handleDiscover = useCallback(async () => {
    const params: DiscoveryParams = {
      limit: 50,
      min_confidence: minConfidence,
      auto_accept_threshold: autoAcceptThreshold,
      skip_with_relations: true,
    };

    try {
      const result = await discoverMutation.mutateAsync(params);
      setSuggestions(result.suggestions);
      setSelectedIds(new Set());
      setStats({
        autoAccepted: result.auto_accepted,
        scannedCount: result.scanned_count,
        totalWithoutRelations: result.total_without_relations,
      });
    } catch (error) {
      console.error("Discovery failed:", error);
    }
  }, [minConfidence, autoAcceptThreshold, discoverMutation]);

  const handleSelectSuggestion = (suggestionId: string, selected: boolean) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (selected) {
        next.add(suggestionId);
      } else {
        next.delete(suggestionId);
      }
      return next;
    });
  };

  const handleAcceptSingle = async (suggestion: DiscoverySuggestion, relationType: string) => {
    try {
      await acceptMutation.mutateAsync([{
        source_id: suggestion.source_id,
        target_id: suggestion.target_id,
        relation_type: relationType,
      }]);
      // Remove from list
      setSuggestions((prev) => prev.filter((s) =>
        !(s.source_id === suggestion.source_id && s.target_id === suggestion.target_id)
      ));
    } catch (error) {
      console.error("Accept failed:", error);
    }
  };

  const handleRejectSingle = async (suggestion: DiscoverySuggestion) => {
    try {
      await rejectMutation.mutateAsync({
        sourceId: suggestion.source_id,
        targetId: suggestion.target_id,
        relationType: suggestion.relation_type,
      });
      // Remove from list
      setSuggestions((prev) => prev.filter((s) =>
        !(s.source_id === suggestion.source_id && s.target_id === suggestion.target_id)
      ));
    } catch (error) {
      console.error("Reject failed:", error);
    }
  };

  const handleBulkAccept = async (minConfidenceFilter?: number) => {
    const toAccept = suggestions.filter((s) => {
      if (minConfidenceFilter !== undefined) {
        return s.confidence >= minConfidenceFilter;
      }
      return selectedIds.has(`${s.source_id}-${s.target_id}`);
    });

    if (toAccept.length === 0) return;

    try {
      await acceptMutation.mutateAsync(
        toAccept.map((s) => ({
          source_id: s.source_id,
          target_id: s.target_id,
          relation_type: s.relation_type,
        }))
      );
      // Remove accepted from list
      const acceptedSet = new Set(toAccept.map((s) => `${s.source_id}-${s.target_id}`));
      setSuggestions((prev) => prev.filter((s) => !acceptedSet.has(`${s.source_id}-${s.target_id}`)));
      setSelectedIds(new Set());
    } catch (error) {
      console.error("Bulk accept failed:", error);
    }
  };

  const handleBulkReject = async (maxConfidenceFilter?: number) => {
    const toReject = suggestions.filter((s) => {
      if (maxConfidenceFilter !== undefined) {
        return s.confidence < maxConfidenceFilter;
      }
      return selectedIds.has(`${s.source_id}-${s.target_id}`);
    });

    if (toReject.length === 0) return;

    // Reject each one
    for (const s of toReject) {
      try {
        await rejectMutation.mutateAsync({
          sourceId: s.source_id,
          targetId: s.target_id,
          relationType: s.relation_type,
        });
      } catch (error) {
        console.error("Reject failed:", error);
      }
    }

    // Remove rejected from list
    const rejectedSet = new Set(toReject.map((s) => `${s.source_id}-${s.target_id}`));
    setSuggestions((prev) => prev.filter((s) => !rejectedSet.has(`${s.source_id}-${s.target_id}`)));
    setSelectedIds(new Set());
  };

  const isLoading = discoverMutation.isPending || acceptMutation.isPending || rejectMutation.isPending;
  const highConfidenceCount = suggestions.filter((s) => s.confidence >= 0.85).length;
  const lowConfidenceCount = suggestions.filter((s) => s.confidence < 0.70).length;

  return (
    <div className="container py-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Discover Relations</h1>
          <p className="text-muted-foreground">
            Automatically find and create relations between your memories
          </p>
        </div>
        <Button
          variant="outline"
          size="icon"
          onClick={() => setShowSettings(!showSettings)}
        >
          <Settings2 className="h-4 w-4" />
        </Button>
      </div>

      {/* Settings Panel */}
      {showSettings && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Discovery Settings</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label>Minimum Confidence</Label>
                <span className="text-sm text-muted-foreground">
                  {Math.round(minConfidence * 100)}%
                </span>
              </div>
              <Slider
                value={[minConfidence]}
                onValueChange={([v]) => setMinConfidence(v)}
                min={0.5}
                max={0.95}
                step={0.05}
              />
              <p className="text-xs text-muted-foreground">
                Only show suggestions with confidence above this threshold
              </p>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label>Auto-Accept Threshold</Label>
                <span className="text-sm text-muted-foreground">
                  {Math.round(autoAcceptThreshold * 100)}%
                </span>
              </div>
              <Slider
                value={[autoAcceptThreshold]}
                onValueChange={([v]) => setAutoAcceptThreshold(v)}
                min={0.85}
                max={1.0}
                step={0.01}
              />
              <p className="text-xs text-muted-foreground">
                Automatically accept relations with confidence above this threshold
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Scan Button */}
      <Card>
        <CardContent className="py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Button
                onClick={handleDiscover}
                disabled={isLoading}
                size="lg"
              >
                {discoverMutation.isPending ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Scanning...
                  </>
                ) : (
                  <>
                    <Search className="h-4 w-4 mr-2" />
                    Scan for Relations
                  </>
                )}
              </Button>

              {stats && (
                <div className="flex items-center gap-4 text-sm">
                  <span className="text-muted-foreground">
                    Scanned: {stats.scannedCount}/{stats.totalWithoutRelations}
                  </span>
                  {stats.autoAccepted > 0 && (
                    <Badge variant="secondary" className="bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400">
                      <CheckCircle2 className="h-3 w-3 mr-1" />
                      {stats.autoAccepted} auto-accepted
                    </Badge>
                  )}
                  <span className="text-muted-foreground">
                    Found: {suggestions.length} suggestions
                  </span>
                </div>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Bulk Actions */}
      {suggestions.length > 0 && (
        <Card>
          <CardContent className="py-3">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <span>Bulk Actions:</span>
              </div>
              <div className="flex items-center gap-2">
                {highConfidenceCount > 0 && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleBulkAccept(0.85)}
                    disabled={isLoading}
                  >
                    <CheckCircle2 className="h-3 w-3 mr-1 text-green-600" />
                    Accept all &gt;85% ({highConfidenceCount})
                  </Button>
                )}
                {lowConfidenceCount > 0 && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleBulkReject(0.70)}
                    disabled={isLoading}
                  >
                    <XCircle className="h-3 w-3 mr-1 text-red-600" />
                    Reject all &lt;70% ({lowConfidenceCount})
                  </Button>
                )}
                {selectedIds.size > 0 && (
                  <>
                    <Button
                      variant="default"
                      size="sm"
                      onClick={() => handleBulkAccept()}
                      disabled={isLoading}
                    >
                      Accept selected ({selectedIds.size})
                    </Button>
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => handleBulkReject()}
                      disabled={isLoading}
                    >
                      Reject selected ({selectedIds.size})
                    </Button>
                  </>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Suggestions List */}
      {suggestions.length > 0 ? (
        <div className="grid gap-4 md:grid-cols-2">
          {suggestions.map((suggestion) => {
            const id = `${suggestion.source_id}-${suggestion.target_id}`;
            return (
              <SuggestionCard
                key={id}
                suggestion={suggestion}
                selected={selectedIds.has(id)}
                onSelect={(selected) => handleSelectSuggestion(id, selected)}
                onAccept={(relationType) => handleAcceptSingle(suggestion, relationType)}
                onReject={() => handleRejectSingle(suggestion)}
                disabled={isLoading}
              />
            );
          })}
        </div>
      ) : stats ? (
        <Card>
          <CardContent className="py-12 text-center">
            <CheckCircle2 className="h-12 w-12 mx-auto text-green-500 mb-4" />
            <h3 className="text-lg font-medium mb-2">All caught up!</h3>
            <p className="text-muted-foreground">
              No more suggestions to review. Try lowering the confidence threshold or scan again later.
            </p>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="py-12 text-center">
            <Search className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
            <h3 className="text-lg font-medium mb-2">Ready to Discover</h3>
            <p className="text-muted-foreground">
              Click "Scan for Relations" to find potential connections between your memories.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
