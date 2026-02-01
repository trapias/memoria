"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useCreateRelation, RELATION_COLORS, RELATION_DESCRIPTIONS } from "@/lib/hooks/use-graph";
import { useSearchMemories } from "@/lib/hooks/use-memories";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Badge } from "@/components/ui/badge";
import { Search } from "lucide-react";

const formSchema = z.object({
  targetId: z.string().min(1, "Target memory is required"),
  relationType: z.string().min(1, "Relation type is required"),
  weight: z.number().min(0).max(1),
});

type FormData = z.infer<typeof formSchema>;

interface RelationFormProps {
  sourceId: string;
  sourceLabel: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: () => void;
}

const RELATION_TYPES = Object.keys(RELATION_COLORS);

export function RelationForm({
  sourceId,
  sourceLabel,
  open,
  onOpenChange,
  onSuccess,
}: RelationFormProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const { data: searchResults } = useSearchMemories(searchQuery, undefined, 5);
  const createMutation = useCreateRelation();

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    reset,
    formState: { errors },
  } = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      targetId: "",
      relationType: "related",
      weight: 0.8,
    },
  });

  const selectedTargetId = watch("targetId");
  const selectedRelationType = watch("relationType");
  const weight = watch("weight");

  const onSubmit = async (data: FormData) => {
    await createMutation.mutateAsync({
      sourceId,
      targetId: data.targetId,
      relationType: data.relationType,
      weight: data.weight,
    });
    reset();
    setSearchQuery("");
    onOpenChange(false);
    onSuccess();
  };

  const handleTargetSelect = (id: string) => {
    setValue("targetId", id);
    setSearchQuery("");
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>Create Relation</DialogTitle>
          <DialogDescription>
            From: &quot;{sourceLabel}&quot;
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
          {/* Target Memory Search */}
          <div className="space-y-2">
            <Label>Target Memory</Label>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search for target memory..."
                className="pl-10"
              />
            </div>

            {searchQuery.length > 0 && searchResults && (
              <div className="border rounded-lg max-h-40 overflow-y-auto">
                {searchResults.map((memory) => (
                  <button
                    key={memory.id}
                    type="button"
                    onClick={() => handleTargetSelect(memory.id)}
                    className={`w-full px-3 py-2 text-left text-sm hover:bg-muted transition-colors ${
                      selectedTargetId === memory.id ? "bg-muted" : ""
                    }`}
                  >
                    <p className="line-clamp-1">{memory.content}</p>
                    <Badge variant="outline" className="text-xs mt-1">
                      {memory.memory_type}
                    </Badge>
                  </button>
                ))}
              </div>
            )}

            {selectedTargetId && (
              <p className="text-sm text-muted-foreground">
                Selected: {selectedTargetId.slice(0, 8)}...
              </p>
            )}
            {errors.targetId && (
              <p className="text-sm text-destructive">{errors.targetId.message}</p>
            )}
          </div>

          {/* Relation Type */}
          <div className="space-y-2">
            <Label>Relation Type</Label>
            <div className="grid grid-cols-3 gap-2">
              {RELATION_TYPES.map((type) => (
                <button
                  key={type}
                  type="button"
                  onClick={() => setValue("relationType", type)}
                  className={`p-2 text-sm rounded-lg border transition-colors ${
                    selectedRelationType === type
                      ? "border-primary bg-primary/10"
                      : "border-muted hover:border-primary/50"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <div
                      className="w-2 h-2 rounded-full"
                      style={{ backgroundColor: RELATION_COLORS[type] }}
                    />
                    <span>{type}</span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1 text-left">
                    {RELATION_DESCRIPTIONS[type]}
                  </p>
                </button>
              ))}
            </div>
          </div>

          {/* Weight */}
          <div className="space-y-2">
            <div className="flex justify-between">
              <Label>Strength</Label>
              <span className="text-sm text-muted-foreground">
                {weight.toFixed(1)}
              </span>
            </div>
            <Slider
              value={[weight]}
              onValueChange={([v]) => setValue("weight", v)}
              min={0}
              max={1}
              step={0.1}
            />
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>Weak</span>
              <span>Strong</span>
            </div>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={createMutation.isPending}>
              {createMutation.isPending ? "Creating..." : "Create Relation"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
