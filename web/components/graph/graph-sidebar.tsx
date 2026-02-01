"use client";

import { GraphNode } from "@/lib/api";
import { useRelations, RELATION_COLORS } from "@/lib/hooks/use-graph";
import { useMemory } from "@/lib/hooks/use-memories";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ArrowRight, ArrowLeft, Link2, Eye, Target, Plus } from "lucide-react";

interface GraphSidebarProps {
  selectedNode: GraphNode | null;
  allNodes: GraphNode[];
  onNodeSelect: (node: GraphNode | null) => void;
  onCenterNode: (id: string) => void;
  onAddRelation?: () => void;
}

export function GraphSidebar({
  selectedNode,
  allNodes,
  onNodeSelect,
  onCenterNode,
  onAddRelation,
}: GraphSidebarProps) {
  // Helper to get node label by ID
  const getNodeLabel = (id: string): string => {
    const node = allNodes.find((n) => n.id === id);
    return node?.label ?? id.slice(0, 8) + "...";
  };

  // Helper to navigate to a related node
  const handleRelationClick = (nodeId: string) => {
    const node = allNodes.find((n) => n.id === nodeId);
    if (node) {
      onNodeSelect(node);
    } else {
      // Node not in current graph, center on it to load its subgraph
      onCenterNode(nodeId);
    }
  };
  const { data: memory } = useMemory(selectedNode?.id ?? null);
  const { data: relationsData } = useRelations(selectedNode?.id ?? null);

  if (!selectedNode) {
    return (
      <div className="p-4 text-center text-muted-foreground">
        <p className="text-sm">Select a node to view details</p>
        <p className="text-xs mt-2">
          Click on a node in the graph to see its information and relationships
        </p>
      </div>
    );
  }

  const relations = relationsData?.relations ?? [];
  const outgoing = relations.filter((r) => r.source_id === selectedNode.id);
  const incoming = relations.filter((r) => r.target_id === selectedNode.id);

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4">
      {/* Node Details */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg truncate">
              {selectedNode.label}
            </CardTitle>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => onCenterNode(selectedNode.id)}
              title="Center on this node"
            >
              <Target className="h-4 w-4" />
            </Button>
          </div>
          <CardDescription>
            {selectedNode.type && (
              <Badge variant="outline" className="mr-2">
                {selectedNode.type}
              </Badge>
            )}
            Importance: {(selectedNode.importance * 100).toFixed(0)}%
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {memory?.content && (
            <div>
              <p className="text-sm text-muted-foreground mb-1">Content</p>
              <p className="text-sm line-clamp-4">{memory.content}</p>
            </div>
          )}

          {selectedNode.tags.length > 0 && (
            <div>
              <p className="text-sm text-muted-foreground mb-1">Tags</p>
              <div className="flex flex-wrap gap-1">
                {selectedNode.tags.map((tag) => (
                  <Badge key={tag} variant="secondary" className="text-xs">
                    {tag}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          {onAddRelation && (
            <Button
              variant="outline"
              size="sm"
              className="w-full mt-2"
              onClick={onAddRelation}
            >
              <Plus className="h-4 w-4 mr-2" />
              Add Relation from this Memory
            </Button>
          )}
        </CardContent>
      </Card>

      {/* Relations Summary */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Link2 className="h-4 w-4" />
            Relations ({relations.length})
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Outgoing */}
          {outgoing.length > 0 && (
            <div>
              <p className="text-sm text-muted-foreground mb-2 flex items-center gap-1">
                <ArrowRight className="h-3 w-3" />
                Outgoing ({outgoing.length})
              </p>
              <div className="space-y-2">
                {outgoing.map((r) => (
                  <button
                    key={r.id}
                    onClick={() => handleRelationClick(r.target_id)}
                    className="flex items-center gap-2 text-sm p-2 rounded bg-muted/50 hover:bg-muted w-full text-left transition-colors"
                    title={`Click to view: ${getNodeLabel(r.target_id)}`}
                  >
                    <div
                      className="w-2 h-2 rounded-full shrink-0"
                      style={{
                        backgroundColor: RELATION_COLORS[r.type] ?? "#6b7280",
                      }}
                    />
                    <span className="font-medium shrink-0">{r.type}</span>
                    <span className="text-muted-foreground shrink-0">→</span>
                    <span className="truncate text-primary hover:underline">
                      {getNodeLabel(r.target_id)}
                    </span>
                    <Eye className="h-3 w-3 ml-auto shrink-0 text-muted-foreground" />
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Incoming */}
          {incoming.length > 0 && (
            <div>
              <p className="text-sm text-muted-foreground mb-2 flex items-center gap-1">
                <ArrowLeft className="h-3 w-3" />
                Incoming ({incoming.length})
              </p>
              <div className="space-y-2">
                {incoming.map((r) => (
                  <button
                    key={r.id}
                    onClick={() => handleRelationClick(r.source_id)}
                    className="flex items-center gap-2 text-sm p-2 rounded bg-muted/50 hover:bg-muted w-full text-left transition-colors"
                    title={`Click to view: ${getNodeLabel(r.source_id)}`}
                  >
                    <Eye className="h-3 w-3 shrink-0 text-muted-foreground" />
                    <span className="truncate text-primary hover:underline">
                      {getNodeLabel(r.source_id)}
                    </span>
                    <span className="text-muted-foreground shrink-0">→</span>
                    <span className="font-medium shrink-0">{r.type}</span>
                    <div
                      className="w-2 h-2 rounded-full shrink-0 ml-auto"
                      style={{
                        backgroundColor: RELATION_COLORS[r.type] ?? "#6b7280",
                      }}
                    />
                  </button>
                ))}
              </div>
            </div>
          )}

          {relations.length === 0 && (
            <p className="text-sm text-muted-foreground text-center py-2">
              No relations yet
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
