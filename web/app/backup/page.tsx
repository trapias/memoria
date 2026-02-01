"use client";

import { useState, useRef } from "react";
import {
  Download,
  Upload,
  FileJson,
  Database,
  GitBranch,
  Tags,
  Loader2,
  CheckCircle2,
  AlertCircle,
} from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { useBackupStats, useExportBackup, useImportBackup } from "@/lib/hooks/use-backup";
import { ImportResult } from "@/lib/api";

export default function BackupPage() {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [includeGraph, setIncludeGraph] = useState(true);
  const [skipExisting, setSkipExisting] = useState(true);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);

  const { data: stats, isLoading: statsLoading } = useBackupStats();
  const exportMutation = useExportBackup();
  const importMutation = useImportBackup();

  const handleExport = async () => {
    try {
      await exportMutation.mutateAsync({
        include_graph: includeGraph,
        memory_types: ["episodic", "semantic", "procedural"],
      });
    } catch (error) {
      console.error("Export failed:", error);
    }
  };

  const handleImport = async (file: File) => {
    try {
      const result = await importMutation.mutateAsync({
        file,
        skipExisting,
      });
      setImportResult(result);
    } catch (error) {
      console.error("Import failed:", error);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      handleImport(file);
    }
    // Reset input so same file can be selected again
    e.target.value = "";
  };

  return (
    <div className="container py-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">Backup & Restore</h1>
        <p className="text-muted-foreground">
          Export your memories and graph to a JSON file, or import from a backup
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        {/* Export Section */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Download className="h-5 w-5" />
              Export
            </CardTitle>
            <CardDescription>
              Download all your memories and relations as a JSON file
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Stats */}
            {statsLoading ? (
              <div className="flex items-center gap-2 text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Loading stats...
              </div>
            ) : stats ? (
              <div className="grid grid-cols-3 gap-4">
                <div className="text-center p-3 rounded-lg bg-muted/50">
                  <Database className="h-5 w-5 mx-auto mb-1 text-muted-foreground" />
                  <p className="text-2xl font-bold">{stats.memories_count}</p>
                  <p className="text-xs text-muted-foreground">Memories</p>
                </div>
                <div className="text-center p-3 rounded-lg bg-muted/50">
                  <GitBranch className="h-5 w-5 mx-auto mb-1 text-muted-foreground" />
                  <p className="text-2xl font-bold">{stats.relations_count}</p>
                  <p className="text-xs text-muted-foreground">Relations</p>
                </div>
                <div className="text-center p-3 rounded-lg bg-muted/50">
                  <Tags className="h-5 w-5 mx-auto mb-1 text-muted-foreground" />
                  <p className="text-2xl font-bold">{stats.tags_count}</p>
                  <p className="text-xs text-muted-foreground">Tags</p>
                </div>
              </div>
            ) : null}

            {/* Options */}
            <div className="space-y-2">
              <Label className="text-sm font-medium">Options</Label>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={includeGraph}
                  onChange={(e) => setIncludeGraph(e.target.checked)}
                  className="rounded"
                />
                Include graph relations
              </label>
            </div>

            {/* Export Button */}
            <Button
              onClick={handleExport}
              disabled={exportMutation.isPending}
              className="w-full"
            >
              {exportMutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Exporting...
                </>
              ) : (
                <>
                  <Download className="h-4 w-4 mr-2" />
                  Download Backup
                </>
              )}
            </Button>

            {exportMutation.isSuccess && (
              <div className="flex items-center gap-2 text-green-600 text-sm">
                <CheckCircle2 className="h-4 w-4" />
                Backup downloaded successfully!
              </div>
            )}
          </CardContent>
        </Card>

        {/* Import Section */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Upload className="h-5 w-5" />
              Import
            </CardTitle>
            <CardDescription>
              Restore memories and relations from a backup file
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Options */}
            <div className="space-y-2">
              <Label className="text-sm font-medium">Options</Label>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={skipExisting}
                  onChange={(e) => setSkipExisting(e.target.checked)}
                  className="rounded"
                />
                Skip existing memories (avoid duplicates)
              </label>
            </div>

            {/* File Input */}
            <input
              ref={fileInputRef}
              type="file"
              accept=".json"
              onChange={handleFileSelect}
              className="hidden"
            />

            {/* Import Button */}
            <Button
              onClick={() => fileInputRef.current?.click()}
              disabled={importMutation.isPending}
              variant="outline"
              className="w-full"
            >
              {importMutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Importing...
                </>
              ) : (
                <>
                  <FileJson className="h-4 w-4 mr-2" />
                  Select Backup File
                </>
              )}
            </Button>

            {/* Import Result */}
            {importResult && (
              <div className="space-y-2 p-3 rounded-lg bg-muted/50">
                <div className="flex items-center gap-2 text-green-600 text-sm font-medium">
                  <CheckCircle2 className="h-4 w-4" />
                  Import Complete
                </div>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div>
                    <span className="text-muted-foreground">Memories imported:</span>
                    <Badge variant="secondary" className="ml-2">
                      {importResult.memories_imported}
                    </Badge>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Skipped:</span>
                    <Badge variant="outline" className="ml-2">
                      {importResult.memories_skipped}
                    </Badge>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Relations imported:</span>
                    <Badge variant="secondary" className="ml-2">
                      {importResult.relations_imported}
                    </Badge>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Skipped:</span>
                    <Badge variant="outline" className="ml-2">
                      {importResult.relations_skipped}
                    </Badge>
                  </div>
                </div>
                {importResult.errors.length > 0 && (
                  <div className="pt-2 border-t">
                    <div className="flex items-center gap-1 text-orange-600 text-sm mb-1">
                      <AlertCircle className="h-3 w-3" />
                      {importResult.errors.length} errors
                    </div>
                    <div className="text-xs text-muted-foreground max-h-24 overflow-y-auto">
                      {importResult.errors.slice(0, 5).map((err, i) => (
                        <p key={i}>{err}</p>
                      ))}
                      {importResult.errors.length > 5 && (
                        <p>...and {importResult.errors.length - 5} more</p>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}

            {importMutation.isError && (
              <div className="flex items-center gap-2 text-red-600 text-sm">
                <AlertCircle className="h-4 w-4" />
                Import failed: {importMutation.error?.message}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Tips */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Backup Tips</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground space-y-2">
          <p>
            <strong>Regular backups:</strong> Export your memories regularly to prevent data loss.
          </p>
          <p>
            <strong>Safe storage:</strong> Store backup files in a secure location like encrypted cloud storage.
          </p>
          <p>
            <strong>Version history:</strong> Keep multiple backup versions with dates in the filename.
          </p>
          <p>
            <strong>Import safety:</strong> Enable "Skip existing" to avoid duplicate entries when restoring.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
