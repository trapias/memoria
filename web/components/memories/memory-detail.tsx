"use client";

import { useState } from "react";
import { Edit2, Save, X, Clock, Star, Link2, Trash2 } from "lucide-react";
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

interface MemoryDetailProps {
  memory: Memory | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSave: (updates: { content?: string; tags?: string[]; importance?: number }) => void;
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

  const startEditing = () => {
    if (!memory) return;
    setEditContent(memory.content);
    setEditTags(memory.tags.join(", "));
    setEditImportance(memory.importance);
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

    onSave({
      content: editContent !== memory?.content ? editContent : undefined,
      tags: tags.join(",") !== memory?.tags.join(",") ? tags : undefined,
      importance: editImportance !== memory?.importance ? editImportance : undefined,
    });
    setIsEditing(false);
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

          {/* Metadata */}
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
