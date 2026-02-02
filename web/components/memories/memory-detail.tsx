"use client";

import { useState } from "react";
import { Edit2, Save, X, Clock, Star, Link2, Trash2, Plus, Minus } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Slider } from "@/components/ui/slider";
import { Label } from "@/components/ui/label";
import { Memory } from "@/lib/api";
import { MEMORY_TYPE_COLORS } from "@/lib/hooks/use-memories";
import { cn } from "@/lib/utils";
import { MarkdownContent } from "@/components/ui/markdown-content";

interface MetadataEntry {
  key: string;
  value: string;
}

interface MemoryDetailProps {
  memory: Memory | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSave: (updates: {
    content?: string;
    tags?: string[];
    importance?: number;
    metadata?: Record<string, unknown>;
  }) => void;
  onDelete: () => void;
  onViewRelations: () => void;
  isSaving?: boolean;
}

export function MemoryDetail({
  memory,
  open,
  onOpenChange,
  onSave,
  onDelete,
  onViewRelations,
  isSaving = false,
}: MemoryDetailProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editContent, setEditContent] = useState("");
  const [editTags, setEditTags] = useState("");
  const [editImportance, setEditImportance] = useState(0.5);
  const [editMetadata, setEditMetadata] = useState<MetadataEntry[]>([]);

  const startEditing = () => {
    if (!memory) return;
    setEditContent(memory.content);
    setEditTags(memory.tags.join(", "));
    setEditImportance(memory.importance);
    // Convert metadata object to array of entries
    const entries = Object.entries(memory.metadata || {}).map(([key, value]) => ({
      key,
      value: typeof value === "string" ? value : JSON.stringify(value),
    }));
    setEditMetadata(entries.length > 0 ? entries : [{ key: "", value: "" }]);
    setIsEditing(true);
  };

  const cancelEditing = () => {
    setIsEditing(false);
  };

  const handleSave = () => {
    const tags = editTags
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean);

    // Convert metadata entries back to object, filtering out empty keys
    const metadata: Record<string, unknown> = {};
    for (const entry of editMetadata) {
      if (entry.key.trim()) {
        // Try to parse as JSON for non-string values
        try {
          metadata[entry.key.trim()] = JSON.parse(entry.value);
        } catch {
          metadata[entry.key.trim()] = entry.value;
        }
      }
    }

    // Check if metadata changed
    const originalMetadata = memory?.metadata || {};
    const metadataChanged =
      JSON.stringify(metadata) !== JSON.stringify(originalMetadata);

    onSave({
      content: editContent !== memory?.content ? editContent : undefined,
      tags: tags.join(",") !== memory?.tags.join(",") ? tags : undefined,
      importance: editImportance !== memory?.importance ? editImportance : undefined,
      metadata: metadataChanged ? metadata : undefined,
    });
    setIsEditing(false);
  };

  const addMetadataEntry = () => {
    setEditMetadata([...editMetadata, { key: "", value: "" }]);
  };

  const removeMetadataEntry = (index: number) => {
    setEditMetadata(editMetadata.filter((_, i) => i !== index));
  };

  const updateMetadataEntry = (
    index: number,
    field: "key" | "value",
    value: string
  ) => {
    const updated = [...editMetadata];
    updated[index] = { ...updated[index], [field]: value };
    setEditMetadata(updated);
  };

  const formatDate = (dateStr: string) => {
    try {
      return new Date(dateStr).toLocaleString();
    } catch {
      return dateStr;
    }
  };

  if (!memory) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <div className="flex items-center justify-between">
            <DialogTitle className="flex items-center gap-2">
              <Badge
                variant="secondary"
                className={cn("text-xs", MEMORY_TYPE_COLORS[memory.memory_type])}
              >
                {memory.memory_type}
              </Badge>
              Memory Detail
            </DialogTitle>
            {!isEditing && (
              <Button variant="outline" size="sm" onClick={startEditing}>
                <Edit2 className="h-4 w-4 mr-2" />
                Edit
              </Button>
            )}
          </div>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* Content */}
          <div className="space-y-2">
            <Label>Content</Label>
            {isEditing ? (
              <Textarea
                value={editContent}
                onChange={(e) => setEditContent(e.target.value)}
                rows={8}
                className="font-mono text-sm"
              />
            ) : (
              <div className="p-3 rounded-md bg-muted/50">
                <MarkdownContent content={memory.content} />
              </div>
            )}
          </div>

          {/* Tags */}
          <div className="space-y-2">
            <Label>Tags</Label>
            {isEditing ? (
              <Input
                value={editTags}
                onChange={(e) => setEditTags(e.target.value)}
                placeholder="tag1, tag2, tag3"
              />
            ) : (
              <div className="flex flex-wrap gap-1">
                {memory.tags.length > 0 ? (
                  memory.tags.map((tag) => (
                    <Badge key={tag} variant="outline">
                      {tag}
                    </Badge>
                  ))
                ) : (
                  <span className="text-sm text-muted-foreground">No tags</span>
                )}
              </div>
            )}
          </div>

          {/* Importance */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label>Importance</Label>
              <span className="text-sm text-muted-foreground">
                {Math.round((isEditing ? editImportance : memory.importance) * 100)}%
              </span>
            </div>
            {isEditing ? (
              <Slider
                value={[editImportance]}
                onValueChange={([v]) => setEditImportance(v)}
                min={0}
                max={1}
                step={0.05}
              />
            ) : (
              <div className="h-2 bg-muted rounded-full overflow-hidden">
                <div
                  className="h-full bg-primary"
                  style={{ width: `${memory.importance * 100}%` }}
                />
              </div>
            )}
          </div>

          {/* Custom Metadata */}
          <div className="space-y-2 pt-4 border-t">
            <div className="flex items-center justify-between">
              <Label>Metadata</Label>
              {isEditing && (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={addMetadataEntry}
                >
                  <Plus className="h-3 w-3 mr-1" />
                  Add
                </Button>
              )}
            </div>
            {isEditing ? (
              <div className="space-y-2">
                {editMetadata.map((entry, index) => (
                  <div key={index} className="flex items-center gap-2">
                    <Input
                      value={entry.key}
                      onChange={(e) =>
                        updateMetadataEntry(index, "key", e.target.value)
                      }
                      placeholder="key"
                      className="w-1/3 text-sm"
                    />
                    <Input
                      value={entry.value}
                      onChange={(e) =>
                        updateMetadataEntry(index, "value", e.target.value)
                      }
                      placeholder="value"
                      className="flex-1 text-sm"
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => removeMetadataEntry(index)}
                      className="px-2"
                    >
                      <Minus className="h-4 w-4 text-muted-foreground" />
                    </Button>
                  </div>
                ))}
                {editMetadata.length === 0 && (
                  <p className="text-sm text-muted-foreground">
                    No metadata. Click "Add" to add key-value pairs.
                  </p>
                )}
              </div>
            ) : (
              <div className="space-y-1">
                {memory.metadata && Object.keys(memory.metadata).length > 0 ? (
                  Object.entries(memory.metadata).map(([key, value]) => (
                    <div
                      key={key}
                      className="flex items-center gap-2 text-sm"
                    >
                      <span className="font-medium text-muted-foreground">
                        {key}:
                      </span>
                      <span className="font-mono">
                        {typeof value === "string" ? value : JSON.stringify(value)}
                      </span>
                    </div>
                  ))
                ) : (
                  <span className="text-sm text-muted-foreground">
                    No metadata
                  </span>
                )}
              </div>
            )}
          </div>

          {/* Timestamps */}
          <div className="grid grid-cols-2 gap-4 pt-4 border-t">
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground">Created</p>
              <p className="text-sm flex items-center gap-1">
                <Clock className="h-3 w-3" />
                {formatDate(memory.created_at)}
              </p>
            </div>
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground">Updated</p>
              <p className="text-sm flex items-center gap-1">
                <Clock className="h-3 w-3" />
                {formatDate(memory.updated_at)}
              </p>
            </div>
          </div>

          {/* ID */}
          <div className="pt-2">
            <p className="text-xs text-muted-foreground">ID</p>
            <p className="text-xs font-mono text-muted-foreground">{memory.id}</p>
          </div>
        </div>

        <DialogFooter className="flex-col sm:flex-row gap-2">
          {isEditing ? (
            <>
              <Button variant="outline" onClick={cancelEditing} disabled={isSaving}>
                <X className="h-4 w-4 mr-2" />
                Cancel
              </Button>
              <Button onClick={handleSave} disabled={isSaving}>
                <Save className="h-4 w-4 mr-2" />
                {isSaving ? "Saving..." : "Save Changes"}
              </Button>
            </>
          ) : (
            <>
              <Button
                variant="outline"
                onClick={onViewRelations}
                className="flex-1 sm:flex-none"
              >
                <Link2 className="h-4 w-4 mr-2" />
                View Relations
              </Button>
              <Button
                variant="destructive"
                onClick={onDelete}
                className="flex-1 sm:flex-none"
              >
                <Trash2 className="h-4 w-4 mr-2" />
                Delete
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
