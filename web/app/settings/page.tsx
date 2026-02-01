"use client";

import { useState } from "react";
import {
  Loader2,
  AlertCircle,
  CheckCircle2,
  Combine,
  Trash2,
  TrendingDown,
  Play,
  Eye,
} from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useStats, useConsolidateMemories } from "@/lib/hooks/use-memories";
import { ConsolidationPreview } from "@/lib/api";

export default function SettingsPage() {
  const { data: stats } = useStats();
  const consolidateMutation = useConsolidateMemories();

  // Consolidation settings
  const [memoryType, setMemoryType] = useState("semantic");
  const [similarityThreshold, setSimilarityThreshold] = useState(0.9);
  const [maxAgeDays, setMaxAgeDays] = useState(30);
  const [minImportance, setMinImportance] = useState(0.3);
  const [lastPreview, setLastPreview] = useState<ConsolidationPreview | null>(null);

  const handleConsolidate = async (operation: "consolidate" | "forget" | "decay", dryRun: boolean) => {
    try {
      const result = await consolidateMutation.mutateAsync({
        operation,
        memory_type: memoryType,
        similarity_threshold: similarityThreshold,
        max_age_days: maxAgeDays,
        min_importance: minImportance,
        dry_run: dryRun,
      });
      setLastPreview(result);
    } catch (error) {
      console.error("Consolidation failed:", error);
    }
  };

  return (
    <div className="container py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight">Settings</h1>
        <p className="text-muted-foreground">
          Configuration, maintenance, and system information
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        {/* Memory Consolidation */}
        <Card className="md:col-span-2">
          <CardHeader>
            <CardTitle>Memory Consolidation</CardTitle>
            <CardDescription>
              Merge similar memories, remove old unused ones, and optimize your memory store
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Settings */}
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label>Memory Type</Label>
                  <Select value={memoryType} onValueChange={setMemoryType}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="episodic">Episodic</SelectItem>
                      <SelectItem value="semantic">Semantic</SelectItem>
                      <SelectItem value="procedural">Procedural</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label>Similarity Threshold</Label>
                    <span className="text-sm text-muted-foreground">
                      {Math.round(similarityThreshold * 100)}%
                    </span>
                  </div>
                  <Slider
                    value={[similarityThreshold]}
                    onValueChange={([v]) => setSimilarityThreshold(v)}
                    min={0.7}
                    max={0.99}
                    step={0.01}
                  />
                  <p className="text-xs text-muted-foreground">
                    Memories more similar than this will be merged
                  </p>
                </div>
              </div>

              <div className="space-y-4">
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label>Max Age (days)</Label>
                    <span className="text-sm text-muted-foreground">
                      {maxAgeDays} days
                    </span>
                  </div>
                  <Slider
                    value={[maxAgeDays]}
                    onValueChange={([v]) => setMaxAgeDays(v)}
                    min={7}
                    max={90}
                    step={1}
                  />
                </div>

                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label>Min Importance to Keep</Label>
                    <span className="text-sm text-muted-foreground">
                      {Math.round(minImportance * 100)}%
                    </span>
                  </div>
                  <Slider
                    value={[minImportance]}
                    onValueChange={([v]) => setMinImportance(v)}
                    min={0.1}
                    max={0.5}
                    step={0.05}
                  />
                  <p className="text-xs text-muted-foreground">
                    Old memories below this importance may be forgotten
                  </p>
                </div>
              </div>
            </div>

            {/* Actions */}
            <div className="flex flex-wrap gap-3 pt-4 border-t">
              <div className="space-y-1">
                <p className="text-sm font-medium flex items-center gap-2">
                  <Combine className="h-4 w-4" />
                  Consolidate (Merge Similar)
                </p>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleConsolidate("consolidate", true)}
                    disabled={consolidateMutation.isPending}
                  >
                    <Eye className="h-4 w-4 mr-1" />
                    Preview
                  </Button>
                  <Button
                    size="sm"
                    onClick={() => handleConsolidate("consolidate", false)}
                    disabled={consolidateMutation.isPending}
                  >
                    <Play className="h-4 w-4 mr-1" />
                    Run
                  </Button>
                </div>
              </div>

              <div className="space-y-1">
                <p className="text-sm font-medium flex items-center gap-2">
                  <Trash2 className="h-4 w-4" />
                  Forget (Remove Old/Unused)
                </p>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleConsolidate("forget", true)}
                    disabled={consolidateMutation.isPending}
                  >
                    <Eye className="h-4 w-4 mr-1" />
                    Preview
                  </Button>
                  <Button
                    size="sm"
                    variant="destructive"
                    onClick={() => handleConsolidate("forget", false)}
                    disabled={consolidateMutation.isPending}
                  >
                    <Play className="h-4 w-4 mr-1" />
                    Run
                  </Button>
                </div>
              </div>

              <div className="space-y-1">
                <p className="text-sm font-medium flex items-center gap-2">
                  <TrendingDown className="h-4 w-4" />
                  Decay (Reduce Old Importance)
                </p>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleConsolidate("decay", true)}
                    disabled={consolidateMutation.isPending}
                  >
                    <Eye className="h-4 w-4 mr-1" />
                    Preview
                  </Button>
                  <Button
                    size="sm"
                    onClick={() => handleConsolidate("decay", false)}
                    disabled={consolidateMutation.isPending}
                  >
                    <Play className="h-4 w-4 mr-1" />
                    Run
                  </Button>
                </div>
              </div>
            </div>

            {/* Loading state */}
            {consolidateMutation.isPending && (
              <div className="flex items-center gap-2 text-muted-foreground p-3 rounded-lg bg-muted/50">
                <Loader2 className="h-4 w-4 animate-spin" />
                Processing...
              </div>
            )}

            {/* Result */}
            {lastPreview && (
              <div className={`p-4 rounded-lg ${lastPreview.is_preview ? "bg-blue-50 dark:bg-blue-900/20" : "bg-green-50 dark:bg-green-900/20"}`}>
                <div className="flex items-center gap-2 mb-2">
                  {lastPreview.is_preview ? (
                    <Eye className="h-4 w-4 text-blue-600" />
                  ) : (
                    <CheckCircle2 className="h-4 w-4 text-green-600" />
                  )}
                  <span className="font-medium">
                    {lastPreview.is_preview ? "Preview" : "Completed"}: {lastPreview.operation}
                  </span>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                  <div>
                    <span className="text-muted-foreground">Processed:</span>
                    <span className="ml-2 font-medium">{lastPreview.total_processed}</span>
                  </div>
                  {lastPreview.merged_count > 0 && (
                    <div>
                      <span className="text-muted-foreground">Would merge:</span>
                      <span className="ml-2 font-medium">{lastPreview.merged_count}</span>
                    </div>
                  )}
                  {lastPreview.forgotten_count > 0 && (
                    <div>
                      <span className="text-muted-foreground">Would remove:</span>
                      <span className="ml-2 font-medium text-red-600">{lastPreview.forgotten_count}</span>
                    </div>
                  )}
                  {lastPreview.updated_count > 0 && (
                    <div>
                      <span className="text-muted-foreground">Would update:</span>
                      <span className="ml-2 font-medium">{lastPreview.updated_count}</span>
                    </div>
                  )}
                  <div>
                    <span className="text-muted-foreground">Duration:</span>
                    <span className="ml-2 font-medium">{lastPreview.duration_seconds.toFixed(2)}s</span>
                  </div>
                </div>
                {lastPreview.is_preview && (lastPreview.merged_count > 0 || lastPreview.forgotten_count > 0 || lastPreview.updated_count > 0) && (
                  <p className="text-xs text-muted-foreground mt-2">
                    This is a preview. Click "Run" to apply changes.
                  </p>
                )}
              </div>
            )}

            {consolidateMutation.isError && (
              <div className="flex items-center gap-2 text-red-600 p-3 rounded-lg bg-red-50 dark:bg-red-900/20">
                <AlertCircle className="h-4 w-4" />
                Error: {consolidateMutation.error?.message}
              </div>
            )}
          </CardContent>
        </Card>

        {/* API Configuration */}
        <Card>
          <CardHeader>
            <CardTitle>API Configuration</CardTitle>
            <CardDescription>
              Current API endpoint configuration
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <p className="text-sm text-muted-foreground">API Base URL</p>
              <code className="text-sm bg-muted px-2 py-1 rounded">
                {process.env.NEXT_PUBLIC_API_URL || "http://localhost:8765"}
              </code>
            </div>
          </CardContent>
        </Card>

        {/* System Stats */}
        <Card>
          <CardHeader>
            <CardTitle>System Statistics</CardTitle>
            <CardDescription>Current database statistics</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-muted-foreground">Total Memories</p>
                <p className="text-2xl font-bold">
                  {stats?.total_memories ?? 0}
                </p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Total Relations</p>
                <p className="text-2xl font-bold">
                  {stats?.total_relations ?? 0}
                </p>
              </div>
            </div>

            <div>
              <p className="text-sm text-muted-foreground mb-2">By Type</p>
              <div className="flex flex-wrap gap-2">
                {stats?.by_type &&
                  Object.entries(stats.by_type).map(([type, count]) => (
                    <Badge key={type} variant="secondary">
                      {type}: {count}
                    </Badge>
                  ))}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* About */}
        <Card className="md:col-span-2">
          <CardHeader>
            <CardTitle>About Memoria</CardTitle>
            <CardDescription>
              Knowledge Graph Explorer for MCP Memoria
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm">
              Memoria is an MCP (Model Context Protocol) server providing
              persistent, unlimited local AI memory. This web interface allows
              you to explore and manage the knowledge graph of relationships
              between memories.
            </p>

            <div>
              <p className="text-sm text-muted-foreground mb-2">
                Relation Types
              </p>
              <div className="grid grid-cols-3 gap-2 text-sm">
                <div>
                  <Badge variant="causes">causes</Badge> - A leads to B
                </div>
                <div>
                  <Badge variant="fixes">fixes</Badge> - A solves B
                </div>
                <div>
                  <Badge variant="supports">supports</Badge> - A confirms B
                </div>
                <div>
                  <Badge variant="opposes">opposes</Badge> - A contradicts B
                </div>
                <div>
                  <Badge variant="follows">follows</Badge> - A comes after B
                </div>
                <div>
                  <Badge variant="supersedes">supersedes</Badge> - A replaces B
                </div>
                <div>
                  <Badge variant="derives">derives</Badge> - A derived from B
                </div>
                <div>
                  <Badge variant="part_of">part_of</Badge> - A is component of B
                </div>
                <div>
                  <Badge variant="related">related</Badge> - General connection
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
